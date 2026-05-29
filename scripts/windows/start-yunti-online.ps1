param(
    [switch]$RestartTunnel,
    [switch]$SkipVercelUpdate
)

$ErrorActionPreference = "Stop"

$StartupMutex = New-Object System.Threading.Mutex($false, "Global\YuntiLangBotStartup")
if (-not $StartupMutex.WaitOne(0)) {
    Write-Host "Yunti startup is already running. Skip duplicate startup."
    exit 0
}

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$LogDir = Join-Path $RepoRoot "temp\logs"
$ToolDir = Join-Path $RepoRoot "temp\tools"
$Cloudflared = Join-Path $ToolDir "cloudflared.exe"
$PythonExe = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$BackendLog = Join-Path $LogDir "backend.log"
$TunnelLog = Join-Path $LogDir "cloudflared.log"
$LastPublicUrlFile = Join-Path $LogDir "last-public-url.txt"
$VercelLog = Join-Path $LogDir "vercel-proxy.log"
$VercelUpdateScript = Join-Path $RepoRoot "scripts\windows\update-yunti-vercel-proxy.ps1"
$VercelProxyDir = Join-Path $RepoRoot "deploy\vercel-proxy"
$VercelProxyConfig = Join-Path $VercelProxyDir "vercel.json"
$StableVercelUrl = "https://yunti-ai-sales-online.vercel.app"

New-Item -ItemType Directory -Force -Path $LogDir, $ToolDir | Out-Null

function Test-PortListening {
    param([int]$Port)
    $conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    return $null -ne $conn
}

function Stop-ProcessIds {
    param([int[]]$ProcessIds)
    foreach ($processId in ($ProcessIds | Select-Object -Unique)) {
        if ($processId -and $processId -ne $PID) {
            Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
        }
    }
}

function Get-ProcessIdsByPort {
    param([int[]]$Ports)
    Get-NetTCPConnection -LocalPort $Ports -State Listen -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique
}

function Remove-StaleYuntiProcesses {
    $backendOwner = Get-ProcessIdsByPort -Ports @(5300)
    $devServerOwners = Get-ProcessIdsByPort -Ports @(3000)

    if ($devServerOwners) {
        Write-Host "Stopping unused Vite dev server on 3000..."
        Stop-ProcessIds -ProcessIds $devServerOwners
    }

    $repoPath = [string]$RepoRoot
    $processes = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue

    if (-not $backendOwner) {
        $staleBackends = $processes |
            Where-Object {
                $_.CommandLine -and
                $_.CommandLine -like "*$repoPath*" -and
                $_.CommandLine -match "main\.py"
            } |
            Select-Object -ExpandProperty ProcessId
        Stop-ProcessIds -ProcessIds $staleBackends
    }

    if (-not $backendOwner) {
        $pluginRuntimePids = $processes |
            Where-Object {
                $_.CommandLine -and
                $_.CommandLine -like "*$repoPath*" -and
                $_.CommandLine -match "langbot_plugin\.cli\.__init__"
            } |
            Select-Object -ExpandProperty ProcessId
        Stop-ProcessIds -ProcessIds $pluginRuntimePids
    }

    $unrelatedTunnels = $processes |
        Where-Object {
            $_.Name -eq "cloudflared.exe" -and
            $_.CommandLine -and
            $_.CommandLine -notmatch "127\.0\.0\.1:5300|localhost:5300"
        } |
        Select-Object -ExpandProperty ProcessId
    Stop-ProcessIds -ProcessIds $unrelatedTunnels
}

function Start-HiddenProcess {
    param(
        [string]$FilePath,
        [string]$Arguments,
        [string]$WorkingDirectory,
        [string]$LogPath
    )

    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $FilePath
    $psi.Arguments = $Arguments
    $psi.WorkingDirectory = $WorkingDirectory
    $psi.UseShellExecute = $false
    $psi.CreateNoWindow = $true
    $psi.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Hidden
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.EnvironmentVariables["PYTHONUTF8"] = "1"
    $psi.EnvironmentVariables["PYTHONIOENCODING"] = "utf-8"
    $psi.EnvironmentVariables["PYTHONUNBUFFERED"] = "1"

    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $psi
    $process.EnableRaisingEvents = $true

    $stdoutAction = {
        if ($EventArgs.Data) {
            Add-Content -LiteralPath $Event.MessageData -Value $EventArgs.Data
        }
    }
    Register-ObjectEvent -InputObject $process -EventName OutputDataReceived -Action $stdoutAction -MessageData $LogPath | Out-Null
    Register-ObjectEvent -InputObject $process -EventName ErrorDataReceived -Action $stdoutAction -MessageData $LogPath | Out-Null

    [void]$process.Start()
    $process.BeginOutputReadLine()
    $process.BeginErrorReadLine()
    return $process
}

function Update-VercelProxy {
    param([string]$PublicUrl)

    if (-not (Test-Path -LiteralPath $VercelUpdateScript)) {
        Write-Host "Vercel update script not found: $VercelUpdateScript"
        return
    }

    Write-Host "Updating stable Vercel address in background..."
    $args = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$VercelUpdateScript`" -PublicUrl `"$PublicUrl`""
    Start-Process -FilePath "powershell.exe" -ArgumentList $args -WindowStyle Hidden | Out-Null
}

if (-not (Test-Path -LiteralPath $Cloudflared)) {
    Write-Host "Downloading cloudflared..."
    $url = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"
    Invoke-WebRequest -Uri $url -OutFile $Cloudflared
}

if (-not (Test-Path -LiteralPath $PythonExe)) {
    throw "Python virtual environment not found: $PythonExe"
}

Remove-StaleYuntiProcesses

if (-not (Test-PortListening -Port 5300)) {
    Write-Host "Starting LangBot backend..."
    Start-HiddenProcess `
        -FilePath $PythonExe `
        -Arguments "main.py" `
        -WorkingDirectory $RepoRoot `
        -LogPath $BackendLog | Out-Null
} else {
    Write-Host "LangBot backend is already listening on 5300."
}

Write-Host "Waiting for backend health..."
$backendReady = $false
for ($i = 0; $i -lt 30; $i++) {
    try {
        $resp = Invoke-WebRequest -Uri "http://127.0.0.1:5300/api/v1/system/info" -UseBasicParsing -TimeoutSec 2
        if ($resp.StatusCode -eq 200) {
            $backendReady = $true
            break
        }
    } catch {
        Start-Sleep -Seconds 1
    }
}

if (-not $backendReady) {
    throw "Backend did not become healthy. Check $BackendLog"
}

$tunnelProcesses = Get-CimInstance Win32_Process -Filter "name = 'cloudflared.exe'" |
    Where-Object { $_.CommandLine -match "127\.0\.0\.1:5300|localhost:5300" }

if ($RestartTunnel -and $tunnelProcesses) {
    $tunnelProcesses | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
    $tunnelProcesses = @()
    Start-Sleep -Seconds 2
}

if (-not $tunnelProcesses) {
    Write-Host "Starting public tunnel..."
    Clear-Content -LiteralPath $TunnelLog -ErrorAction SilentlyContinue
    Start-HiddenProcess `
        -FilePath $Cloudflared `
        -Arguments "tunnel --url http://127.0.0.1:5300 --no-autoupdate" `
        -WorkingDirectory $RepoRoot `
        -LogPath $TunnelLog | Out-Null
} else {
    Write-Host "Public tunnel is already running."
}

Write-Host "Waiting for public URL..."
$publicUrl = $null
for ($i = 0; $i -lt 3; $i++) {
    if (Test-Path -LiteralPath $TunnelLog) {
        $content = Get-Content -LiteralPath $TunnelLog -Tail 80 -ErrorAction SilentlyContinue | Out-String
        $match = [regex]::Match($content, "https://[a-zA-Z0-9-]+\.trycloudflare\.com")
        if ($match.Success) {
            $publicUrl = $match.Value
            Set-Content -LiteralPath $LastPublicUrlFile -Value $publicUrl -Encoding ASCII
            break
        }
    }
    Start-Sleep -Seconds 1
}

if ($publicUrl) {
    Write-Host "Yunti AI sales system is online:"
    Write-Host $publicUrl
    if (-not $SkipVercelUpdate) {
        Update-VercelProxy -PublicUrl $publicUrl
    }
    Write-Host "Stable public address:"
    Write-Host $StableVercelUrl
} else {
    if (Test-Path -LiteralPath $LastPublicUrlFile) {
        $lastPublicUrl = Get-Content -LiteralPath $LastPublicUrlFile -TotalCount 1
        Write-Host "Tunnel is still connecting. Last public tunnel:"
        Write-Host $lastPublicUrl
    } else {
        Write-Host "Tunnel is still connecting. Check $TunnelLog"
    }
    Write-Host "Stable public address:"
    Write-Host $StableVercelUrl
}

$StartupMutex.ReleaseMutex() | Out-Null
$StartupMutex.Dispose()
