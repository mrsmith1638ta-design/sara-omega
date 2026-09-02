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

    throw "A native Railway CLI entry point (railway.cmd or railway.exe) was not found. The railway.ps1 npm shim is intentionally rejected."
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

function Invoke-RailwayWrite {
    param(
        [Parameter(Mandatory = $true)][string]$RailwayCommand,
        [Parameter(Mandatory = $true)][string[]]$Arguments
    )

    $previousPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = "Continue"
        $null = & $RailwayCommand @Arguments 2>$null
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousPreference
    }

    if ($exitCode -ne 0) {
        $safeArgs = ($Arguments | ForEach-Object {
            if ($_ -match 'TOKEN|KEY|SECRET') { '<redacted>' } else { $_ }
        }) -join ' '
        throw "Railway write failed with exit code $exitCode`: $safeArgs"
    }
}

function Invoke-RailwayStdinWrite {
    param(
        [Parameter(Mandatory = $true)][string]$RailwayCommand,
        [Parameter(Mandatory = $true)][string]$Value,
        [Parameter(Mandatory = $true)][string[]]$Arguments
    )

    $previousPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = "Continue"
        $Value | & $RailwayCommand @Arguments 2>$null | Out-Null
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousPreference
    }

    if ($exitCode -ne 0) {
        $safeArgs = ($Arguments | ForEach-Object {
            if ($_ -match 'TOKEN|KEY|SECRET') { '<redacted>' } else { $_ }
        }) -join ' '
        throw "Railway stdin write failed with exit code $exitCode`: $safeArgs"
    }
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

$railwayCommand = Resolve-RailwayNativeCommand
Write-SaraLog "Railway native entry point VERIFIED: $([System.IO.Path]::GetFileName($railwayCommand))"

if (-not (Test-Path "main.py")) {
    throw "Run this controller from the SARA-OMEGA repository root."
}
if (-not (Select-String -Path "main.py" -Pattern 'GPT_ACTION_TOKEN' -Quiet)) {
    throw "Local main.py does not contain the governed GPT_ACTION_TOKEN lane. Refusing to deploy stale source."
}
if (-not (Test-Path "tools/railway_finalize_windows.ps1")) {
    throw "tools/railway_finalize_windows.ps1 is missing. Refusing an unverified deployment path."
}

Write-SaraLog "Verifying authenticated Railway identity"
$whoami = Invoke-RailwayCapture -RailwayCommand $railwayCommand -Arguments @("whoami")
if ([string]::IsNullOrWhiteSpace($whoami)) {
    throw "Railway authentication is not active."
}
Write-SaraLog "Railway authentication VERIFIED"

$targetArgs = @("--project", $ProjectId, "--environment", $EnvironmentName, "--service", $ServiceName)
Write-SaraLog "Verifying canonical production identity before any write"
$domainJson = Invoke-RailwayCapture -RailwayCommand $railwayCommand -Arguments (@("domain", "list") + $targetArgs + @("--json"))
if ($domainJson -notmatch [regex]::Escape($ProductionDomain)) {
    throw "Project $ProjectId does not currently own $ProductionDomain for service $ServiceName. No Railway changes were made."
}
Write-SaraLog "Canonical production identity VERIFIED: project=$ProjectId service=$ServiceName domain=$ProductionDomain"

Write-SaraLog "Running non-interactive Railway command-contract preflight"
$kv = Invoke-RailwayCapture -RailwayCommand $railwayCommand -Arguments (@("variable", "list") + $targetArgs + @("--kv"))
$volumeArgs = @("volume", "--project", $ProjectId, "--environment", $EnvironmentName, "--service", $ServiceName)
$volumeJson = Invoke-RailwayCapture -RailwayCommand $railwayCommand -Arguments ($volumeArgs + @("list", "--json"))
Write-SaraLog "Non-interactive Railway command contract VERIFIED"

Write-SaraLog "Reading production variable inventory without printing secrets"
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
    Invoke-RailwayStdinWrite -RailwayCommand $railwayCommand -Value $gptActionToken -Arguments (@("variable", "set", "GPT_ACTION_TOKEN", "--stdin", "--skip-deploys") + $targetArgs)
    Write-SaraLog "Installed dedicated GPT Action token without printing it"
}
else {
    Write-SaraLog "Existing dedicated GPT Action token retained"
}

Write-SaraLog "Applying production fail-safe variables with literal Linux container paths"
Invoke-RailwayWrite -RailwayCommand $railwayCommand -Arguments (@(
    "variable", "set",
    "SARA_FAILSAFE_REQUIRED=true",
    "SARA_FAILSAFE_ROOT=/data/sara-failsafe",
    "SARA_FAILSAFE_REQUIRE_DEDICATED_MOUNT=true",
    "SARA_FAILSAFE_MIN_FREE_BYTES=67108864",
    "SARA_RELEASE_VERSION=3.2.1",
    "--skip-deploys"
) + $targetArgs)

Write-SaraLog "Verifying persistent /data volume"
if (-not (Test-DataVolume -JsonText $volumeJson)) {
    Invoke-RailwayWrite -RailwayCommand $railwayCommand -Arguments ($volumeArgs + @("add", "--mount-path", "/data", "--json"))
    Write-SaraLog "Created persistent /data volume"
}
else {
    Write-SaraLog "Persistent /data volume already present"
}

Write-SaraLog "Deploying governed SARA-OMEGA V3.2.1 source to canonical production"
Invoke-RailwayWrite -RailwayCommand $railwayCommand -Arguments @("up", "--project", $ProjectId, "--environment", $EnvironmentName, "--service", $ServiceName, "--ci")
Write-SaraLog "Railway deploy command completed successfully; transferring authority to live HTTPS acceptance"

& ".\tools\railway_finalize_windows.ps1" `
    -ProjectId $ProjectId `
    -ProductionDomain $ProductionDomain `
    -ServiceName $ServiceName `
    -EnvironmentName $EnvironmentName
if ($LASTEXITCODE -ne 0) {
    throw "Live production finalization failed."
}
