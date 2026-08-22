$ErrorActionPreference = "Stop"
Write-Host "🌐 Iniciando API..."
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
