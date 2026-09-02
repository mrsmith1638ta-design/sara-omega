[CmdletBinding()]
param(
    [string]$ProjectId = "d231d279-92f3-435d-a1d6-c38849b6bfc8",
    [string]$ProductionDomain = "sara-omega-production.up.railway.app",
    [string]$ServiceName = "sara-omega",
    [string]$EnvironmentName = "production",
    [ValidateRange(1, 120)][int]$MaxAttempts = 60,
    [ValidateRange(1, 30)][int]$DelaySeconds = 5
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-SaraLog {
    param([Parameter(Mandatory = $true)][string]$Message)
    Write-Host "[SARA-OMEGA V3.2.1] $Message"
}

function Resolve-RailwayNativeCommand {
    $candidates = New-Object System.Collections.Generic.List[string]

    $railwayCmd = Get-Command railway.cmd -ErrorAction SilentlyContinue
    if ($null -ne $railwayCmd -and -not [string]::IsNullOrWhiteSpace($railwayCmd.Source)) {
        $candidates.Add($railwayCmd.Source)
    }

    $railwayExe = Get-Command railway.exe -ErrorAction SilentlyContinue
    if ($null -ne $railwayExe -and -not [string]::IsNullOrWhiteSpace($railwayExe.Source)) {
        $candidates.Add($railwayExe.Source)
    }

    $railwayAny = Get-Command railway -ErrorAction SilentlyContinue
    if ($null -ne $railwayAny -and -not [string]::IsNullOrWhiteSpace($railwayAny.Source)) {
        $source = $railwayAny.Source
        $dir = Split-Path -Parent $source
        if (-not [string]::IsNullOrWhiteSpace($dir)) {
            $cmdSibling = Join-Path $dir "railway.cmd"
            $exeSibling = Join-Path $dir "railway.exe"
            if (Test-Path $cmdSibling) { $candidates.Add($cmdSibling) }
            if (Test-Path $exeSibling) { $candidates.Add($exeSibling) }
        }
        if ([System.IO.Path]::GetExtension($source) -ne ".ps1") {
            $candidates.Add($source)
        }
    }

    foreach ($candidate in ($candidates | Select-Object -Unique)) {
        if (Test-Path $candidate) {
            return (Resolve-Path $candidate).Path
        }
    }

    throw "A native Railway CLI entry point (railway.cmd or railway.exe) was not found."
}

function Invoke-RailwayCapture {
    param(
        [Parameter(Mandatory = $true)][string]$RailwayCommand,
        [Parameter(Mandatory = $true)][string[]]$Arguments
    )

    $previousPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = "Continue"
        $output = & $RailwayCommand @Arguments 2>$null
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousPreference
    }

    if ($exitCode -ne 0) {
        $safeArgs = ($Arguments | ForEach-Object {
            if ($_ -match 'TOKEN|KEY|SECRET') { '<redacted>' } else { $_ }
        }) -join ' '
        throw "Railway command failed with exit code $exitCode`: $safeArgs"
    }

    return ($output -join "`n")
}

function Get-KvValue {
    param(
        [Parameter(Mandatory = $true)][string]$KvText,
        [Parameter(Mandatory = $true)][string]$Name
    )

    foreach ($line in ($KvText -split "`r?`n")) {
        if ($line.StartsWith("$Name=")) {
            return $line.Substring($Name.Length + 1)
        }
    }
    return $null
}

function Test-LiveProductionReady {
    param([Parameter(Mandatory = $true)][string]$BaseUrl)

    try {
        $readyResponse = Invoke-WebRequest -Uri "$BaseUrl/health/ready" -UseBasicParsing -TimeoutSec 10 -ErrorAction Stop
        if ($readyResponse.StatusCode -ne 200) { return $false }
        $ready = $readyResponse.Content | ConvertFrom-Json -ErrorAction Stop
        if (-not [bool]$ready.ready) { return $false }

        $acceptanceResponse = Invoke-WebRequest -Uri "$BaseUrl/health/production-acceptance" -UseBasicParsing -TimeoutSec 10 -ErrorAction Stop
        if ($acceptanceResponse.StatusCode -ne 200) { return $false }
        $acceptance = $acceptanceResponse.Content | ConvertFrom-Json -ErrorAction Stop
        if (-not [bool]$acceptance.production_accepted) { return $false }

        return $true
    }
    catch {
        return $false
    }
}

$railwayCommand = Resolve-RailwayNativeCommand
Write-SaraLog "Railway native entry point VERIFIED: $([System.IO.Path]::GetFileName($railwayCommand))"

$pythonExe = $null
$pythonPrefix = @()
if (Get-Command python -ErrorAction SilentlyContinue) {
    $pythonExe = "python"
}
elseif (Get-Command py -ErrorAction SilentlyContinue) {
    $pythonExe = "py"
    $pythonPrefix = @("-3")
}
else {
    throw "Python 3 is required for live production acceptance."
}

if (-not (Test-Path "tools/railway_runtime_acceptance.py")) {
    throw "tools/railway_runtime_acceptance.py is missing."
}
if (-not (Select-String -Path "tools/railway_runtime_acceptance.py" -Pattern 'require-gpt-action-token' -Quiet)) {
    throw "The live acceptance controller does not contain the governed GPT Action token gate."
}

Write-SaraLog "Verifying Railway authentication"
$whoami = Invoke-RailwayCapture -RailwayCommand $railwayCommand -Arguments @("whoami")
if ([string]::IsNullOrWhiteSpace($whoami)) {
    throw "Railway authentication is not active."
}

$targetArgs = @("--project", $ProjectId, "--environment", $EnvironmentName, "--service", $ServiceName)
Write-SaraLog "Verifying canonical production identity"
$domainJson = Invoke-RailwayCapture -RailwayCommand $railwayCommand -Arguments (@("domain", "list") + $targetArgs + @("--json"))
if ($domainJson -notmatch [regex]::Escape($ProductionDomain)) {
    throw "Project $ProjectId does not own $ProductionDomain for service $ServiceName."
}
Write-SaraLog "Canonical production identity VERIFIED: project=$ProjectId service=$ServiceName domain=$ProductionDomain"

Write-SaraLog "Reading existing production credentials without printing secrets"
$kv = Invoke-RailwayCapture -RailwayCommand $railwayCommand -Arguments (@("variable", "list") + $targetArgs + @("--kv"))
$ownerToken = Get-KvValue -KvText $kv -Name "OWNER_TOKEN"
$gptActionToken = Get-KvValue -KvText $kv -Name "GPT_ACTION_TOKEN"

if ([string]::IsNullOrWhiteSpace($ownerToken)) {
    throw "OWNER_TOKEN is missing in canonical production."
}
if ([string]::IsNullOrWhiteSpace($gptActionToken)) {
    throw "GPT_ACTION_TOKEN is missing in canonical production."
}

$baseUrl = "https://$ProductionDomain"
Write-SaraLog "Waiting on live HTTPS readiness and production acceptance"
$liveReady = $false
for ($attempt = 1; $attempt -le $MaxAttempts; $attempt++) {
    if (Test-LiveProductionReady -BaseUrl $baseUrl) {
        $liveReady = $true
        break
    }
    Start-Sleep -Seconds $DelaySeconds
}
if (-not $liveReady) {
    throw "Production did not reach live readiness and production_accepted within the bounded acceptance window."
}
Write-SaraLog "Live HTTPS runtime VERIFIED"

Write-SaraLog "Running governed production acceptance"
$oldOwner = $env:SARA_OWNER_TOKEN
$oldAction = $env:SARA_GPT_ACTION_TOKEN
try {
    $env:SARA_OWNER_TOKEN = $ownerToken
    $env:SARA_GPT_ACTION_TOKEN = $gptActionToken

    $acceptanceArgs = @() + $pythonPrefix + @(
        "tools/railway_runtime_acceptance.py",
        $baseUrl,
        "--require-gpt-action-token"
    )
    & $pythonExe @acceptanceArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Live GPT Action production acceptance failed."
    }
}
finally {
    if ($null -eq $oldOwner) { Remove-Item Env:SARA_OWNER_TOKEN -ErrorAction SilentlyContinue } else { $env:SARA_OWNER_TOKEN = $oldOwner }
    if ($null -eq $oldAction) { Remove-Item Env:SARA_GPT_ACTION_TOKEN -ErrorAction SilentlyContinue } else { $env:SARA_GPT_ACTION_TOKEN = $oldAction }
    $ownerToken = $null
    $gptActionToken = $null
    $kv = $null
}

$baseUrl | Set-Content -Path "railway-public-url.txt" -Encoding ascii
Write-SaraLog "PRODUCTION ACCEPTANCE PASS $baseUrl"
Write-SaraLog "GPT_ACTION_TOKEN VERIFIED with limited Action authority; OWNER_TOKEN remains owner/admin only"
