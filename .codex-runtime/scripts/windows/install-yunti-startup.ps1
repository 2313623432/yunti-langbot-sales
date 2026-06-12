$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$StartScript = Join-Path $RepoRoot "scripts\windows\start-yunti-online.ps1"
$TaskName = "YuntiLangBotOnline"
$RunName = "YuntiLangBotOnline"
$PowerShell = (Get-Command powershell.exe).Source
$RunCommand = "`"$PowerShell`" -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$StartScript`""

try {
    $Action = New-ScheduledTaskAction `
        -Execute $PowerShell `
        -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$StartScript`""
    $Trigger = New-ScheduledTaskTrigger -AtLogOn
    $Settings = New-ScheduledTaskSettingsSet `
        -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries `
        -RestartCount 3 `
        -RestartInterval (New-TimeSpan -Minutes 1)

    Register-ScheduledTask `
        -TaskName $TaskName `
        -Action $Action `
        -Trigger $Trigger `
        -Settings $Settings `
        -Description "Start Yunti LangBot backend, plugin runtime, and public tunnel at Windows logon." `
        -Force | Out-Null

    Write-Host "Startup task installed: $TaskName"
} catch {
    $StartupDir = [Environment]::GetFolderPath("Startup")
    $StartupCmd = Join-Path $StartupDir "YuntiLangBotOnline.cmd"
    $CmdContent = "@echo off`r`n$RunCommand`r`n"
    Set-Content -LiteralPath $StartupCmd -Value $CmdContent -Encoding ASCII
    Write-Host "Scheduled task was unavailable, startup shortcut installed:"
    Write-Host $StartupCmd
}

$RunKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"
New-Item -Path $RunKey -Force | Out-Null
Set-ItemProperty -Path $RunKey -Name $RunName -Value $RunCommand
Write-Host "Current-user auto start installed:"
Write-Host "$RunKey\$RunName"
