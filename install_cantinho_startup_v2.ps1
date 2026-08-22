$ErrorActionPreference = "Stop"

$ProjectDir = $PSScriptRoot
$StartScript = Join-Path $ProjectDir "start_cantinho_background.ps1"
$TaskName = "Cantinho Ghibli AI"

# Caminho absoluto do Windows PowerShell.
$PowerShellExe = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"

if (!(Test-Path $StartScript)) {
    Write-Host ""
    Write-Host "ERRO: start_cantinho_background.ps1 nao foi encontrado." -ForegroundColor Red
    Write-Host "Esperado em:"
    Write-Host $StartScript
    exit 1
}

if (!(Test-Path $PowerShellExe)) {
    Write-Host ""
    Write-Host "ERRO: Windows PowerShell nao encontrado." -ForegroundColor Red
    Write-Host "Esperado em:"
    Write-Host $PowerShellExe
    exit 1
}

$Arguments = "-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$StartScript`""

$Action = New-ScheduledTaskAction `
    -Execute $PowerShellExe `
    -Argument $Arguments `
    -WorkingDirectory $ProjectDir

$Trigger = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME"

$Settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit (New-TimeSpan -Hours 0)

$Principal = New-ScheduledTaskPrincipal `
    -UserId "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType Interactive `
    -RunLevel Limited

# Remove versao anterior para evitar configuracao antiga.
$Existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue

if ($Existing) {
    Unregister-ScheduledTask `
        -TaskName $TaskName `
        -Confirm:$false
}

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Principal $Principal `
    -Description "Inicia Ollama e o Worker do Cantinho Ghibli automaticamente no login." `
    -Force | Out-Null

Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host " Cantinho Ghibli registrado com sucesso!" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host ""
Write-Host "PowerShell:"
Write-Host $PowerShellExe
Write-Host ""
Write-Host "Script:"
Write-Host $StartScript
Write-Host ""
Write-Host "Projeto:"
Write-Host $ProjectDir
Write-Host ""
Write-Host "Agora teste com:"
Write-Host 'Start-ScheduledTask -TaskName "Cantinho Ghibli AI"'
Write-Host ""
