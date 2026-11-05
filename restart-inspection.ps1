$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$healthUrl = "http://127.0.0.1:8001/health"
$health = $null
try { $health = Invoke-RestMethod -Uri $healthUrl -TimeoutSec 3 } catch { }
$listener = Get-NetTCPConnection -LocalPort 8001 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1

if ($null -ne $listener) {
    $ownerPid = [int]$listener.OwningProcess
    $owner = Get-Process -Id $ownerPid -ErrorAction SilentlyContinue
    $isInspectionApi = $null -ne $health -and $health.status -eq "ok" -and $null -ne $health.gemini_api_key_configured -and $null -ne $health.gemini_key_count
    if (-not $isInspectionApi -or $null -eq $owner -or $owner.ProcessName -notmatch "(?i)^pythonw?$") {
        throw "Could not verify that port 8001 belongs to the PCB Forge inspection API. Nothing was stopped."
    }
    Stop-Process -Id $ownerPid -Force
    for ($i = 0; $i -lt 10; $i++) {
        Start-Sleep -Milliseconds 300
        if (-not (Get-NetTCPConnection -LocalPort 8001 -State Listen -ErrorAction SilentlyContinue)) { break }
    }
} elseif ($null -ne $health -and $health.status -eq "ok" -and $null -ne $health.gemini_api_key_configured) {
    throw "The inspection API responds, but Windows did not provide its listener PID. Close its backend process in Task Manager, then rerun this script."
}

$quality = Join-Path $root "quality-inspection"
$python = Join-Path $quality ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) { throw "Inspection Python was not found: $python" }

$logDir = Join-Path $root ".runlogs"
New-Item -ItemType Directory -Path $logDir -Force | Out-Null
$stdout = Join-Path $logDir "gemma-api.out.log"
$stderr = Join-Path $logDir "gemma-api.err.log"
$process = Start-Process -FilePath $python `
    -ArgumentList @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8001") `
    -WorkingDirectory $quality `
    -RedirectStandardOutput $stdout `
    -RedirectStandardError $stderr `
    -WindowStyle Hidden -PassThru

for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Seconds 1
    try {
        $health = Invoke-RestMethod -Uri $healthUrl -TimeoutSec 2
        if ($health.status -eq "ok" -and $health.gemini_api_key_configured) {
            Write-Host "PCB Forge inspection API restarted with Gemma credentials on port 8001." -ForegroundColor Green
            exit 0
        }
    } catch { }
    if ($process.HasExited) { break }
}

$details = if (Test-Path -LiteralPath $stderr) { (Get-Content -LiteralPath $stderr -Tail 12 -ErrorAction SilentlyContinue) -join [Environment]::NewLine } else { "No backend log was created." }
throw "Inspection API did not start. $details"
