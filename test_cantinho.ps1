$ErrorActionPreference = "Stop"

$ProjectDir = $PSScriptRoot
$Python = Join-Path $ProjectDir ".venv\Scripts\python.exe"
$DevRequirements = Join-Path $ProjectDir "requirements-dev.txt"
$LogsDir = Join-Path $ProjectDir "logs"
$Report = Join-Path $LogsDir "tests-last.txt"
$PytestTemp = Join-Path `
    $LogsDir `
    ("pytest-" + [Guid]::NewGuid().ToString("N"))

$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

if (!(Test-Path $Python)) {
    Write-Host "[ERRO] Python da .venv nao encontrado." -ForegroundColor Red
    exit 1
}

if (!(Test-Path $DevRequirements)) {
    Write-Host "[ERRO] requirements-dev.txt nao encontrado." -ForegroundColor Red
    exit 1
}

if (!(Test-Path $LogsDir)) {
    New-Item -ItemType Directory -Path $LogsDir | Out-Null
}

Push-Location $ProjectDir

try {
    # Verifica pytest sem gerar erro no stderr quando o modulo nao existe.
    $PytestFound = & $Python -c "import importlib.util; print('1' if importlib.util.find_spec('pytest') else '0')"

    if (($PytestFound | Select-Object -Last 1).Trim() -ne "1") {
        Write-Host ""
        Write-Host "pytest nao encontrado. Instalando dependencias de teste..." -ForegroundColor Yellow
        Write-Host ""

        & $Python -m pip install -r $DevRequirements

        if ($LASTEXITCODE -ne 0) {
            Write-Host ""
            Write-Host "[ERRO] Nao foi possivel instalar as dependencias de teste." -ForegroundColor Red
            exit 1
        }

        Write-Host ""
        Write-Host "[OK] Dependencias de teste instaladas." -ForegroundColor Green
    }
    else {
        Write-Host "[OK] pytest ja esta instalado." -ForegroundColor Green
    }

    Write-Host ""
    Write-Host "==============================================" -ForegroundColor Cyan
    Write-Host "       TESTES - CANTINHO GHIBLI AI" -ForegroundColor Cyan
    Write-Host "==============================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Suite offline: nao grava no Notion e nao chama Ollama real." -ForegroundColor DarkGray
    Write-Host ""

    # Durante a suite, nao queremos que stderr de pytest seja convertido
    # em excecao do PowerShell antes de capturarmos o exit code.
    $PreviousPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"

    & $Python `
        -m pytest `
        -q `
        -p no:cacheprovider `
        --basetemp $PytestTemp `
        2>&1 | Tee-Object -FilePath $Report
    $Code = $LASTEXITCODE

    $ErrorActionPreference = $PreviousPreference

    Write-Host ""

    if ($Code -eq 0) {
        Write-Host "==============================================" -ForegroundColor Green
        Write-Host " CANTINHO APROVADO NOS TESTES" -ForegroundColor Green
        Write-Host "==============================================" -ForegroundColor Green
        Write-Host "Relatorio: $Report" -ForegroundColor DarkGray
    }
    else {
        Write-Host "==============================================" -ForegroundColor Red
        Write-Host " TESTES FALHARAM - NAO FAÇA DEPLOY AINDA" -ForegroundColor Red
        Write-Host "==============================================" -ForegroundColor Red
        Write-Host "Relatorio: $Report" -ForegroundColor Yellow
    }

    exit $Code
}
finally {
    Pop-Location
}
