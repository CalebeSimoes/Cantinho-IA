$ErrorActionPreference = "SilentlyContinue"

$ProjectDir = $PSScriptRoot
$TaskName = "Cantinho Ghibli AI"
$ExpectedModel = "qwen3:4b"

$LogsDir = Join-Path $ProjectDir "logs"
$StartupLog = Join-Path $LogsDir "startup.log"
$WorkerErr = Join-Path $LogsDir "worker-error.log"
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
    Write-Ok "Worker rodando"

    foreach ($Worker in $Workers) {
        Write-Host "       PID: $($Worker.ProcessId)" -ForegroundColor DarkGray
    }

    if ($Workers.Count -gt 1) {
        Write-Warn "Mais de um Worker foi encontrado ($($Workers.Count))"
    }
}
else {
    Write-Fail "Worker nao esta rodando"
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
