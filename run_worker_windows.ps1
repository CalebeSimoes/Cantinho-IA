$ErrorActionPreference = "Stop"
Write-Host "🤖 Iniciando Worker..."
.\.venv\Scripts\python.exe -m app.worker
