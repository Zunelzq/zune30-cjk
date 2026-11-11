# Write a firmware image to the Zune 30 system partition (the 150 MB TFAT volume).
#
# ZIF->USB adapters drop connections mid-write; this script waits for the volume,
# retries, and verifies hashes. It also restores the standard files if the device
# formatted the partition after a failed boot.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File write_device.ps1 -Image .\nk.CJK.bin
#   powershell -ExecutionPolicy Bypass -File write_device.ps1 -Image .\nk.CJK.bin -RestoreStandardFiles
#
# WARNING: before writing, make sure F:\EBoot.bin is the 1.0 TEST bootloader
#          (sha256 prefix 11D94DE4). If it is a retail EBoot the device will flash
#          it into NOR and you lose the ability to boot modified images.

param(
    [Parameter(Mandatory = $true)][string]$Image,
    [string]$Volume = 'F:',
    [string]$BackupDir = "$PSScriptRoot\..\backup",
    # optional: folder containing the 1.0 TEST EBoot.bin / recovery.bin / config files
    [string]$StandardFiles,
    [switch]$RestoreStandardFiles
)

$ErrorActionPreference = 'SilentlyContinue'
$EXPECTED_EBoot = '11D94DE4'

function Wait-Volume([int]$tries = 40) {
    for ($i = 0; $i -lt $tries; $i++) {
        Update-HostStorageCache 2>&1 | Out-Null
        if (Test-Path "$Volume\") { return $true }
        Start-Sleep -Seconds 2
    }
    return $false
}

if (-not (Test-Path $Image)) { Write-Host "image not found: $Image" -ForegroundColor Red; exit 2 }
$srcHash = (Get-FileHash $Image -Algorithm SHA256).Hash

Write-Host "waiting for $Volume ..." -ForegroundColor Yellow
if (-not (Wait-Volume)) { Write-Host "volume $Volume never appeared" -ForegroundColor Red; exit 2 }

# 1) sanity: bootloader on disk
if (Test-Path "$Volume\EBoot.bin") {
    $eboot = (Get-FileHash "$Volume\EBoot.bin" -Algorithm SHA256).Hash.Substring(0, 16)
    if ($eboot -ne $EXPECTED_EBoot) {
        Write-Host "WARNING: $Volume\EBoot.bin is $eboot, not the 1.0 TEST loader ($EXPECTED_EBoot)." -ForegroundColor Red
        Write-Host "         Booting with a retail EBoot will overwrite NOR and lock the device." -ForegroundColor Red
    } else {
        Write-Host "bootloader on disk: $eboot (TEST loader, good)" -ForegroundColor Green
    }
}

# 2) back up the current nk.bin
New-Item -ItemType Directory -Force $BackupDir | Out-Null
if (Test-Path "$Volume\nk.bin") {
    $stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
    Copy-Item "$Volume\nk.bin" "$BackupDir\nk_$stamp.bin" -Force
    Write-Host "backed up current nk.bin -> $BackupDir\nk_$stamp.bin"
}

# 3) write with retries
$ok = $false
for ($try = 1; $try -le 5 -and -not $ok; $try++) {
    if (-not (Test-Path "$Volume\")) { Wait-Volume 10 | Out-Null }
    Copy-Item $Image "$Volume\nk.bin" -Force
    Start-Sleep -Milliseconds 400
    if ((Test-Path "$Volume\nk.bin") -and
        ((Get-FileHash "$Volume\nk.bin" -Algorithm SHA256).Hash -eq $srcHash)) { $ok = $true }
    else { Write-Host "retry $try/5" -ForegroundColor Yellow; Start-Sleep -Seconds 1 }
}
if (-not $ok) { Write-Host "write failed - re-seat the adapter and try again" -ForegroundColor Red; exit 3 }
Write-Host ("  OK  {0}\nk.bin  {1}" -f $Volume, $srcHash.Substring(0, 16)) -ForegroundColor Green

# 4) optionally restore the standard files (the device formats the partition when boot fails)
if ($RestoreStandardFiles -and $StandardFiles -and (Test-Path $StandardFiles)) {
    foreach ($name in @('EBoot.bin', 'recovery.bin', 'zconfig.dat', 'pmcver.dat', 'pmcstore.edb')) {
        $src = Join-Path $StandardFiles $name
        if (Test-Path $src) { Copy-Item $src "$Volume\$name" -Force; Write-Host "  restored $name" }
    }
}

Write-Host ""
Write-Host "done - eject safely, reinstall the drive, boot" -ForegroundColor Cyan
Get-ChildItem "$Volume\" -Force | Select-Object Name, @{n = 'KB'; e = { [math]::Round($_.Length / 1KB, 1) } } | Format-Table -AutoSize
