param(
  [string]$CampaignBranch = "completion/campaign-20260903-170559",
  [string]$ProductionUrl = "https://sara-omega-production.up.railway.app",
  [switch]$SkipLiveChecks
)

$ErrorActionPreference = "Stop"
$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptRoot
$scriptPath = Join-Path $repoRoot "SARA_OMEGA_Integrated_Completion_Campaign_RESUME.ps1"

if (-not (Test-Path -LiteralPath $scriptPath)) {
  throw "Root resume controller not found at $scriptPath"
}

& $scriptPath -CampaignBranch $CampaignBranch -ProductionUrl $ProductionUrl -SkipLiveChecks:$SkipLiveChecks
exit $LASTEXITCODE
