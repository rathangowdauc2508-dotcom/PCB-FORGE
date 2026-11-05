$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path

$pythonLauncher = Get-Command py.exe -ErrorAction SilentlyContinue
if (-not $pythonLauncher) {
    throw "Python Launcher was not found. Install Python 3.11 with the Python Launcher, reopen VS Code, and run setup.ps1 again."
}
$nodeCommand = Get-Command node.exe -ErrorAction SilentlyContinue
if (-not $nodeCommand) {
    throw "Node.js was not found. Install Node.js 22.12 or newer, reopen VS Code, and run setup.ps1 again."
}

$nodeVersion = (& $nodeCommand.Source --version).Trim().TrimStart('v')
$nodeParts = $nodeVersion.Split('.')
$nodeMajor = [int]$nodeParts[0]
$nodeMinor = [int]$nodeParts[1]
if ($nodeMajor -lt 22 -or ($nodeMajor -eq 22 -and $nodeMinor -lt 12)) {
    throw "Node.js 22.12 or newer is required for the Vite frontend. Found $nodeVersion."
}

& $pythonLauncher.Source -3.11 --version
if ($LASTEXITCODE -ne 0) {
    throw "Python 3.11 was not found. Install Python 3.11, reopen VS Code, and run setup.ps1 again."
}

function Invoke-Checked {
    param([string]$Program, [string[]]$Arguments, [string]$WorkingDirectory)
    Push-Location $WorkingDirectory
    try {
        & $Program @Arguments
        if ($LASTEXITCODE -ne 0) {
            throw "Setup command failed with exit code ${LASTEXITCODE}: $Program $($Arguments -join ' ')"
        }
    }
    finally { Pop-Location }
}

$services = @(
    @{ Path = "ai-pcb-agent\backend"; Requirements = "requirements.txt"; EnvExample = ".env.example" },
    @{ Path = "quality-inspection"; Requirements = "requirements.txt"; EnvExample = ".env.example" }
)

foreach ($service in $services) {
    $servicePath = Join-Path $root $service.Path
    $venvPython = Join-Path $servicePath ".venv\Scripts\python.exe"
    if (-not (Test-Path -LiteralPath $venvPython)) {
        Write-Host "Creating Python environment: $($service.Path)" -ForegroundColor Cyan
        Invoke-Checked $pythonLauncher.Source @("-3.11", "-m", "venv", ".venv") $servicePath
    }
    Write-Host "Installing Python packages: $($service.Path)" -ForegroundColor Cyan
    Invoke-Checked $venvPython @("-m", "pip", "install", "-r", $service.Requirements) $servicePath

    $envPath = Join-Path $servicePath ".env"
    if (-not (Test-Path -LiteralPath $envPath)) {
        Copy-Item -LiteralPath (Join-Path $servicePath $service.EnvExample) -Destination $envPath
        Write-Host "Created $($service.Path)\.env from its example." -ForegroundColor Green
    }
}

$frontends = @("ai-pcb-agent\frontend", "quality-inspection\front")
foreach ($frontend in $frontends) {
    $frontendPath = Join-Path $root $frontend
    Write-Host "Installing frontend packages: $frontend" -ForegroundColor Cyan
    Invoke-Checked "npm.cmd" @("install") $frontendPath
}

Write-Host ""
Write-Host "Setup finished. Add your Gemini API key to quality-inspection\.env, then start the backends and frontends using the two start scripts." -ForegroundColor Green
