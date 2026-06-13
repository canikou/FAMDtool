$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $Root ".venv\Scripts\python.exe"

if (-not (Test-Path $Python)) {
    python -m venv (Join-Path $Root ".venv")
}

& $Python -c "import PIL" 2>$null
if ($LASTEXITCODE -ne 0) {
    & $Python -m pip install -r (Join-Path $Root "requirements.txt")
}
& $Python (Join-Path $Root "famd_tool.py")
