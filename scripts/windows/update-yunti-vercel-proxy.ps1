param(
    [Parameter(Mandatory = $true)]
    [string]$PublicUrl
)

$ErrorActionPreference = "Continue"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$LogDir = Join-Path $RepoRoot "temp\logs"
$VercelLog = Join-Path $LogDir "vercel-proxy.log"
$VercelProxyDir = Join-Path $RepoRoot "deploy\vercel-proxy"
$VercelProxyConfig = Join-Path $VercelProxyDir "vercel.json"
$StableVercelUrl = "https://yunti-ai-sales-online.vercel.app"

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

function Write-Log {
    param([string]$Message)
    $line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $Message"
    Add-Content -LiteralPath $VercelLog -Value $line
}

try {
    Write-Log "Starting Vercel proxy update for $PublicUrl"

    if (-not (Test-Path -LiteralPath $VercelProxyConfig)) {
        Write-Log "Vercel proxy config not found: $VercelProxyConfig"
        exit 1
    }

    $destination = "$PublicUrl/:match*"
    $config = Get-Content -LiteralPath $VercelProxyConfig -Raw | ConvertFrom-Json
    $currentDestination = $config.rewrites[0].destination

    if ($currentDestination -eq $destination) {
        Write-Log "Stable Vercel proxy already points to this tunnel."
        exit 0
    }

    $config.rewrites[0].destination = $destination
    $json = $config | ConvertTo-Json -Depth 10
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($VercelProxyConfig, $json, $utf8NoBom)

    Push-Location $VercelProxyDir
    try {
        Write-Log "Running Vercel deploy..."
        $deployOutput = & cmd.exe /c "corepack pnpm exec vercel deploy --prod --yes --name yunti-ai-sales-online 2>&1"
        $deployOutput | Add-Content -LiteralPath $VercelLog

        if ($LASTEXITCODE -ne 0) {
            Write-Log "Vercel deploy failed with exit code $LASTEXITCODE"
            exit $LASTEXITCODE
        }

        Write-Log "Stable Vercel address updated: $StableVercelUrl"
    } finally {
        Pop-Location
    }
} catch {
    Write-Log "Vercel update error: $($_.Exception.Message)"
    exit 1
}
