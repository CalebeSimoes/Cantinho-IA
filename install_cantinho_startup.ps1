$ErrorActionPreference = "Stop"

$ProjectDir = $PSScriptRoot
$StartScript = Join-Path $ProjectDir "start_cantinho_background.ps1"
$TaskName = "Cantinho Ghibli AI"

if (!(Test-Path $StartScript)) {
    Write-Host ""
    Write-Host "ERRO: start_cantinho_background.ps1 nao foi encontrado na mesma pasta." -ForegroundColor Red
    Write-Host "Esperado em: $StartScript"
    exit 1
}

$Action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$StartScript`""

$Trigger = New-ScheduledTaskTrigger -AtLogOn

$Settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit (New-TimeSpan -Hours 0)

$Principal = New-ScheduledTaskPrincipal `
    -UserId "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType Interactive `
    -RunLevel Limited

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Principal $Principal `
    -Description "Inicia Ollama e o Worker do Cantinho Ghibli automaticamente no login." `
    -Force | Out-Null

Write-Host ""
Write-Host "==========================================" -ForegroundColor Green
Write-Host " Cantinho Ghibli configurado com sucesso!" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Tarefa: $TaskName"
Write-Host "Projeto: $ProjectDir"
Write-Host ""
Write-Host "Para testar agora:"
Write-Host 'Start-ScheduledTask -TaskName "Cantinho Ghibli AI"'
Write-Host ""
