$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$Version = "1.5.1"
$AppName = "FAMDTool"
$DistDir = Join-Path $Root "dist\$AppName"
$ReleaseDir = Join-Path $Root "release"
$ZipPath = Join-Path $ReleaseDir "$AppName-v$Version-windows.zip"
$InstallerPath = Join-Path $ReleaseDir "$AppName-v$Version-windows-setup.exe"

function Find-InnoCompiler {
    $Command = Get-Command "ISCC.exe" -ErrorAction SilentlyContinue
    if ($Command) {
        return $Command.Source
    }

    $Candidates = @(
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "${env:ProgramFiles}\Inno Setup 6\ISCC.exe",
        "${env:LOCALAPPDATA}\Programs\Inno Setup 6\ISCC.exe"
    )
    foreach ($Candidate in $Candidates) {
        if ($Candidate -and (Test-Path $Candidate)) {
            return $Candidate
        }
    }
    return $null
}

function Ensure-InnoCompiler {
    $Compiler = Find-InnoCompiler
    if ($Compiler) {
        return $Compiler
    }

    $Winget = Get-Command "winget.exe" -ErrorAction SilentlyContinue
    if (-not $Winget) {
        throw "Inno Setup compiler not found. Install Inno Setup 6 or install winget, then rerun this script."
    }

    $null = & $Winget.Source install --id JRSoftware.InnoSetup -e --silent --accept-package-agreements --accept-source-agreements
    $Compiler = Find-InnoCompiler
    if (-not $Compiler) {
        throw "Inno Setup compiler was not found after winget install."
    }
    return $Compiler
}

if (-not (Test-Path $Python)) {
    py -3 -m venv (Join-Path $Root ".venv")
}

& $Python -m pip install --upgrade pip
& $Python -m pip install -r (Join-Path $Root "requirements.txt") -r (Join-Path $Root "requirements-build.txt")

& $Python -m compileall -q (Join-Path $Root "famd_tool.py") (Join-Path $Root "famdtool") (Join-Path $Root "tests")
& $Python -m unittest discover -s (Join-Path $Root "tests")
& $Python (Join-Path $Root "tools\generate_icon.py")

foreach ($Path in @((Join-Path $Root "build"), (Join-Path $Root "dist"), $ReleaseDir)) {
    if (Test-Path $Path) {
        Remove-Item -LiteralPath $Path -Recurse -Force
    }
}

& $Python -m PyInstaller (Join-Path $Root "famd_tool.spec") --noconfirm --clean

Copy-Item -LiteralPath (Join-Path $Root "config.cfg") -Destination (Join-Path $DistDir "config.cfg") -Force
Copy-Item -LiteralPath (Join-Path $Root "README.md") -Destination (Join-Path $DistDir "README.md") -Force
Copy-Item -LiteralPath (Join-Path $Root "assets") -Destination (Join-Path $DistDir "assets") -Recurse -Force

foreach ($Folder in @("attachments", "exports", "logs")) {
    New-Item -ItemType Directory -Force -Path (Join-Path $DistDir $Folder) | Out-Null
}

New-Item -ItemType Directory -Force -Path $ReleaseDir | Out-Null
Compress-Archive -Path (Join-Path $DistDir "*") -DestinationPath $ZipPath -Force

$InnoCompiler = [string](Ensure-InnoCompiler | Select-Object -Last 1)
& $InnoCompiler (Join-Path $Root "packaging\FAMDTool.iss") "/DMyAppVersion=$Version"
if (-not (Test-Path $InstallerPath)) {
    throw "Installer was not produced: $InstallerPath"
}

Write-Host "Built $ZipPath"
Write-Host "Built $InstallerPath"
