# Run with a Python 3.11 venv in .venv (pip install -r requirements.txt windows-curses).
# Stages a runnable Windows distribution without modifying the source checkout.
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path "$PSScriptRoot\..\..").Path
Push-Location $root
try {
    $python = "$root\.venv\Scripts\python.exe"
    $out = "$root\dist\kcauto_custom_windows"
    $build = "$root\build\windows"
    New-Item -ItemType Directory -Force -Path $build, $out | Out-Null
    $common = @('--noconfirm', '--clean', '--paths', 'kcauto', '--specpath', $build, '--workpath', $build)

    & $python -m PyInstaller @common --onedir --distpath "$out\bin" --name kcauto_custom kcauto\__main__.py
    if ($LASTEXITCODE) { throw 'Core build failed' }
    $data = @('--add-data', "$root\kcauto\cui\theme.tcss;cui")
    if (Test-Path kcauto\cui\locales) {
        $data += @('--add-data', "$root\kcauto\cui\locales;cui\locales")
    }
    & $python -m PyInstaller @common @data --onefile --collect-all textual --icon "$root\assets\cui\bot.ico" --distpath $out --name kcauto_cui kcauto\kcauto_cui.py
    if ($LASTEXITCODE) { throw 'Launcher build failed' }
    foreach ($dir in @('assets', 'configs', 'data', 'template')) {
        Copy-Item $dir -Destination $out -Recurse -Force
    }
    Copy-Item LICENSE -Destination $out
    New-Item -ItemType Directory -Force -Path "$out\log" | Out-Null
    Write-Output "Launcher: $out\kcauto_cui.exe"
} finally {
    Pop-Location
}
