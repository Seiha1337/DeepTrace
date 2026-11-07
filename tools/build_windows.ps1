param(
    [string]$Python = (Join-Path $PSScriptRoot '..\.venv\Scripts\python.exe')
)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$logs = Join-Path $root 'local\verification'
New-Item -ItemType Directory -Path $logs -Force | Out-Null
$pythonPath = (Resolve-Path -LiteralPath $Python).Path
Push-Location -LiteralPath $root
try {
    $env:PYTHONUTF8 = '1'
    & $pythonPath -c "import sys; assert sys.platform == 'win32'; assert sys.maxsize > 2**32; assert sys.version_info.releaselevel == 'final', 'Utiliser Python stable pour la livraison'"
    if ($LASTEXITCODE -ne 0) { throw 'Runtime Windows x64 stable requis.' }
    & $pythonPath -m PyInstaller --noconfirm --distpath dist --workpath local/pyinstaller DeepTrace.spec *> (Join-Path $logs 'windows-build.txt')
    if ($LASTEXITCODE -ne 0) {
        Get-Content -LiteralPath (Join-Path $logs 'windows-build.txt') -Tail 30
        throw 'La construction Windows a échoué.'
    }
    $exePath = Join-Path $root 'dist\DeepTrace.exe'
    $hash = (Get-FileHash -LiteralPath $exePath -Algorithm SHA256).Hash.ToLowerInvariant()
    Set-Content -LiteralPath (Join-Path $root 'dist\SHA256SUMS.txt') -Value "$hash  DeepTrace.exe" -Encoding ascii
    Write-Output "Exécutable prêt : $exePath"
    Write-Output "SHA-256 : $hash"
} finally {
    Pop-Location
}
