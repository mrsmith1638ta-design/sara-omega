[CmdletBinding()]
param(
    [string]$ProjectId = "d231d279-92f3-435d-a1d6-c38849b6bfc8",
    [string]$ProductionDomain = "sara-omega-production.up.railway.app",
    [string]$ServiceName = "sara-omega",
    [string]$EnvironmentName = "production"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-SaraLog {
    param([Parameter(Mandatory = $true)][string]$Message)
    Write-Host "[SARA-OMEGA V3.2.1] $Message"
}

function Invoke-RailwayCapture {
    param([Parameter(Mandatory = $true)][string[]]$Arguments)
    $output = & railway @Arguments 2>&1
    if ($LASTEXITCODE -ne 0) {
        $safeArgs = ($Arguments | ForEach-Object {
            if ($_ -match 'TOKEN|KEY|SECRET') { '<redacted>' } else { $_ }
        }) -join ' '
        throw "Railway command failed: railway $safeArgs"
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

function New-SecureHex {
    param([ValidateRange(16, 256)][int]$Bytes = 48)
    $buffer = New-Object byte[] $Bytes
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $rng.GetBytes($buffer)
    }
    finally {
        $rng.Dispose()
    }
    return ([System.BitConverter]::ToString($buffer)).Replace('-', '').ToLowerInvariant()
}

function Test-DataVolume {
    param([Parameter(Mandatory = $true)][string]$JsonText)
    try {
        $doc = $JsonText | ConvertFrom-Json -ErrorAction Stop
    }
    catch {
        return $false
    }

    function Walk-Node {
        param($Node)
        if ($null -eq $Node) { return $false }

        if ($Node -is [System.Collections.IEnumerable] -and $Node -isnot [string] -and $Node -isnot [System.Management.Automation.PSCustomObject]) {
            foreach ($item in $Node) {
                if (Walk-Node $item) { return $true }
            }
            return $false
        }

        if ($Node -is [System.Management.Automation.PSCustomObject]) {
            foreach ($prop in $Node.PSObject.Properties) {
                $normalized = ($prop.Name.ToLowerInvariant() -replace '_', '')
                if (($normalized -eq 'mount' -or $normalized -eq 'mountpath') -and [string]$prop.Value -eq '/data') {
                    return $true
                }
                if (Walk-Node $prop.Value) { return $true }
            }
        }
        return $false
    }

    return (Walk-Node $doc)
}

if (-not (Get-Command railway -ErrorAction SilentlyContinue)) {
    throw "Railway CLI is required."
}

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
    throw "Python 3 is required for the live acceptance controller."
}

if (-not (Test-Path "main.py")) {
    throw "Run this controller from the SARA-OMEGA repository root."
}
if (-not (Select-String -Path "main.py" -Pattern 'GPT_ACTION_TOKEN' -Quiet)) {
    throw "Local main.py does not contain the governed GPT_ACTION_TOKEN lane. Refusing to deploy stale source."
}
if (-not (Test-Path "tools/railway_runtime_acceptance.py")) {
    throw "tools/railway_runtime_acceptance.py is missing."
}
if (-not (Select-String -Path "tools/railway_runtime_acceptance.py" -Pattern 'require-gpt-action-token' -Quiet)) {
    throw "Local acceptance controller does not support the GPT Action token gate. Refusing deployment."
}

Write-SaraLog "Verifying authenticated Railway identity"
& railway whoami
if ($LASTEXITCODE -ne 0) { throw "Railway authentication is not active." }

Write-SaraLog "Verifying canonical production identity before any write"
$domainJson = Invoke-RailwayCapture @(
    "domain", "list",
    "--project", $ProjectId,
    "--environment", $EnvironmentName,
    "--service", $ServiceName,
    "--json"
)
if ($domainJson -notmatch [regex]::Escape($ProductionDomain)) {
    throw "Project $ProjectId does not currently own $ProductionDomain for service $ServiceName. No Railway changes were made."
}

Write-SaraLog "Canonical production identity VERIFIED: project=$ProjectId service=$ServiceName domain=$ProductionDomain"

Invoke-RailwayCapture @("link", "--project", $ProjectId, "--environment", $EnvironmentName) | Out-Null
Invoke-RailwayCapture @("service", $ServiceName) | Out-Null

$servicesJson = Invoke-RailwayCapture @("service", "list", "--json")
if ($servicesJson -notmatch ('"name"\s*:\s*"' + [regex]::Escape($ServiceName) + '"')) {
    throw "Expected production service $ServiceName is missing from project $ProjectId. Refusing to create a replacement service."
}

Write-SaraLog "Reading production variable inventory without printing secrets"
$kv = Invoke-RailwayCapture @("variable", "list", "--service", $ServiceName, "--kv")
$ownerToken = Get-KvValue -KvText $kv -Name "OWNER_TOKEN"
$gptActionToken = Get-KvValue -KvText $kv -Name "GPT_ACTION_TOKEN"
$failsafeHex = Get-KvValue -KvText $kv -Name "SARA_FAILSAFE_MASTER_KEY_HEX"
$failsafeB64 = Get-KvValue -KvText $kv -Name "SARA_FAILSAFE_MASTER_KEY_B64"

if ([string]::IsNullOrWhiteSpace($ownerToken)) {
    throw "OWNER_TOKEN is missing in canonical production. Refusing to invent or rotate owner authority."
}
if ([string]::IsNullOrWhiteSpace($failsafeHex) -and [string]::IsNullOrWhiteSpace($failsafeB64)) {
    throw "Production fail-safe master key is missing. Refusing to invent a replacement key for an accepted production chain."
}

if ([string]::IsNullOrWhiteSpace($gptActionToken)) {
    $gptActionToken = New-SecureHex -Bytes 48
    $gptActionToken | & railway variable set GPT_ACTION_TOKEN --stdin --skip-deploys --service $ServiceName | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Failed to install GPT_ACTION_TOKEN in canonical production." }
    Write-SaraLog "Installed dedicated GPT Action token without printing it"
}
else {
    Write-SaraLog "Existing dedicated GPT Action token retained"
}

Write-SaraLog "Applying production fail-safe variables with literal Linux container paths"
& railway variable set `
    SARA_FAILSAFE_REQUIRED=true `
    SARA_FAILSAFE_ROOT=/data/sara-failsafe `
    SARA_FAILSAFE_REQUIRE_DEDICATED_MOUNT=true `
    SARA_FAILSAFE_MIN_FREE_BYTES=67108864 `
    SARA_RELEASE_VERSION=3.2.1 `
    --skip-deploys --service $ServiceName | Out-Null
if ($LASTEXITCODE -ne 0) { throw "Failed to apply production fail-safe variables." }

Write-SaraLog "Verifying persistent /data volume"
$volumeJson = Invoke-RailwayCapture @("volume", "list", "--json")
if (-not (Test-DataVolume -JsonText $volumeJson)) {
    & railway volume add --mount-path /data --json | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Failed to create persistent /data volume." }
    Write-SaraLog "Created persistent /data volume"
}
else {
    Write-SaraLog "Persistent /data volume already present"
}

Write-SaraLog "Deploying governed SARA-OMEGA V3.2.1 source to canonical production"
& railway up --service $ServiceName --ci
if ($LASTEXITCODE -ne 0) { throw "Railway source deployment failed." }

Write-SaraLog "Waiting for Railway deployment SUCCESS"
$deploymentSucceeded = $false
for ($i = 0; $i -lt 90; $i++) {
    $deploymentJson = Invoke-RailwayCapture @("deployment", "list", "--service", $ServiceName, "--limit", "1", "--json")
    try {
        $doc = $deploymentJson | ConvertFrom-Json -ErrorAction Stop
        $latest = if ($doc -is [System.Array]) { $doc | Select-Object -First 1 } else { $doc }
        $status = [string]($latest.status ?? $latest.state ?? "UNKNOWN")
    }
    catch {
        $status = "UNKNOWN"
    }

    switch ($status.ToUpperInvariant()) {
        "SUCCESS" { $deploymentSucceeded = $true; break }
        "FAILED" { throw "Railway deployment ended in FAILED." }
        "CRASHED" { throw "Railway deployment ended in CRASHED." }
        "REMOVED" { throw "Railway deployment ended in REMOVED." }
    }
    Start-Sleep -Seconds 4
}
if (-not $deploymentSucceeded) { throw "Railway deployment did not reach SUCCESS." }

$baseUrl = "https://$ProductionDomain"
Write-SaraLog "Running live production acceptance with owner and limited Action credentials"
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
    if ($LASTEXITCODE -ne 0) { throw "Live GPT Action production acceptance failed." }
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
Write-SaraLog "GPT_ACTION_TOKEN is live with limited Action authority; OWNER_TOKEN remains owner/admin only"
