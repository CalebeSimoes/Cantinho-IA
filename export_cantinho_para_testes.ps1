$ErrorActionPreference = "Stop"

$Source = $PSScriptRoot
$Temp = Join-Path $env:TEMP "cantinho-ghibli-src-testes"
$Output = Join-Path $Source "cantinho-ghibli-src-testes.zip"

Write-Host ""
Write-Host "Preparando copia segura do Cantinho para testes..." -ForegroundColor Cyan
Write-Host ""

if (Test-Path $Temp) {
    Remove-Item $Temp -Recurse -Force
}

New-Item -ItemType Directory -Path $Temp | Out-Null

$null = robocopy `
    $Source `
    $Temp `
    /E `
    /XD ".venv" "logs" "__pycache__" ".git" ".pytest_cache" `
    /XF ".env" "*.pyc" "*.pyo" "cantinho-ghibli-src-testes.zip" `
    /NFL /NDL /NJH /NJS /NP

if ($LASTEXITCODE -gt 7) {
    throw "Falha ao copiar arquivos. Codigo robocopy: $LASTEXITCODE"
}

if (Test-Path $Output) {
    Remove-Item $Output -Force
}

Compress-Archive `
    -Path (Join-Path $Temp "*") `
    -DestinationPath $Output `
    -Force

Remove-Item $Temp -Recurse -Force

Write-Host "==============================================" -ForegroundColor Green
Write-Host " EXPORTACAO CONCLUIDA" -ForegroundColor Green
Write-Host "==============================================" -ForegroundColor Green
Write-Host ""
Write-Host "Arquivo criado:"
Write-Host $Output -ForegroundColor Yellow
Write-Host ""
Write-Host "O arquivo .env, .venv, logs e .git NAO foram incluidos."
Write-Host "Agora envie o ZIP para o ChatGPT."
Write-Host ""
