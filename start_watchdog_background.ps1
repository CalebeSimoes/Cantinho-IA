$ErrorActionPreference = "Stop"

$ProjectDir = $PSScriptRoot
$WatchdogScript = Join-Path $ProjectDir "watchdog_cantinho.ps1"
$LogsDir = Join-Path $ProjectDir "logs"
$WatchdogPidFile = Join-Path $LogsDir "watchdog.pid"
$PowerShellExe = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"

if (!(Test-Path $WatchdogScript)) {
    Write-Host "[ERRO] watchdog_cantinho.ps1 nao encontrado." -ForegroundColor Red
    exit 1
}

if (!(Test-Path $PowerShellExe)) {
    Write-Host "[ERRO] Windows PowerShell nao encontrado." -ForegroundColor Red
    exit 1
}

if (Test-Path $WatchdogPidFile) {
    try {
        $PidFileInfo = Get-Item -LiteralPath $WatchdogPidFile
        $SavedWatchdogPid = [int](
            Get-Content -LiteralPath $WatchdogPidFile |
            Select-Object -First 1
        )
        $SavedWatchdog = Get-Process `
            -Id $SavedWatchdogPid `
            -ErrorAction Stop
        $StartDifference = [Math]::Abs(
            ($SavedWatchdog.StartTime - $PidFileInfo.LastWriteTime).TotalSeconds
        )

        if (
            $SavedWatchdog.ProcessName -in @("powershell", "pwsh") -and
            $StartDifference -le 60
        ) {
            Write-Host "[OK] Watchdog ja esta rodando (PID $SavedWatchdogPid)." -ForegroundColor Green
            exit 0
        }
    }
    catch {
        # PID antigo: a busca por CommandLine e o mutex sao os fallbacks.
    }
}

$Existing = @(
    Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
    Where-Object {
        $_.CommandLine -like "*watchdog_cantinho.ps1*" -and
        $_.ProcessId -ne $PID
    }
)

if ($Existing.Count -gt 0) {
    Write-Host "[OK] Watchdog ja esta rodando." -ForegroundColor Green
    exit 0
}

if (!(Test-Path $LogsDir)) {
    New-Item -ItemType Directory -Path $LogsDir | Out-Null
}

$Arguments = (
    "-NoProfile -NonInteractive -WindowStyle Hidden " +
    "-ExecutionPolicy Bypass -File `"$WatchdogScript`""
)

Start-Process `
    -FilePath $PowerShellExe `
    -ArgumentList $Arguments `
    -WorkingDirectory $ProjectDir `
    -WindowStyle Hidden | Out-Null

Start-Sleep -Seconds 3

$StartedPid = Get-Content `
    -LiteralPath $WatchdogPidFile `
    -ErrorAction SilentlyContinue |
    Select-Object -First 1

if ($StartedPid -and (Get-Process -Id $StartedPid -ErrorAction SilentlyContinue)) {
    Write-Host "[OK] Watchdog iniciado em background (PID $StartedPid)." -ForegroundColor Green
    exit 0
}

Write-Host "[ERRO] Watchdog nao confirmou a inicializacao." -ForegroundColor Red
exit 1
