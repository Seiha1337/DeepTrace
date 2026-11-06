$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root '.venv\Scripts\python.exe'
$logs = Join-Path $root 'local\verification'
New-Item -ItemType Directory -Force -Path $logs | Out-Null
Push-Location -LiteralPath $root
try {
    $env:PYTHONUTF8 = '1'
    $checks = @(
        @{ Name='lint'; Args=@('-m','ruff','check','src','tests','tools') },
        @{ Name='format'; Args=@('-m','ruff','format','--check','src','tests','tools') },
        @{ Name='publication'; Args=@('tools/check_repository.py') },
        @{ Name='tests'; Args=@('-m','pytest','-q') },
        @{ Name='build'; Args=@('-m','build','--no-isolation') }
    )
    foreach ($check in $checks) {
        $arguments = $check.Args
        $log = Join-Path $logs ($check.Name + '.txt')
        & $python @arguments *> $log
        if ($LASTEXITCODE -ne 0) {
            Get-Content -LiteralPath $log -Tail 30
            throw "Échec du contrôle $($check.Name) ; code $LASTEXITCODE"
        }
        Write-Output "$($check.Name) : OK"
    }
} finally {
    Pop-Location
}
