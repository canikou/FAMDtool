$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$Version = "1.0.0"
$AppName = "FAMDTool"
$DistDir = Join-Path $Root "dist\$AppName"
$ReleaseDir = Join-Path $Root "release"
$ZipPath = Join-Path $ReleaseDir "$AppName-v$Version-windows.zip"

if (-not (Test-Path $Python)) {
    py -3 -m venv (Join-Path $Root ".venv")
}

& $Python -m pip install --upgrade pip
& $Python -m pip install -r (Join-Path $Root "requirements.txt") -r (Join-Path $Root "requirements-build.txt")

& $Python -m compileall -q (Join-Path $Root "famd_tool.py") (Join-Path $Root "famdtool") (Join-Path $Root "tests")
& $Python -m unittest discover -s (Join-Path $Root "tests")

foreach ($Path in @((Join-Path $Root "build"), (Join-Path $Root "dist"), $ReleaseDir)) {
    if (Test-Path $Path) {
        Remove-Item -LiteralPath $Path -Recurse -Force
    }
}

& $Python -m PyInstaller (Join-Path $Root "famd_tool.spec") --noconfirm --clean

Copy-Item -LiteralPath (Join-Path $Root "config.cfg") -Destination (Join-Path $DistDir "config.cfg") -Force
Copy-Item -LiteralPath (Join-Path $Root "README.md") -Destination (Join-Path $DistDir "README.md") -Force

foreach ($Folder in @("attachments", "exports", "logs")) {
    New-Item -ItemType Directory -Force -Path (Join-Path $DistDir $Folder) | Out-Null
}

New-Item -ItemType Directory -Force -Path $ReleaseDir | Out-Null
Compress-Archive -Path (Join-Path $DistDir "*") -DestinationPath $ZipPath -Force

Write-Host "Built $ZipPath"
