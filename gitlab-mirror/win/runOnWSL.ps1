$Distro = "archlinux"
$timeoutSeconds = 900
$pollIntervalSeconds = 5
$featuresToEnsure = @(
  "Microsoft-Windows-Subsystem-Linux",
  "VirtualMachinePlatform"
)

function Ensure-RunAsAdmin {
  $isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")
  if (-not $isAdmin) {
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = "powershell.exe"
    if ($PSCommandPath) {
      $psi.Arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`""
    } else {
      $psi.Arguments = "-NoProfile -ExecutionPolicy Bypass"
    }
    $psi.Verb = "runas"
    try { [System.Diagnostics.Process]::Start($psi) | Out-Null } catch { Write-Error "Failed to elevate: $_" }
    exit
  }
}

function Is-FeatureEnabled {
  param($featureName)
  try {
    $f = Get-WindowsOptionalFeature -Online -FeatureName $featureName -ErrorAction Stop
    return ($f.State -eq "Enabled")
  } catch {
    $out = & dism.exe /online /Get-FeatureInfo /FeatureName:$featureName 2>&1
    return ($out -match "State : Enabled")
  }
}

function Enable-FeatureIfNeeded {
  param($featureName)
  if (Is-FeatureEnabled -featureName $featureName) {
    Write-Host "Feature '$featureName' already enabled."
    return
  }
  try {
    Enable-WindowsOptionalFeature -Online -FeatureName $featureName -All -NoRestart -ErrorAction Stop
    if (Is-FeatureEnabled -featureName $featureName) {
      Write-Host "Feature '$featureName' enabled (PowerShell)."
      return
    }
  } catch {
    Write-Host "Falling back to DISM for feature: $featureName"
  }
  $args = "/online","/Enable-Feature","/FeatureName:$featureName","/All","/NoRestart"
  & dism.exe $args
  $ec = $LASTEXITCODE
  if ($ec -eq 0) {
    Write-Host "DISM enabled feature '$featureName' (no reboot required)."
  } elseif ($ec -eq 3010) {
    Write-Host "DISM enabled feature '$featureName' but a reboot is required."
    $script:needReboot = $true
  } else {
    Write-Warning "DISM returned exit code $ec while enabling '$featureName'."
  }
}

function Convert-WindowsPathToWsl {
  param($winPath)
  $full = (Resolve-Path -Path $winPath).ProviderPath
  $full = $full -replace '\\','/'
  if ($full.Length -ge 2 -and $full[1] -eq ':') {
    $drive = $full.Substring(0,1).ToLower()
    $rest  = $full.Substring(2)
    return "/mnt/$drive$rest"
  } else {
    throw "Cannot convert path to WSL format: $full"
  }
}

function Wait-ForDistro {
  param($distroName, $timeoutSec, $intervalSec)
  $deadline = (Get-Date).AddSeconds($timeoutSec)
  while ((Get-Date) -lt $deadline) {
    try { $list = & wsl -l -q 2>$null } catch { Start-Sleep -Seconds $intervalSec; continue }
    if ($null -ne $list) {
      foreach ($line in $list) {
        if ($line.Trim() -ieq $distroName) { return $true }
      }
    }
    Start-Sleep -Seconds $intervalSec
  }
  return $false
}

Ensure-RunAsAdmin

if (-not (Get-Command wsl -ErrorAction SilentlyContinue)) {
  Write-Error "wsl.exe is not available on PATH. Aborting."
  exit 1
}

$script:needReboot = $false
foreach ($f in $featuresToEnsure) { Enable-FeatureIfNeeded -featureName $f }

if ($script:needReboot) {
  Write-Host "A reboot is required to complete feature installation. The system will reboot now. Re-run this script after boot if necessary."
  Restart-Computer -Force
  exit
}

$wslInstalled = $false
try {
  $wslListOutput = & wsl -l -v 2>&1
  if ($LASTEXITCODE -eq 0) { $wslInstalled = $true }
} catch {
  $wslInstalled = $false
}

if (-not $wslInstalled) {
  Write-Host "Attempting: wsl --install archlinux"
  & wsl --install archlinux
} else {
  $exists = $false
  $list = & wsl -l -q
  foreach ($line in $list) { if ($line.Trim() -ieq $Distro) { $exists = $true } }
  if ($exists) {
    Write-Host "Distro '$Distro' already installed. Skipping install."
  } else {
    Write-Host "Installing distro via: wsl --install archlinux"
    & wsl --install archlinux
  }
}

Write-Host "Waiting up to $timeoutSeconds seconds for distro '$Distro' to show up..."
$ok = Wait-ForDistro -distroName $Distro -timeoutSec $timeoutSeconds -intervalSec $pollIntervalSeconds
if (-not $ok) {
  Write-Warning "Timed out waiting for distro '$Distro'. You may need to finish installation manually and re-run this script."
  exit 2
}
Write-Host "Distro '$Distro' detected."

if ($PSCommandPath) { $scriptDir = Split-Path -Parent $PSCommandPath } else { $scriptDir = (Get-Location).ProviderPath }
$parentDir = (Resolve-Path -Path (Join-Path $scriptDir "..")).ProviderPath
Write-Host "Parent directory: $parentDir"

$mkEdgeWinPath = Join-Path $parentDir "mkedgescript"
if (-not (Test-Path $mkEdgeWinPath)) {
  Write-Warning "mkedgescript not found at: $mkEdgeWinPath"
  exit 3
}

try { $wslParent = Convert-WindowsPathToWsl $parentDir } catch { Write-Error "Failed to convert Windows path to WSL path: $_"; exit 4 }
Write-Host "Converted parent path to WSL path: $wslParent"

$escapedWslPath = $wslParent -replace "'","'\"'\"'"
$wslCmd = "cd '$escapedWslPath' && chmod +x ./mkedgescript && ./mkedgescript"
Write-Host "Running mkedgescript inside WSL (distro: $Distro)..."
& wsl -d "$Distro" -- bash -lc "$wslCmd"

Write-Host "Done"
