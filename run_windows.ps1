$ErrorActionPreference = "Stop"

Write-Host "Iniciando Cantinho Ghibli AI..."
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
