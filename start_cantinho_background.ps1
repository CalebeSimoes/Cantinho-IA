$ErrorActionPreference = "Stop"

$ProjectDir = $PSScriptRoot
$Python = Join-Path $ProjectDir ".venv\Scripts\python.exe"

$LogsDir = Join-Path $ProjectDir "logs"

$WorkerOut = Join-Path $LogsDir "worker.log"
$WorkerErr = Join-Path $LogsDir "worker-error.log"
$OllamaOut = Join-Path $LogsDir "ollama.log"
$OllamaErr = Join-Path $LogsDir "ollama-error.log"
$StartupLog = Join-Path $LogsDir "startup.log"
$WorkerPidFile = Join-Path $LogsDir "worker.pid"

if (!(Test-Path $LogsDir)) {
    New-Item -ItemType Directory -Path $LogsDir | Out-Null
}

function Write-StartupLog {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Message
    )

    Add-Content `
        -Path $StartupLog `
        -Value "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') - $Message"
}

function Get-WorkerByPid {
    if (!(Test-Path $WorkerPidFile)) {
        return $null
    }

    try {
        $SavedPid = [int](Get-Content $WorkerPidFile -ErrorAction Stop | Select-Object -First 1)
        $Proc = Get-CimInstance Win32_Process -Filter "ProcessId = $SavedPid" -ErrorAction Stop

        if (
            $null -ne $Proc -and
            $Proc.CommandLine -like "*-m app.worker*"
        ) {
            return $Proc
        }
    }
    catch {
        return $null
    }

    return $null
}

function Find-ExistingWorkerRoot {
    $Workers = @(
        Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object {
            $_.CommandLine -like "*-m app.worker*"
        }
    )

    if ($Workers.Count -eq 0) {
        return $null
    }

    $WorkerIds = @($Workers | ForEach-Object { [int]$_.ProcessId })

    # A .venv pode gerar um processo wrapper + processo Python real.
    # Consideramos como "raiz logica" aquele cujo pai nao esta no conjunto.
    $Roots = @(
        $Workers |
        Where-Object {
            $WorkerIds -notcontains [int]$_.ParentProcessId
        } |
        Sort-Object CreationDate
    )

    if ($Roots.Count -gt 0) {
        if ($Roots.Count -gt 1) {
            Write-StartupLog "AVISO: Foram encontrados $($Roots.Count) Workers logicos. Mantendo referencia ao mais antigo."
        }

        return $Roots[0]
    }

    return $Workers[0]
}

# ==========================================================
# Forcar UTF-8 no Python em background
# ==========================================================

$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUNBUFFERED = "1"

Write-StartupLog "Inicializacao do Cantinho Ghibli solicitada."

# ==========================================================
# 1. Verificar Ollama
# ==========================================================

$OllamaRunning = $false

try {
    $null = Invoke-RestMethod `
        -Uri "http://127.0.0.1:11434/api/tags" `
        -TimeoutSec 2

    $OllamaRunning = $true
    Write-StartupLog "Ollama ja estava rodando."
}
catch {
    $OllamaRunning = $false
}

if (-not $OllamaRunning) {

    $OllamaCommand = Get-Command ollama.exe -ErrorAction SilentlyContinue

    if ($null -eq $OllamaCommand) {
        Write-StartupLog "ERRO: Ollama nao encontrado."
        exit 1
    }

    Write-StartupLog "Ollama nao estava rodando. Iniciando ollama serve."

    Start-Process `
        -FilePath $OllamaCommand.Source `
        -ArgumentList "serve" `
        -WindowStyle Hidden `
        -RedirectStandardOutput $OllamaOut `
        -RedirectStandardError $OllamaErr

    $Tentativas = 0

    while ($Tentativas -lt 30) {

        Start-Sleep -Seconds 1

        try {
            $null = Invoke-RestMethod `
                -Uri "http://127.0.0.1:11434/api/tags" `
                -TimeoutSec 2

            $OllamaRunning = $true
            Write-StartupLog "Ollama iniciado com sucesso."
            break
        }
        catch {
            $Tentativas++
        }
    }
}

if (-not $OllamaRunning) {
    Write-StartupLog "ERRO: Ollama nao respondeu apos 30 tentativas."
    exit 1
}

# ==========================================================
# 2. Verificar Worker pelo PID salvo
# ==========================================================

$WorkerByPid = Get-WorkerByPid

if ($null -ne $WorkerByPid) {
    Write-StartupLog "Worker ja estava rodando (PID $($WorkerByPid.ProcessId)). Nenhuma nova instancia foi criada."
    exit 0
}

# ==========================================================
# 3. Fallback: procurar Worker existente e adotar PID
# ==========================================================

$ExistingWorker = Find-ExistingWorkerRoot

if ($null -ne $ExistingWorker) {
    Set-Content `
        -Path $WorkerPidFile `
        -Value $ExistingWorker.ProcessId `
        -Encoding ascii

    Write-StartupLog "Worker existente encontrado e adotado (PID $($ExistingWorker.ProcessId)). Nenhuma nova instancia foi criada."
    exit 0
}

# PID antigo/stale nao deve impedir novo start.
if (Test-Path $WorkerPidFile) {
    Remove-Item $WorkerPidFile -Force -ErrorAction SilentlyContinue
}

# ==========================================================
# 4. Verificar Python da .venv
# ==========================================================

if (!(Test-Path $Python)) {
    Write-StartupLog "ERRO: Python da .venv nao encontrado em $Python."
    exit 1
}

# ==========================================================
# 5. Iniciar Worker em background
# ==========================================================

Write-StartupLog "Iniciando Worker em background com UTF-8 e PID lock."

$StartedProcess = Start-Process `
    -FilePath $Python `
    -ArgumentList "-u", "-m", "app.worker" `
    -WorkingDirectory $ProjectDir `
    -WindowStyle Hidden `
    -RedirectStandardOutput $WorkerOut `
    -RedirectStandardError $WorkerErr `
    -PassThru

Set-Content `
    -Path $WorkerPidFile `
    -Value $StartedProcess.Id `
    -Encoding ascii

Start-Sleep -Seconds 3

$WorkerStarted = Get-WorkerByPid

if ($null -ne $WorkerStarted) {
    Write-StartupLog "Cantinho Ghibli iniciado automaticamente com sucesso (PID $($WorkerStarted.ProcessId))."
    exit 0
}

# Em alguns ambientes o launcher da .venv pode trocar de PID.
# Fazemos uma ultima busca e adotamos a raiz encontrada.
$FallbackWorker = Find-ExistingWorkerRoot

if ($null -ne $FallbackWorker) {
    Set-Content `
        -Path $WorkerPidFile `
        -Value $FallbackWorker.ProcessId `
        -Encoding ascii

    Write-StartupLog "Cantinho Ghibli iniciado com sucesso; PID final adotado: $($FallbackWorker.ProcessId)."
    exit 0
}

Remove-Item $WorkerPidFile -Force -ErrorAction SilentlyContinue
Write-StartupLog "ERRO: O Worker nao foi encontrado apos a tentativa de inicializacao."
exit 1