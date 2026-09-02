param(
  [string]$Python = "python",
  [switch]$SkipInstall,
  [switch]$SkipTests,
  [switch]$NoArchive
)

$ErrorActionPreference = "Stop"

function Write-Step {
  param([string]$Message)
  Write-Host ""
  Write-Host "=== $Message ==="
}

function Require-Command {
  param([string]$Name)
  if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
    throw "$Name is required but was not found on PATH."
  }
}

function Assert-InProject {
  param(
    [string]$Root,
    [string]$Path
  )
  $resolvedRoot = (Resolve-Path -LiteralPath $Root).Path
  $resolvedPath = (Resolve-Path -LiteralPath $Path).Path
  if (-not $resolvedPath.StartsWith($resolvedRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing to operate outside project: $resolvedPath"
  }
}

function Get-Sha256Hex {
  param([string]$Path)
  $stream = [System.IO.File]::OpenRead($Path)
  try {
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
      $bytes = $sha.ComputeHash($stream)
      return ([System.BitConverter]::ToString($bytes) -replace "-", "").ToLowerInvariant()
    } finally {
      $sha.Dispose()
    }
  } finally {
    $stream.Dispose()
  }
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptDir
Push-Location $projectRoot

try {
  Write-Step "SARA Omega build preflight"
  Require-Command $Python
  $pythonVersion = & $Python --version
  Write-Host "Project: $projectRoot"
  Write-Host "Python:  $pythonVersion"
  $git = Get-Command git -ErrorAction SilentlyContinue
  if ($git) {
    Write-Host "Git:     $(& git --version)"
  } else {
    Write-Host "Git:     not found; continuing without git metadata"
  }

  Write-Step "Virtual environment"
  $venvDir = Join-Path $projectRoot ".venv"
  $venvPython = Join-Path $venvDir "Scripts\python.exe"
  if (-not (Test-Path -LiteralPath $venvPython)) {
    & $Python -m venv $venvDir
  }
  Assert-InProject $projectRoot $venvPython
  Write-Host "Using: $venvPython"

  if (-not $SkipInstall) {
    Write-Step "Install package and test dependencies"
    & $venvPython -m pip install -e ".[dev]"
  }

  if (-not $env:SARA_RUNTIME_ASSURANCE_SECRET) {
    $env:SARA_RUNTIME_ASSURANCE_SECRET = "local-build-only-runtime-assurance-secret"
  }
  if (-not $env:TITAN_HMAC_SECRET) {
    $env:TITAN_HMAC_SECRET = "local-build-only-titan-secret"
  }

  Write-Step "Compile"
  & $venvPython -m compileall app tests

  $testCount = "skipped"
  if (-not $SkipTests) {
    Write-Step "Tests"
    $pytestOutput = & $venvPython -m pytest 2>&1
    $pytestExit = $LASTEXITCODE
    $pytestOutput | ForEach-Object { Write-Host $_ }
    if ($pytestExit -ne 0) {
      throw "pytest failed with exit code $pytestExit"
    }
    $summary = ($pytestOutput | Select-String -Pattern "(\d+) passed").Matches | Select-Object -Last 1
    if ($summary) {
      $testCount = $summary.Groups[1].Value
    }
  }

  Write-Step "Refresh build verification"
  $pyFileCount = (Get-ChildItem -Path app,tests -Filter "*.py" -Recurse | Measure-Object).Count
  $verificationPath = Join-Path $projectRoot "BUILD_VERIFICATION.md"
  $today = Get-Date -Format "yyyy-MM-dd"
  $verification = Get-Content -LiteralPath $verificationPath -Raw
  $verification = [regex]::Replace($verification, "Date: \d{4}-\d{2}-\d{2}", "Date: $today")
  $verification = [regex]::Replace($verification, "- Python files syntax checked: .+", "- Python files syntax checked: $pyFileCount")
  if ($testCount -ne "skipped") {
    $verification = [regex]::Replace($verification, "- Offline tests: .+", "- Offline tests: $testCount passed")
  }
  [System.IO.File]::WriteAllText($verificationPath, $verification, [System.Text.Encoding]::UTF8)
  Write-Host "Python files: $pyFileCount"
  Write-Host "Tests:        $testCount"

  Write-Step "Refresh manifest"
  $manifestPath = Join-Path $projectRoot "MANIFEST.sha256"
  $excludedPattern = "\\(\.git|\.venv|__pycache__|\.pytest_cache|dist)\\|\\data\\.*\.(db|jsonl)$"
  if ($git) {
    $trackedFiles = & git ls-files
    if ($LASTEXITCODE -ne 0) {
      throw "git ls-files failed while building the release manifest"
    }
    $files = $trackedFiles | Where-Object {
      $_ -ne "MANIFEST.sha256"
    } | ForEach-Object {
      Get-Item -LiteralPath (Join-Path $projectRoot $_)
    } | Sort-Object FullName
  } else {
    $files = Get-ChildItem -File -Recurse -Force | Where-Object {
      $_.FullName -ne $manifestPath -and
      $_.FullName -notmatch $excludedPattern
    } | Sort-Object FullName
  }
  $lines = foreach ($file in $files) {
    $relative = $file.FullName.Substring($projectRoot.Length + 1).Replace("\", "/")
    $hash = Get-Sha256Hex $file.FullName
    "$hash  $relative"
  }
  [System.IO.File]::WriteAllLines($manifestPath, [string[]]$lines, [System.Text.Encoding]::ASCII)
  Write-Host "Manifest entries: $($lines.Count)"

  Write-Step "Verify manifest"
  $bad = @()
  $__saraManifestRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
[Environment]::CurrentDirectory = $__saraManifestRoot

Get-Content -LiteralPath $manifestPath | ForEach-Object {
    if (-not $_.Trim()) { return }
    $parts = $_ -split "  ", 2
    $expected = $parts[0]
    $path = $parts[1].Replace("/", "\")
    if (-not (Test-Path -LiteralPath $path)) {
      $bad += "missing $($parts[1])"
      return
    }
    $actual = Get-Sha256Hex $path
    if ($actual -ne $expected) {
      $bad += "mismatch $($parts[1])"
    }
  }
  if ($bad.Count) {
    $bad | ForEach-Object { Write-Error $_ }
    throw "Manifest verification failed"
  }
  Write-Host "MANIFEST OK"

  $archivePath = $null
  if (-not $NoArchive) {
    Write-Step "Package clean ZIP"
    $distDir = Join-Path $projectRoot "dist"
    if (-not (Test-Path -LiteralPath $distDir)) {
      New-Item -ItemType Directory -Path $distDir | Out-Null
    }
    Assert-InProject $projectRoot $distDir
    $stamp = Get-Date -Format "yyyyMMddHHmmss"
    $archivePath = Join-Path $distDir "SARA_OMEGA_FULL_ARCHITECTURE_v1.0_build_$stamp.zip"
    $stageDir = Join-Path $distDir "_stage_$stamp"
    New-Item -ItemType Directory -Path $stageDir | Out-Null
    Assert-InProject $projectRoot $stageDir
    try {
      foreach ($file in $files) {
        $relative = $file.FullName.Substring($projectRoot.Length + 1)
        $target = Join-Path $stageDir $relative
        $targetDir = Split-Path -Parent $target
        if (-not (Test-Path -LiteralPath $targetDir)) {
          New-Item -ItemType Directory -Path $targetDir | Out-Null
        }
        Copy-Item -LiteralPath $file.FullName -Destination $target
      }
      Copy-Item -LiteralPath $manifestPath -Destination (Join-Path $stageDir "MANIFEST.sha256")
      Compress-Archive -Path (Join-Path $stageDir "*") -DestinationPath $archivePath -Force
      if (-not (Test-Path -LiteralPath $archivePath)) {
        throw "Archive was not created: $archivePath"
      }
    } finally {
      Assert-InProject $projectRoot $stageDir
      Remove-Item -LiteralPath $stageDir -Recurse -Force
    }
    Write-Host "Archive: $archivePath"
  }

  Write-Step "Build complete"
  Write-Host "Compile:  OK"
  Write-Host "Tests:    $testCount"
  Write-Host "Manifest: OK"
  if ($archivePath) {
    Write-Host "ZIP:      $archivePath"
  }
} finally {
  Pop-Location
}
