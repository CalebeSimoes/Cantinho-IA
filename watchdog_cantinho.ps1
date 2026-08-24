param(
    [switch]$Once,
    [switch]$NoRepair
)

$ErrorActionPreference = "Stop"

$ProjectDir = $PSScriptRoot
$LogsDir = Join-Path $ProjectDir "logs"
$EnvFile = Join-Path $ProjectDir ".env"
$StartScript = Join-Path $ProjectDir "start_cantinho_background.ps1"
$WorkerPidFile = Join-Path $LogsDir "worker.pid"
$HeartbeatFile = Join-Path $LogsDir "worker-heartbeat.json"
$WatchdogPidFile = Join-Path $LogsDir "watchdog.pid"
$StateFile = Join-Path $LogsDir "watchdog-state.json"
$WatchdogLog = Join-Path $LogsDir "watchdog.log"
$PowerShellExe = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"

if (!(Test-Path $LogsDir)) {
    New-Item -ItemType Directory -Path $LogsDir | Out-Null
}

function Write-WatchdogLog {
    param([Parameter(Mandatory = $true)][string]$Message)

    Add-Content `
        -LiteralPath $WatchdogLog `
        -Value "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') - $Message" `
        -Encoding utf8
}

function Get-CantinhoIntSetting {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][int]$Default,
        [Parameter(Mandatory = $true)][int]$Minimum
    )

    $RawValue = [Environment]::GetEnvironmentVariable($Name)

    if (!$RawValue -and (Test-Path $EnvFile)) {
        $EscapedName = [regex]::Escape($Name)
        $Line = Get-Content -LiteralPath $EnvFile |
            Where-Object { $_ -match "^\s*$EscapedName\s*=" } |
            Select-Object -Last 1

        if ($Line) {
            $RawValue = ($Line -split "=", 2)[1].Trim()
        }
    }

    $ParsedValue = 0
    if (
        $RawValue -and
        [int]::TryParse($RawValue, [ref]$ParsedValue) -and
        $ParsedValue -ge $Minimum
    ) {
        return $ParsedValue
    }

    return $Default
}

$CheckSeconds = Get-CantinhoIntSetting `
    -Name "WATCHDOG_CHECK_SECONDS" `
    -Default 15 `
    -Minimum 5
$WorkerStaleSeconds = Get-CantinhoIntSetting `
    -Name "WATCHDOG_WORKER_STALE_SECONDS" `
    -Default 90 `
    -Minimum 30
$MaxRecoveries = Get-CantinhoIntSetting `
    -Name "WATCHDOG_MAX_RECOVERIES" `
    -Default 5 `
    -Minimum 1
$RecoveryWindowSeconds = Get-CantinhoIntSetting `
    -Name "WATCHDOG_RECOVERY_WINDOW_SECONDS" `
    -Default 600 `
    -Minimum 60
$CooldownSeconds = Get-CantinhoIntSetting `
    -Name "WATCHDOG_COOLDOWN_SECONDS" `
    -Default 300 `
    -Minimum 60

function Test-OllamaHealth {
    try {
        $null = Invoke-RestMethod `
            -Uri "http://127.0.0.1:11434/api/tags" `
            -TimeoutSec 3
        return $true
    }
    catch {
        return $false
    }
}

function Get-LogicalWorkers {
    $Workers = @(
        Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -like "*-m app.worker*" }
    )

    if ($Workers.Count -eq 0) {
        return @()
    }

    $WorkerIds = @($Workers | ForEach-Object { [int]$_.ProcessId })
    $Roots = @(
        $Workers |
        Where-Object {
            $WorkerIds -notcontains [int]$_.ParentProcessId
        }
    )

    if ($Roots.Count -eq 0) {
        return @($Workers[0])
    }

    return $Roots
}

function Get-WorkerHealth {
    param([Parameter(Mandatory = $true)][DateTimeOffset]$Now)

    $Workers = @(Get-LogicalWorkers)
    $ProcessRunning = $Workers.Count -gt 0
    $HeartbeatState = "missing"
    $HeartbeatAgeSeconds = $null
    $HeartbeatFresh = $false

    if (Test-Path $HeartbeatFile) {
        try {
            $Heartbeat = Get-Content -Raw -LiteralPath $HeartbeatFile |
                ConvertFrom-Json
            $HeartbeatState = [string]$Heartbeat.state
            $HeartbeatAt = [DateTimeOffset]::Parse(
                [string]$Heartbeat.timestamp,
                [Globalization.CultureInfo]::InvariantCulture
            )
            $HeartbeatAgeSeconds = [Math]::Max(
                0,
                [Math]::Round(
                    ($Now.ToUniversalTime() - $HeartbeatAt.ToUniversalTime()).TotalSeconds,
                    1
                )
            )
            $HeartbeatFresh = (
                $HeartbeatAgeSeconds -le $WorkerStaleSeconds -and
                $HeartbeatState -ne "stopped"
            )
        }
        catch {
            $HeartbeatState = "invalid"
            $HeartbeatFresh = $false
        }
    }

    # Um Worker acabou de subir e pode ainda nao ter publicado o primeiro
    # heartbeat. Damos a ele a mesma janela usada para detectar travamento.
    if ($ProcessRunning -and !$HeartbeatFresh -and $HeartbeatState -eq "missing") {
        try {
            $YoungestAge = @(
                $Workers |
                ForEach-Object {
                    ([DateTime]::Now - [DateTime]$_.CreationDate).TotalSeconds
                }
            ) | Measure-Object -Minimum

            if ($YoungestAge.Minimum -le $WorkerStaleSeconds) {
                $HeartbeatState = "starting"
                $HeartbeatFresh = $true
            }
        }
        catch {
            $HeartbeatFresh = $false
        }
    }

    return [pscustomobject]@{
        Healthy = ($ProcessRunning -and $HeartbeatFresh)
        ProcessRunning = $ProcessRunning
        ProcessCount = $Workers.Count
        RootPids = @($Workers | ForEach-Object { [int]$_.ProcessId })
        HeartbeatFresh = $HeartbeatFresh
        HeartbeatState = $HeartbeatState
        HeartbeatAgeSeconds = $HeartbeatAgeSeconds
    }
}

function Stop-CantinhoWorkers {
    $Workers = @(
        Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -like "*-m app.worker*" }
    )

    foreach ($Worker in $Workers) {
        Stop-Process `
            -Id $Worker.ProcessId `
            -Force `
            -ErrorAction SilentlyContinue
    }

    Start-Sleep -Seconds 1
    Remove-Item -LiteralPath $WorkerPidFile -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $HeartbeatFile -Force -ErrorAction SilentlyContinue
}

$script:RecoveryHistory = @()
$script:CooldownUntil = $null

function Restore-RecoveryState {
    if (!(Test-Path $StateFile)) {
        return
    }

    try {
        $Previous = Get-Content -Raw -LiteralPath $StateFile |
            ConvertFrom-Json
        $Cutoff = [DateTimeOffset]::UtcNow.AddSeconds(-$RecoveryWindowSeconds)

        $script:RecoveryHistory = @(
            $Previous.recovery_history |
            ForEach-Object { [DateTimeOffset]::Parse([string]$_) } |
            Where-Object { $_ -ge $Cutoff }
        )

        if ($Previous.cooldown_until) {
            $script:CooldownUntil = [DateTimeOffset]::Parse(
                [string]$Previous.cooldown_until
            )
        }
    }
    catch {
        $script:RecoveryHistory = @()
        $script:CooldownUntil = $null
    }
}

function Test-RecoveryAllowed {
    param([Parameter(Mandatory = $true)][DateTimeOffset]$Now)

    if ($script:CooldownUntil) {
        if ($Now -lt $script:CooldownUntil) {
            return $false
        }

        # O cooldown cumprido abre uma nova janela de tentativas.
        $script:CooldownUntil = $null
        $script:RecoveryHistory = @()
    }

    $Cutoff = $Now.AddSeconds(-$RecoveryWindowSeconds)
    $script:RecoveryHistory = @(
        $script:RecoveryHistory |
        Where-Object { $_ -ge $Cutoff }
    )

    if ($script:RecoveryHistory.Count -ge $MaxRecoveries) {
        $script:CooldownUntil = $Now.AddSeconds($CooldownSeconds)
        Write-WatchdogLog (
            "LIMITE: $MaxRecoveries recuperacoes em " +
            "$RecoveryWindowSeconds s. Pausa ate " +
            "$($script:CooldownUntil.ToString('o'))."
        )
        return $false
    }

    return $true
}

function Invoke-CantinhoRecovery {
    param(
        [Parameter(Mandatory = $true)][string]$Reason,
        [Parameter(Mandatory = $true)][DateTimeOffset]$Now
    )

    if (!(Test-Path $StartScript)) {
        throw "Script de inicializacao nao encontrado: $StartScript"
    }

    if (!(Test-Path $PowerShellExe)) {
        throw "Windows PowerShell nao encontrado: $PowerShellExe"
    }

    if ($Reason -eq "worker_stale") {
        Write-WatchdogLog "Worker sem heartbeat recente. Encerrando instancia travada."
        Stop-CantinhoWorkers
    }

    Write-WatchdogLog "Recuperacao iniciada. Motivo: $Reason."
    $Arguments = (
        "-NoProfile -NonInteractive -WindowStyle Hidden " +
        "-ExecutionPolicy Bypass -File `"$StartScript`""
    )
    # Start-Process -Wait, no Windows, pode aguardar tambem toda a arvore de
    # processos. Como o script auxiliar cria o Worker permanente, isso faria
    # o Watchdog ficar bloqueado para sempre. Process.WaitForExit acompanha
    # somente o PowerShell auxiliar e possui um timeout defensivo.
    $RecoveryInfo = New-Object System.Diagnostics.ProcessStartInfo
    $RecoveryInfo.FileName = $PowerShellExe
    $RecoveryInfo.Arguments = $Arguments
    $RecoveryInfo.WorkingDirectory = $ProjectDir
    $RecoveryInfo.UseShellExecute = $false
    $RecoveryInfo.CreateNoWindow = $true
    $RecoveryInfo.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Hidden

    $Recovery = [System.Diagnostics.Process]::Start($RecoveryInfo)
    if (!$Recovery.WaitForExit(60000)) {
        try {
            $Recovery.Kill()
        }
        catch {
            # A falha ao encerrar o auxiliar nao deve ocultar o timeout real.
        }
        finally {
            $Recovery.Dispose()
        }

        throw "Timeout de 60s no script de recuperacao."
    }

    $RecoveryExitCode = $Recovery.ExitCode
    $Recovery.Dispose()

    $script:RecoveryHistory = @($script:RecoveryHistory) + @($Now)
    Write-WatchdogLog (
        "Recuperacao concluida com codigo $RecoveryExitCode. " +
        "Motivo: $Reason."
    )
    return $RecoveryExitCode
}

function Save-WatchdogState {
    param(
        [Parameter(Mandatory = $true)][DateTimeOffset]$Now,
        [Parameter(Mandatory = $true)][bool]$OllamaHealthy,
        [Parameter(Mandatory = $true)]$WorkerHealth,
        [Parameter(Mandatory = $true)][string]$Action
    )

    $Payload = [ordered]@{
        version = 1
        pid = $PID
        checked_at = $Now.ToUniversalTime().ToString("o")
        ollama = [ordered]@{
            healthy = $OllamaHealthy
        }
        worker = [ordered]@{
            healthy = [bool]$WorkerHealth.Healthy
            process_running = [bool]$WorkerHealth.ProcessRunning
            process_count = [int]$WorkerHealth.ProcessCount
            root_pids = @($WorkerHealth.RootPids)
            heartbeat_fresh = [bool]$WorkerHealth.HeartbeatFresh
            heartbeat_state = [string]$WorkerHealth.HeartbeatState
            heartbeat_age_seconds = $WorkerHealth.HeartbeatAgeSeconds
        }
        action = $Action
        recovery_history = @(
            $script:RecoveryHistory |
            ForEach-Object { $_.ToUniversalTime().ToString("o") }
        )
        cooldown_until = if ($script:CooldownUntil) {
            $script:CooldownUntil.ToUniversalTime().ToString("o")
        }
        else {
            $null
        }
        config = [ordered]@{
            check_seconds = $CheckSeconds
            worker_stale_seconds = $WorkerStaleSeconds
            max_recoveries = $MaxRecoveries
            recovery_window_seconds = $RecoveryWindowSeconds
            cooldown_seconds = $CooldownSeconds
        }
    }

    $TemporaryState = "$StateFile.$PID.tmp"
    $Payload |
        ConvertTo-Json -Depth 6 |
        Set-Content -LiteralPath $TemporaryState -Encoding utf8
    Move-Item `
        -LiteralPath $TemporaryState `
        -Destination $StateFile `
        -Force
}

$CreatedNew = $false
$WatchdogMutex = [System.Threading.Mutex]::new(
    $true,
    "Local\CantinhoGhibliWatchdog",
    [ref]$CreatedNew
)

if (!$CreatedNew) {
    Write-WatchdogLog "Outra instancia do Watchdog ja esta ativa. Saindo."
    $WatchdogMutex.Dispose()
    exit 0
}

Set-Content -LiteralPath $WatchdogPidFile -Value $PID -Encoding ascii
Restore-RecoveryState
Write-WatchdogLog (
    "Watchdog iniciado (PID $PID, intervalo ${CheckSeconds}s, " +
    "heartbeat maximo ${WorkerStaleSeconds}s)."
)

try {
    while ($true) {
        $Now = [DateTimeOffset]::UtcNow
        $OllamaHealthy = Test-OllamaHealth
        $WorkerHealth = Get-WorkerHealth -Now $Now
        $Action = "none"

        $RecoveryReason = $null
        if (!$WorkerHealth.Healthy) {
            $RecoveryReason = if ($WorkerHealth.ProcessRunning) {
                "worker_stale"
            }
            else {
                "worker_missing"
            }
        }
        elseif (!$OllamaHealthy) {
            $RecoveryReason = "ollama_offline"
        }

        if ($RecoveryReason -and !$NoRepair) {
            if (Test-RecoveryAllowed -Now $Now) {
                try {
                    $Code = Invoke-CantinhoRecovery `
                        -Reason $RecoveryReason `
                        -Now $Now
                    $Action = "recovery:${RecoveryReason}:exit_$Code"
                }
                catch {
                    $script:RecoveryHistory = @($script:RecoveryHistory) + @($Now)
                    $Action = "recovery_failed:$RecoveryReason"
                    Write-WatchdogLog (
                        "ERRO na recuperacao ($RecoveryReason): " +
                        "$($_.Exception.GetType().Name)."
                    )
                }

                Start-Sleep -Seconds 3
                $Now = [DateTimeOffset]::UtcNow
                $OllamaHealthy = Test-OllamaHealth
                $WorkerHealth = Get-WorkerHealth -Now $Now
            }
            else {
                $Action = "cooldown:$RecoveryReason"
            }
        }
        elseif ($RecoveryReason -and $NoRepair) {
            $Action = "repair_disabled:$RecoveryReason"
        }

        Save-WatchdogState `
            -Now $Now `
            -OllamaHealthy $OllamaHealthy `
            -WorkerHealth $WorkerHealth `
            -Action $Action

        if ($Once) {
            break
        }

        Start-Sleep -Seconds $CheckSeconds
    }
}
finally {
    Write-WatchdogLog "Watchdog encerrado (PID $PID)."
    $SavedPid = Get-Content `
        -LiteralPath $WatchdogPidFile `
        -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ([string]$SavedPid -eq [string]$PID) {
        Remove-Item `
            -LiteralPath $WatchdogPidFile `
            -Force `
            -ErrorAction SilentlyContinue
    }

    $WatchdogMutex.ReleaseMutex()
    $WatchdogMutex.Dispose()
}
