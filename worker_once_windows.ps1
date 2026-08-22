$ErrorActionPreference = "Stop"
Write-Host "🤖 Processando a Caixa de Entrada uma vez..."
.\.venv\Scripts\python.exe -m app.worker --once
