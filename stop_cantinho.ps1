param([switch]$IncludeOllama)

$ErrorActionPreference = "Stop"

$ProjectDir = $PSScriptRoot
$LogsDir = Join-Path $ProjectDir "logs"
$RuntimeFiles = @(
    (Join-Path $LogsDir "worker.pid"),
    (Join-Path $LogsDir "watchdog.pid"),
    (Join-Path $LogsDir "worker-heartbeat.json")
)

$WatchdogPidFile = Join-Path $LogsDir "watchdog.pid"

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

if ($IncludeOllama) {
    Get-Process -Name "ollama" -ErrorAction SilentlyContinue |
        Stop-Process -Force -ErrorAction SilentlyContinue
}

Start-Sleep -Seconds 1

foreach ($RuntimeFile in $RuntimeFiles) {
    Remove-Item `
        -LiteralPath $RuntimeFile `
        -Force `
        -ErrorAction SilentlyContinue
}

Write-Host "[OK] Watchdog e Worker encerrados." -ForegroundColor Green
if (!$IncludeOllama) {
    Write-Host "O Ollama foi mantido ativo para nao afetar outros usos." -ForegroundColor DarkGray
}
