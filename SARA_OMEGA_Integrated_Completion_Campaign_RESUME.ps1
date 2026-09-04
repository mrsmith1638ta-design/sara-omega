param(
  [string]$CampaignBranch = "completion/campaign-20260903-170559",
  [string]$ProductionUrl = "https://sara-omega-production.up.railway.app",
  [switch]$SkipLiveChecks
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$campaignDir = Join-Path $repoRoot $CampaignBranch
$reportDir = Join-Path $campaignDir "resume-reports"
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$reportPath = Join-Path $reportDir "resume-$timestamp.json"

function Add-Step {
  param(
    [System.Collections.Generic.List[object]]$Steps,
    [string]$Name,
    [string]$Status,
    [object]$Detail = $null
  )
  $Steps.Add([pscustomobject]@{
    name = $Name
    status = $Status
    detail = $Detail
    time = (Get-Date).ToUniversalTime().ToString("o")
  }) | Out-Null
}

function Invoke-Checked {
  param(
    [string]$Name,
    [scriptblock]$Script,
    [System.Collections.Generic.List[object]]$Steps
  )
  try {
    $output = & $Script 2>&1
    Add-Step -Steps $Steps -Name $Name -Status "PASS" -Detail (($output | Out-String).Trim())
    return $true
  } catch {
    Add-Step -Steps $Steps -Name $Name -Status "BLOCKED" -Detail $_.Exception.Message
    return $false
  }
}

function Invoke-RoadPost {
  param([string]$ToolName)
  $uri = "$ProductionUrl/road/actions/$ToolName"
  Invoke-RestMethod -Method Post -Uri $uri -ContentType "application/json" -Body "{}" -TimeoutSec 30
}

New-Item -ItemType Directory -Force -Path $reportDir | Out-Null
$steps = [System.Collections.Generic.List[object]]::new()
$startedAt = (Get-Date).ToUniversalTime().ToString("o")

try {
  if (-not (Test-Path (Join-Path $repoRoot ".git"))) {
    throw "This script must run from the SARA OMEGA Git repository root."
  }

  Push-Location $repoRoot
  try {
    $currentBranch = (git branch --show-current).Trim()
    $headBefore = (git rev-parse HEAD).Trim()
    Add-Step -Steps $steps -Name "repo_identity" -Status "PASS" -Detail @{
      repo_root = $repoRoot
      branch = $currentBranch
      head = $headBefore
    }

    $branchExists = $false
    try {
      git rev-parse --verify "$CampaignBranch" *> $null
      $branchExists = $true
    } catch {
      $branchExists = $false
    }
    if (-not $branchExists) {
      throw "Campaign branch '$CampaignBranch' is not present locally."
    }

    if ($currentBranch -ne $CampaignBranch) {
      git switch $CampaignBranch | Out-Null
      Add-Step -Steps $steps -Name "campaign_branch_switch" -Status "PASS" -Detail "Switched from '$currentBranch' to '$CampaignBranch'."
    } else {
      Add-Step -Steps $steps -Name "campaign_branch_switch" -Status "PASS" -Detail "Already on '$CampaignBranch'."
    }

    Invoke-Checked -Name "python_compile" -Steps $steps -Script {
      python -m py_compile main.py road_engine.py sara_production_bootstrap.py
    } | Out-Null

    Invoke-Checked -Name "road_unit_tests" -Steps $steps -Script {
      python -m pytest tests/test_road_engine.py -q
    } | Out-Null

    if (-not $SkipLiveChecks) {
      Invoke-Checked -Name "live_health" -Steps $steps -Script {
        Invoke-RestMethod -Uri "$ProductionUrl/health" -TimeoutSec 30 | ConvertTo-Json -Depth 20
      } | Out-Null

      Invoke-Checked -Name "live_road_tools" -Steps $steps -Script {
        Invoke-RestMethod -Uri "$ProductionUrl/road/tools" -TimeoutSec 30 | ConvertTo-Json -Depth 20
      } | Out-Null

      Invoke-Checked -Name "live_get_completion_overview" -Steps $steps -Script {
        Invoke-RoadPost -ToolName "get_completion_overview" | ConvertTo-Json -Depth 30
      } | Out-Null

      Invoke-Checked -Name "live_get_production_acceptance" -Steps $steps -Script {
        Invoke-RoadPost -ToolName "get_production_acceptance" | ConvertTo-Json -Depth 30
      } | Out-Null
    } else {
      Add-Step -Steps $steps -Name "live_checks" -Status "UNVERIFIED" -Detail "Skipped by operator flag."
    }

    $headAfter = (git rev-parse HEAD).Trim()
    $blocked = @($steps | Where-Object { $_.status -eq "BLOCKED" }).Count
    $unverified = @($steps | Where-Object { $_.status -eq "UNVERIFIED" }).Count
    $campaignStatus = if ($blocked -gt 0) { "BLOCKED" } elseif ($unverified -gt 0) { "PARTIAL" } else { "PASS" }

    $report = [pscustomobject]@{
      campaign = "SARA OMEGA Integrated Completion Campaign"
      campaign_branch = $CampaignBranch
      campaign_status = $campaignStatus
      production_url = $ProductionUrl
      started_at = $startedAt
      completed_at = (Get-Date).ToUniversalTime().ToString("o")
      git_head_before = $headBefore
      git_head_after = $headAfter
      invariant = "Never manufacture PASS from missing, blocked, partial, unverified, stale, or user-asserted evidence."
      steps = $steps
    }
    $report | ConvertTo-Json -Depth 40 | Set-Content -LiteralPath $reportPath -Encoding UTF8
    Write-Host "SARA OMEGA resume complete: $campaignStatus"
    Write-Host "Report: $reportPath"
    if ($campaignStatus -ne "PASS") {
      exit 2
    }
  } finally {
    Pop-Location
  }
} catch {
  $steps = if ($steps) { $steps } else { [System.Collections.Generic.List[object]]::new() }
  Add-Step -Steps $steps -Name "resume_controller" -Status "BLOCKED" -Detail $_.Exception.Message
  $report = [pscustomobject]@{
    campaign = "SARA OMEGA Integrated Completion Campaign"
    campaign_branch = $CampaignBranch
    campaign_status = "BLOCKED"
    production_url = $ProductionUrl
    started_at = $startedAt
    completed_at = (Get-Date).ToUniversalTime().ToString("o")
    invariant = "Never manufacture PASS from missing, blocked, partial, unverified, stale, or user-asserted evidence."
    steps = $steps
  }
  $report | ConvertTo-Json -Depth 40 | Set-Content -LiteralPath $reportPath -Encoding UTF8
  Write-Host "SARA OMEGA resume blocked"
  Write-Host "Report: $reportPath"
  Write-Error $_
  exit 1
}
