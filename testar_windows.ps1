$ErrorActionPreference = "Stop"
Write-Host "1/4 Configuração"; .\.venv\Scripts\python.exe -m scripts.check_env
Write-Host "2/4 Ollama"; .\.venv\Scripts\python.exe -m scripts.test_ollama
Write-Host "3/4 Notion"; .\.venv\Scripts\python.exe -m scripts.test_notion
Write-Host "4/4 Router"; .\.venv\Scripts\python.exe -m scripts.test_router
Write-Host "✅ Testes básicos concluídos."
