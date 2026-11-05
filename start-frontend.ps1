$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$logDir = Join-Path $root ".runlogs"
New-Item -ItemType Directory -Path $logDir -Force | Out-Null
$nodeCommand = Get-Command node.exe -ErrorAction SilentlyContinue
if (-not $nodeCommand) { throw "Node.js was not found. Install Node.js, reopen VS Code, and rerun this launcher." }
$node = $nodeCommand.Source
function Get-Listener([int]$Port) { Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1 }
function Test-WebReady([string]$Uri) {
    try { $response = Invoke-WebRequest -Uri $Uri -TimeoutSec 3 -UseBasicParsing; return ($response.StatusCode -ge 200 -and $response.StatusCode -lt 400) } catch { return $false }
}
function Start-FrontendIfNeeded {
    param([string]$Name,[int]$Port,[string]$Url,[string]$Cli,[string[]]$Arguments,[string]$WorkingDirectory,[string]$StdoutPath,[string]$StderrPath)
    if (Test-WebReady $Url) { Write-Host "$Name is already running at $Url." -ForegroundColor Green; return }
    $listener = Get-Listener $Port
    if ($null -ne $listener) {
        $ownerPid = [int]$listener.OwningProcess
        $owner = Get-Process -Id $ownerPid -ErrorAction SilentlyContinue
        $ownerName = if ($owner) { $owner.ProcessName } else { "unknown process" }
        throw "Port $Port is occupied by PID $ownerPid ($ownerName), but $Name did not respond. Close that process and rerun this launcher."
    }
    if (-not (Test-Path -LiteralPath $Cli)) { throw "$Name files are missing at $Cli. Run npm install in that frontend folder first." }
    $allArguments = @(('"' + $Cli + '"')) + $Arguments
    $proc = Start-Process -FilePath $node -ArgumentList $allArguments -WorkingDirectory $WorkingDirectory -RedirectStandardOutput $StdoutPath -RedirectStandardError $StderrPath -WindowStyle Hidden -PassThru
    for ($i = 0; $i -lt 90; $i++) {
        Start-Sleep -Seconds 1
        if (Test-WebReady $Url) { Write-Host "$Name started at $Url." -ForegroundColor Green; return }
        if ($proc.HasExited) { break }
    }
    $details = ""
    if (Test-Path -LiteralPath $StderrPath) { $details = (Get-Content -LiteralPath $StderrPath -Tail 12 -ErrorAction SilentlyContinue) -join [Environment]::NewLine }
    if (-not $details -and (Test-Path -LiteralPath $StdoutPath)) { $details = (Get-Content -LiteralPath $StdoutPath -Tail 12 -ErrorAction SilentlyContinue) -join [Environment]::NewLine }
    throw "$Name did not become ready. Recent log: $details"
}
$manufacturingFront = Join-Path $root "ai-pcb-agent\frontend"
$nextArgs = @{
    Name = "PCB Forge manufacturing frontend"
    Port = 3000
    Url = "http://127.0.0.1:3000"
    Cli = Join-Path $manufacturingFront "node_modules\next\dist\bin\next"
    Arguments = @("dev","--hostname","127.0.0.1","--port","3000")
    WorkingDirectory = $manufacturingFront
    StdoutPath = Join-Path $logDir "manufacturing-web.out.log"
    StderrPath = Join-Path $logDir "manufacturing-web.err.log"
}
Start-FrontendIfNeeded @nextArgs
$inspectionFront = Join-Path $root "quality-inspection\front"
$viteArgs = @{
    Name = "PCB inspection frontend"
    Port = 5173
    Url = "http://127.0.0.1:5173"
    Cli = Join-Path $inspectionFront "node_modules\vite\bin\vite.js"
    Arguments = @("dev","--host","127.0.0.1","--port","5173","--strictPort")
    WorkingDirectory = $inspectionFront
    StdoutPath = Join-Path $logDir "inspection-web.out.log"
    StderrPath = Join-Path $logDir "inspection-web.err.log"
}
Start-FrontendIfNeeded @viteArgs
Write-Host ""
Write-Host "Both frontends are ready." -ForegroundColor Cyan
Write-Host "Manufacturing: http://localhost:3000"
Write-Host "Inspection:    http://localhost:5173"
Write-Host "Logs: $logDir"
