$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")

function Stop-ProcessIds {
    param([int[]]$ProcessIds)
    foreach ($processId in ($ProcessIds | Select-Object -Unique)) {
        if ($processId -and $processId -ne $PID) {
            Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
        }
    }
}

$tunnelProcesses = Get-CimInstance Win32_Process -Filter "name = 'cloudflared.exe'" |
    Where-Object { $_.CommandLine -match "127\.0\.0\.1:5300|localhost:5300" } |
    Select-Object -ExpandProperty ProcessId
Stop-ProcessIds -ProcessIds $tunnelProcesses

$servicePids = Get-NetTCPConnection -LocalPort 5300,5400,5401 -State Listen -ErrorAction SilentlyContinue |
    Select-Object -ExpandProperty OwningProcess -Unique
Stop-ProcessIds -ProcessIds $servicePids

$repoPath = [string]$RepoRoot
$relatedPids = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
    Where-Object {
        $_.CommandLine -and
        (
            ($_.CommandLine -like "*$repoPath*" -and $_.CommandLine -match "main\.py|langbot_plugin\.cli\.__init__|vite") -or
            ($_.Name -eq "cloudflared.exe" -and $_.CommandLine -match "127\.0\.0\.1:5300|localhost:5300")
        )
    } |
    Select-Object -ExpandProperty ProcessId
Stop-ProcessIds -ProcessIds $relatedPids

Write-Host "Yunti AI sales system processes stopped."
