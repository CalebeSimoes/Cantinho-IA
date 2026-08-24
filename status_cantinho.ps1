$ErrorActionPreference = "SilentlyContinue"

$ProjectDir = $PSScriptRoot
$TaskName = "Cantinho Ghibli AI"
$ExpectedModel = "qwen3:4b"

$LogsDir = Join-Path $ProjectDir "logs"
$StartupLog = Join-Path $LogsDir "startup.log"
$WorkerErr = Join-Path $LogsDir "worker-error.log"
$WatchdogLog = Join-Path $LogsDir "watchdog.log"
$WatchdogStateFile = Join-Path $LogsDir "watchdog-state.json"
$WatchdogPidFile = Join-Path $LogsDir "watchdog.pid"
$HeartbeatFile = Join-Path $LogsDir "worker-heartbeat.json"
$EnvFile = Join-Path $ProjectDir ".env"
$Python = Join-Path $ProjectDir ".venv\Scripts\python.exe"

$Ok = 0
$Warn = 0
$Fail = 0

function Write-Ok {
    param([string]$Message)
    Write-Host "[OK]   $Message" -ForegroundColor Green
    $script:Ok++
}

function Write-Warn {
    param([string]$Message)
    Write-Host "[AVISO] $Message" -ForegroundColor Yellow
    $script:Warn++
}

function Write-Fail {
    param([string]$Message)
    Write-Host "[ERRO] $Message" -ForegroundColor Red
    $script:Fail++
}

Write-Host ""
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host "        STATUS - CANTINHO GHIBLI AI" -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host ""

# ----------------------------------------------------------
# Projeto / ambiente
# ----------------------------------------------------------

Write-Host "Projeto" -ForegroundColor White

if (Test-Path $EnvFile) {
    Write-Ok ".env encontrado"
}
else {
    Write-Fail ".env nao encontrado"
}

if (Test-Path $Python) {
    Write-Ok "Python da .venv encontrado"
}
else {
    Write-Fail "Python da .venv nao encontrado"
}

Write-Host ""

# ----------------------------------------------------------
# Ollama
# ----------------------------------------------------------

Write-Host "Ollama" -ForegroundColor White

$OllamaOnline = $false
$Tags = $null

try {
    $Tags = Invoke-RestMethod `
        -Uri "http://127.0.0.1:11434/api/tags" `
        -TimeoutSec 3

    $OllamaOnline = $true
    Write-Ok "Ollama online em 127.0.0.1:11434"
}
catch {
    Write-Fail "Ollama offline"
}

if ($OllamaOnline) {
    $ModelNames = @()

    if ($Tags.models) {
        $ModelNames = @($Tags.models | ForEach-Object { $_.name })
    }

    if ($ModelNames -contains $ExpectedModel) {
        Write-Ok "Modelo $ExpectedModel instalado"
    }
    else {
        Write-Warn "Modelo $ExpectedModel nao apareceu em /api/tags"

        if ($ModelNames.Count -gt 0) {
            Write-Host "       Modelos encontrados: $($ModelNames -join ', ')" -ForegroundColor DarkGray
        }
    }
}

Write-Host ""

# ----------------------------------------------------------
# Worker
# ----------------------------------------------------------

Write-Host "Worker" -ForegroundColor White

$Workers = @(
    Get-CimInstance Win32_Process |
    Where-Object {
        $_.CommandLine -like "*-m app.worker*"
    }
)

if ($Workers.Count -gt 0) {
    $WorkerIds = @($Workers | ForEach-Object { [int]$_.ProcessId })

    # A .venv no Windows pode aparecer como wrapper Python + processo filho.
    # Contamos apenas as raizes logicas para nao gerar falso aviso.
    $LogicalWorkers = @(
        $Workers |
        Where-Object {
            $WorkerIds -notcontains [int]$_.ParentProcessId
        }
    )

    if ($LogicalWorkers.Count -eq 0) {
        $LogicalWorkers = @($Workers[0])
    }

    Write-Ok "Worker rodando ($($LogicalWorkers.Count) instancia logica)"

    foreach ($Root in $LogicalWorkers) {
        Write-Host "       PID raiz: $($Root.ProcessId)" -ForegroundColor DarkGray
    }

    if ($LogicalWorkers.Count -gt 1) {
        Write-Warn "Mais de um Worker LOGICO foi encontrado ($($LogicalWorkers.Count))"
    }

    $WorkerPidFile = Join-Path $LogsDir "worker.pid"
    if (Test-Path $WorkerPidFile) {
        $SavedPid = Get-Content $WorkerPidFile -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($SavedPid) {
            Write-Host "       PID lock: $SavedPid" -ForegroundColor DarkGray
        }
    }
}
else {
    Write-Fail "Worker nao esta rodando"
}

Write-Host ""

# ----------------------------------------------------------
# Watchdog / heartbeat
# ----------------------------------------------------------

Write-Host "Watchdog" -ForegroundColor White
$HeartbeatLimitSeconds = 90

$Watchdogs = @(
    Get-CimInstance Win32_Process |
    Where-Object {
        $_.CommandLine -like "*watchdog_cantinho.ps1*" -and
        $_.ProcessId -ne $PID
    }
)

if ($Watchdogs.Count -eq 1) {
    Write-Ok "Watchdog rodando"
    Write-Host "       PID: $($Watchdogs[0].ProcessId)" -ForegroundColor DarkGray
}
elseif ($Watchdogs.Count -gt 1) {
    Write-Fail "Mais de um Watchdog foi encontrado ($($Watchdogs.Count))"
}
else {
    Write-Fail "Watchdog nao esta rodando"
}

if (Test-Path $WatchdogPidFile) {
    $WatchdogSavedPid = Get-Content `
        -LiteralPath $WatchdogPidFile `
        -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($WatchdogSavedPid) {
        Write-Host "       PID lock: $WatchdogSavedPid" -ForegroundColor DarkGray
    }
}

if (Test-Path $WatchdogStateFile) {
    try {
        $WatchdogState = Get-Content -Raw -LiteralPath $WatchdogStateFile |
            ConvertFrom-Json
        $StateAt = [DateTimeOffset]::Parse([string]$WatchdogState.checked_at)
        $StateAge = [Math]::Round(
            ([DateTimeOffset]::UtcNow - $StateAt.ToUniversalTime()).TotalSeconds,
            1
        )
        $ExpectedStateAge = [Math]::Max(
            60,
            ([int]$WatchdogState.config.check_seconds * 3)
        )
        if ([int]$WatchdogState.config.worker_stale_seconds -gt 0) {
            $HeartbeatLimitSeconds = [int]$WatchdogState.config.worker_stale_seconds
        }

        if ($StateAge -le $ExpectedStateAge) {
            Write-Ok "Estado do Watchdog atualizado ha ${StateAge}s"
        }
        else {
            Write-Fail "Estado do Watchdog esta desatualizado (${StateAge}s)"
        }

        Write-Host "       Ultima acao: $($WatchdogState.action)" -ForegroundColor DarkGray

        if ($WatchdogState.cooldown_until) {
            Write-Warn "Watchdog esta em cooldown de recuperacao"
            Write-Host "       Ate: $($WatchdogState.cooldown_until)" -ForegroundColor DarkGray
        }

        if ($WatchdogState.worker.heartbeat_state -eq "degraded") {
            Write-Warn "Worker vivo, mas o ultimo ciclo ficou degradado"
        }

        if (!$WatchdogState.worker.healthy) {
            Write-Fail "Watchdog considera o Worker indisponivel"
        }
    }
    catch {
        Write-Fail "watchdog-state.json nao pode ser lido"
    }
}
else {
    Write-Warn "Watchdog ainda nao publicou o arquivo de estado"
}

if (Test-Path $HeartbeatFile) {
    try {
        $Heartbeat = Get-Content -Raw -LiteralPath $HeartbeatFile |
            ConvertFrom-Json
        $HeartbeatAt = [DateTimeOffset]::Parse([string]$Heartbeat.timestamp)
        $HeartbeatAge = [Math]::Round(
            ([DateTimeOffset]::UtcNow - $HeartbeatAt.ToUniversalTime()).TotalSeconds,
            1
        )

        if ($Heartbeat.state -eq "stopped") {
            Write-Fail "Worker publicou estado stopped"
        }
        elseif ($HeartbeatAge -gt $HeartbeatLimitSeconds) {
            Write-Fail "Heartbeat do Worker esta atrasado (${HeartbeatAge}s)"
        }
        else {
            Write-Ok "Heartbeat do Worker: $($Heartbeat.state) (${HeartbeatAge}s)"
        }
    }
    catch {
        Write-Fail "worker-heartbeat.json nao pode ser lido"
    }
}
else {
    Write-Warn "Worker ainda nao publicou heartbeat"
}

Write-Host ""

# ----------------------------------------------------------
# Agendador de Tarefas
# ----------------------------------------------------------

Write-Host "Inicializacao automatica" -ForegroundColor White

$Task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue

if ($Task) {
    Write-Ok "Tarefa '$TaskName' existe"

    if ($Task.State -eq "Disabled") {
        Write-Fail "Tarefa esta desabilitada"
    }
    else {
        Write-Ok "Tarefa habilitada"
    }

    $TaskInfo = Get-ScheduledTaskInfo -TaskName $TaskName -ErrorAction SilentlyContinue

    if ($TaskInfo) {
        if ($TaskInfo.LastRunTime -and $TaskInfo.LastRunTime.Year -gt 2000) {
            Write-Host "       Ultima execucao: $($TaskInfo.LastRunTime)" -ForegroundColor DarkGray
        }

        Write-Host "       Ultimo resultado: $($TaskInfo.LastTaskResult)" -ForegroundColor DarkGray
    }
}
else {
    Write-Fail "Tarefa '$TaskName' nao encontrada"
}

Write-Host ""

# ----------------------------------------------------------
# Logs
# ----------------------------------------------------------

Write-Host "Logs" -ForegroundColor White

if (Test-Path $StartupLog) {
    $LastStartup = Get-Content $StartupLog -Tail 1 -ErrorAction SilentlyContinue

    if ($LastStartup) {
        Write-Ok "startup.log disponivel"
        Write-Host "       $LastStartup" -ForegroundColor DarkGray
    }
    else {
        Write-Warn "startup.log esta vazio"
    }
}
else {
    Write-Warn "startup.log ainda nao existe"
}

if (Test-Path $WorkerErr) {
    $ErrorInfo = Get-Item $WorkerErr

    if ($ErrorInfo.Length -eq 0) {
        Write-Ok "worker-error.log vazio"
    }
    else {
        Write-Warn "worker-error.log contem registros antigos ou atuais"
        Write-Host "       Use: Get-Content .\logs\worker-error.log -Tail 20" -ForegroundColor DarkGray
    }
}
else {
    Write-Ok "Nenhum worker-error.log encontrado"
}

if (Test-Path $WatchdogLog) {
    $LastWatchdog = Get-Content $WatchdogLog -Tail 1 -ErrorAction SilentlyContinue
    if ($LastWatchdog) {
        Write-Ok "watchdog.log disponivel"
        Write-Host "       $LastWatchdog" -ForegroundColor DarkGray
    }
}
else {
    Write-Warn "watchdog.log ainda nao existe"
}

Write-Host ""
Write-Host "==============================================" -ForegroundColor Cyan

if ($Fail -eq 0) {
    Write-Host " CANTINHO OPERACIONAL" -ForegroundColor Green
}
else {
    Write-Host " CANTINHO PRECISA DE ATENCAO" -ForegroundColor Red
}

Write-Host " OK: $Ok | Avisos: $Warn | Erros: $Fail"
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host ""

if ($Fail -gt 0) {
    exit 1
}

exit 0
