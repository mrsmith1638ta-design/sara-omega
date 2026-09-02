param(
  [Parameter(Mandatory = $true)]
  [string]$TargetPath,
  [switch]$Apply,
  [switch]$SkipBuild,
  [switch]$SkipMount
)

$ErrorActionPreference = "Stop"

function Write-Step {
  param([string]$Message)
  Write-Host ""
  Write-Host "=== $Message ==="
}

function Resolve-RequiredPath {
  param([string]$Path)
  if (-not (Test-Path -LiteralPath $Path)) {
    throw "Required path not found: $Path"
  }
  return (Resolve-Path -LiteralPath $Path).Path
}

function Assert-ChildPath {
  param(
    [string]$Root,
    [string]$Path
  )
  $resolvedRoot = Resolve-RequiredPath $Root
  $resolvedPath = Resolve-RequiredPath $Path
  if (-not $resolvedPath.StartsWith($resolvedRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing to operate outside root: $resolvedPath"
  }
}

function Convert-ToRelativePath {
  param(
    [string]$Root,
    [string]$FullName
  )
  return $FullName.Substring($Root.Length + 1).Replace("\", "/")
}

function Test-ProtectedRelativePath {
  param([string]$Relative)
  $protected = @(
    "^\.env($|\.)",
    "^data/",
    "^config/",
    "^\.railway/",
    "^railpack\.json$",
    "^railway\.json$",
    "^nixpacks\.toml$",
    "^Procfile$",
    "^Dockerfile$",
    "^runtime\.txt$",
    "^requirements.*\.txt$",
    "^app/server\.py$",
    "^app/main\.py$",
    "^app/bootstrap.*\.py$",
    "^app/auth.*\.py$",
    "^app/authorization.*\.py$",
    "^app/fail.*\.py$",
    "^app/.*v3.*\.py$",
    "^app/.*V3.*\.py$"
  )
  foreach ($pattern in $protected) {
    if ($Relative -match $pattern) {
      return $true
    }
  }
  return $false
}

function Test-SourceExcludedPath {
  param([string]$Relative)
  $excluded = @(
    "^\.git/",
    "^\.venv/",
    "^__pycache__/",
    "/__pycache__/",
    "^\.pytest_cache/",
    "^dist/",
    "^sara_omega\.egg-info/",
    "^data/.*\.(db|jsonl)$"
  )
  foreach ($pattern in $excluded) {
    if ($Relative -match $pattern) {
      return $true
    }
  }
  return $false
}

function Find-BootstrapFile {
  param([string]$TargetRoot)
  $candidates = @("app/server.py", "app/main.py", "server.py", "main.py")
  foreach ($candidate in $candidates) {
    $path = Join-Path $TargetRoot $candidate
    if (Test-Path -LiteralPath $path) {
      return $path
    }
  }
  return $null
}

function Add-RouterMount {
  param([string]$BootstrapPath)
  $text = Get-Content -LiteralPath $BootstrapPath -Raw
  if ($text -match "enterprise_runtime_router" -or $text -match "include_router\(.*enterprise") {
    return "already_mounted"
  }
  if ($text -notmatch "FastAPI\(") {
    return "not_fastapi_bootstrap"
  }

  $relativeImport = $BootstrapPath.Replace("\", "/") -match "/app/"
  $importLine = if ($relativeImport) {
    "from .enterprise_runtime import router as enterprise_runtime_router"
  } else {
    "from app.enterprise_runtime import router as enterprise_runtime_router"
  }

  $lines = New-Object System.Collections.Generic.List[string]
  $lines.AddRange([string[]]($text -split "`r?`n"))

  $lastImportIndex = -1
  for ($i = 0; $i -lt $lines.Count; $i++) {
    if ($lines[$i] -match "^(from|import) ") {
      $lastImportIndex = $i
    }
  }
  if ($lastImportIndex -ge 0) {
    $lines.Insert($lastImportIndex + 1, $importLine)
  } else {
    $lines.Insert(0, $importLine)
  }

  $appIndex = -1
  for ($i = 0; $i -lt $lines.Count; $i++) {
    if ($lines[$i] -match "^\s*app\s*=\s*FastAPI\(") {
      $appIndex = $i
      break
    }
  }
  if ($appIndex -lt 0) {
    return "app_assignment_not_found"
  }
  $lines.Insert($appIndex + 1, "app.include_router(enterprise_runtime_router)")
  [System.IO.File]::WriteAllText($BootstrapPath, ($lines -join [Environment]::NewLine), [System.Text.Encoding]::UTF8)
  return "mounted"
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$sourceRoot = Resolve-RequiredPath (Split-Path -Parent $scriptDir)
$targetRoot = Resolve-RequiredPath $TargetPath

if ($sourceRoot -eq $targetRoot) {
  throw "Target is the verified source folder. Point TargetPath at the separate Railway production codebase."
}

Write-Step "Railway consume verified build"
Write-Host "Source: $sourceRoot"
Write-Host "Target: $targetRoot"
Write-Host "Mode:   $(if ($Apply) { "APPLY" } else { "DRY RUN" })"

$requiredSourceFiles = @(
  "app/enterprise_runtime.py",
  "app/runtime_assurance.py",
  "app/module_awareness.py",
  "app/titan.py",
  "app/providers/data_analytics.py",
  "MANIFEST.sha256",
  "BUILD_VERIFICATION.md"
)
foreach ($relative in $requiredSourceFiles) {
  $path = Join-Path $sourceRoot $relative
  if (-not (Test-Path -LiteralPath $path)) {
    throw "Verified build is missing required file: $relative"
  }
}

if (-not $SkipBuild) {
  Write-Step "Verify source build"
  & (Join-Path $sourceRoot "scripts/build.ps1") -NoArchive
}

Write-Step "Plan overlay"
$allSourceFiles = Get-ChildItem -LiteralPath $sourceRoot -File -Recurse -Force | ForEach-Object {
  $relative = Convert-ToRelativePath $sourceRoot $_.FullName
  [pscustomobject]@{ File = $_; Relative = $relative }
} | Where-Object {
  -not (Test-SourceExcludedPath $_.Relative) -and
  -not (Test-ProtectedRelativePath $_.Relative)
}

$protectedExisting = @()
foreach ($relative in @("data", "config", ".env", "railpack.json", "railway.json", "nixpacks.toml", "Procfile", "Dockerfile", "app/server.py", "app/main.py")) {
  $path = Join-Path $targetRoot $relative
  if (Test-Path -LiteralPath $path) {
    $protectedExisting += $relative
  }
}

$bootstrap = Find-BootstrapFile $targetRoot
$plannedMount = if ($SkipMount) { "skipped" } elseif ($bootstrap) { $bootstrap } else { "not_found" }

Write-Host "Files to copy: $($allSourceFiles.Count)"
Write-Host "Protected existing paths: $($protectedExisting -join ', ')"
Write-Host "Bootstrap mount target: $plannedMount"

if (-not $Apply) {
  Write-Host ""
  Write-Host "DRY RUN COMPLETE. No Railway production files were modified."
  Write-Host "Apply with:"
  Write-Host ".\railway-consume.cmd -TargetPath `"$targetRoot`" -Apply"
  exit 0
}

Write-Step "Backup target"
$stamp = Get-Date -Format "yyyyMMddHHmmss"
$backupRoot = Join-Path (Split-Path -Parent $targetRoot) ("sara_railway_backup_" + $stamp)
if (Test-Path -LiteralPath $backupRoot) {
  throw "Backup path already exists: $backupRoot"
}
Copy-Item -LiteralPath $targetRoot -Destination $backupRoot -Recurse
Write-Host "Backup: $backupRoot"

Write-Step "Copy verified enterprise build files"
foreach ($item in $allSourceFiles) {
  $destination = Join-Path $targetRoot $item.Relative
  $destinationDir = Split-Path -Parent $destination
  if (-not (Test-Path -LiteralPath $destinationDir)) {
    New-Item -ItemType Directory -Path $destinationDir | Out-Null
  }
  Copy-Item -LiteralPath $item.File.FullName -Destination $destination -Force
}

if (-not $SkipMount) {
  Write-Step "Mount enterprise runtime router"
  if (-not $bootstrap) {
    throw "No FastAPI bootstrap file found. Enterprise files copied, but router was not mounted."
  }
  $mountResult = Add-RouterMount $bootstrap
  Write-Host "Mount result: $mountResult"
  if ($mountResult -notin @("mounted", "already_mounted")) {
    throw "Router mount failed: $mountResult"
  }
}

Write-Step "Post-check protected paths"
foreach ($relative in $protectedExisting) {
  $path = Join-Path $targetRoot $relative
  if (-not (Test-Path -LiteralPath $path)) {
    throw "Protected path missing after overlay: $relative"
  }
}

Write-Step "Railway consume complete"
Write-Host "Copied files: $($allSourceFiles.Count)"
Write-Host "Backup:       $backupRoot"
Write-Host "Bootstrap:    $plannedMount"
Write-Host "Next: run the Railway production test/start command from the target folder before deploying."
