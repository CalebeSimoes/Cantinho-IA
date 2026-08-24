$ErrorActionPreference = "Stop"

$ProjectDir = $PSScriptRoot
$StartWatchdog = Join-Path $ProjectDir "start_watchdog_background.ps1"
$LogsDir = Join-Path $ProjectDir "logs"
$WorkerPidFile = Join-Path $LogsDir "worker.pid"
$WatchdogPidFile = Join-Path $LogsDir "watchdog.pid"
$HeartbeatFile = Join-Path $LogsDir "worker-heartbeat.json"

Write-Host "Parando Watchdog e Worker atuais..." -ForegroundColor Yellow

function Stop-WatchdogFromPidFile {
    if (!(Test-Path $WatchdogPidFile)) {
        return
    }

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
            Stop-Process `
                -Id $SavedWatchdogPid `
                -Force `
                -ErrorAction SilentlyContinue
        }
    }
    catch {
        # PID antigo ou inacessivel: a busca por CommandLine abaixo continua.
    }
}

Stop-WatchdogFromPidFile

$CantinhoProcesses = @(
    Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
    Where-Object {
        $_.CommandLine -like "*-m app.worker*" -or
        (
            $_.CommandLine -like "*watchdog_cantinho.ps1*" -and
            $_.ProcessId -ne $PID
        )
    }
)

foreach ($Process in $CantinhoProcesses) {
    Stop-Process `
        -Id $Process.ProcessId `
        -Force `
        -ErrorAction SilentlyContinue
}

Start-Sleep -Seconds 1

foreach ($RuntimeFile in @($WorkerPidFile, $WatchdogPidFile, $HeartbeatFile)) {
    Remove-Item `
        -LiteralPath $RuntimeFile `
        -Force `
        -ErrorAction SilentlyContinue
}

if (!(Test-Path $StartWatchdog)) {
    Write-Host "[ERRO] start_watchdog_background.ps1 nao encontrado." -ForegroundColor Red
    exit 1
}

Write-Host "Iniciando Cantinho novamente..." -ForegroundColor Cyan
& $StartWatchdog

if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERRO] O Watchdog nao reiniciou." -ForegroundColor Red
    exit 1
}

Start-Sleep -Seconds 3

Write-Host ""
Write-Host "Reinicio solicitado. Confira com:" -ForegroundColor Green
Write-Host ".\status_cantinho.ps1"
