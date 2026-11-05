$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$logDir = Join-Path $root ".runlogs"
New-Item -ItemType Directory -Path $logDir -Force | Out-Null
function Get-Listener([int]$Port) { Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1 }
function Get-Health($Uri) { try { return Invoke-RestMethod -Uri $Uri -TimeoutSec 3 } catch { return $null } }
function Start-ServiceIfNeeded {
    param([string]$Name,[int]$Port,[string]$HealthUrl,[string]$Exe,[string[]]$Arguments,[string]$WorkingDirectory,[string]$StdoutPath,[string]$StderrPath)
    $health = Get-Health $HealthUrl
    if ($null -ne $health) { Write-Host "$Name is already running on port $Port." -ForegroundColor Green; return $health }
    $listener = Get-Listener $Port
    if ($null -ne $listener) {
        $ownerPid = [int]$listener.OwningProcess
        $owner = Get-Process -Id $ownerPid -ErrorAction SilentlyContinue
        $ownerName = if ($owner) { $owner.ProcessName } else { "unknown process" }
        throw "Port $Port is occupied by PID $ownerPid ($ownerName), but $Name did not answer its health check. Close that process and rerun this launcher."
    }
    if (-not (Test-Path -LiteralPath $Exe)) { throw "$Name Python was not found: $Exe" }
    $proc = Start-Process -FilePath $Exe -ArgumentList $Arguments -WorkingDirectory $WorkingDirectory -RedirectStandardOutput $StdoutPath -RedirectStandardError $StderrPath -WindowStyle Hidden -PassThru
    for ($i = 0; $i -lt 60; $i++) {
        Start-Sleep -Seconds 1
        $health = Get-Health $HealthUrl
        if ($null -ne $health) { Write-Host "$Name started on port $Port." -ForegroundColor Green; return $health }
        if ($proc.HasExited) { break }
    }
    $details = ""
    if (Test-Path -LiteralPath $StderrPath) { $details = (Get-Content -LiteralPath $StderrPath -Tail 12 -ErrorAction SilentlyContinue) -join [Environment]::NewLine }
    if (-not $details -and (Test-Path -LiteralPath $StdoutPath)) { $details = (Get-Content -LiteralPath $StdoutPath -Tail 12 -ErrorAction SilentlyContinue) -join [Environment]::NewLine }
    throw "$Name did not become ready. Recent log: $details"
}
$backend = Join-Path $root "ai-pcb-agent\backend"
$manufacturingArgs = @{
    Name = "PCB Forge manufacturing API"
    Port = 8000
    HealthUrl = "http://127.0.0.1:8000/api/health"
    Exe = Join-Path $backend ".venv\Scripts\python.exe"
    Arguments = @("-m","uvicorn","main:app","--host","127.0.0.1","--port","8000")
    WorkingDirectory = $backend
    StdoutPath = Join-Path $logDir "manufacturing-api.out.log"
    StderrPath = Join-Path $logDir "manufacturing-api.err.log"
}
$null = Start-ServiceIfNeeded @manufacturingArgs
$quality = Join-Path $root "quality-inspection"
$qualityArgs = @{
    Name = "Gemma and inspection API"
    Port = 8001
    HealthUrl = "http://127.0.0.1:8001/health"
    Exe = Join-Path $quality ".venv\Scripts\python.exe"
    Arguments = @("-m","uvicorn","app.main:app","--host","127.0.0.1","--port","8001")
    WorkingDirectory = $quality
    StdoutPath = Join-Path $logDir "gemma-api.out.log"
    StderrPath = Join-Path $logDir "gemma-api.err.log"
}
$gemmaHealth = Start-ServiceIfNeeded @qualityArgs
if (-not $gemmaHealth.gemini_api_key_configured) { Write-Warning "No Gemini key was loaded. Check quality-inspection\.env; keep the key private, then rerun this launcher." }
Write-Host ""
Write-Host "Backend services are ready." -ForegroundColor Cyan
Write-Host "Manufacturing API: http://127.0.0.1:8000"
Write-Host "Gemma/inspection API: http://127.0.0.1:8001"
Write-Host "Logs: $logDir"
