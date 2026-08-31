$appPath = Join-Path $PSScriptRoot "app.py"
$pythonPath = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $pythonPath)) {
    Write-Error "Project virtual environment not found at $pythonPath"
    exit 1
}

$port = 8501

Start-Process `
    -FilePath $pythonPath `
    -ArgumentList "-m", "streamlit", "run", $appPath, "--server.headless", "false", "--server.port", $port `
    -WorkingDirectory $PSScriptRoot
