$ErrorActionPreference = 'Stop'
$raizProjeto = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$pythonBuild = Join-Path $raizProjeto '.venv/Scripts/python.exe'
Push-Location -LiteralPath $raizProjeto
try {
    # O runtime usado no build carrega este recurso junto ao módulo ssl.
    # Preservar a política TLS original também no executável portátil.
    $recursoSsl = & $pythonBuild -c "import ssl; from pathlib import Path; print(Path(ssl.__file__).with_name('codex-rejected-cas.pem'))"
    $dadosSsl = @()
    if (Test-Path -LiteralPath $recursoSsl) { $dadosSsl = @('--add-data', ($recursoSsl + ';.')) }
    & $pythonBuild -m PyInstaller --noconfirm --onedir --windowed `
        --name SimuladorCredito --icon (Join-Path $raizProjeto 'assets/icon.ico') `
        --paths . --distpath dist/rede --workpath build/rede --specpath build `
        --add-data ((Join-Path $raizProjeto 'src/web') + ';src/web') --add-data ((Join-Path $raizProjeto 'modelo.yaml') + ';.') `
        --collect-all eel --hidden-import sqlalchemy.sql.default_comparator `
        @dadosSsl compartilhamento/entrada_portatil.py
    if ($LASTEXITCODE -ne 0) { throw 'Falha no empacotamento portátil.' }
    Write-Host (Join-Path $raizProjeto 'dist/rede/SimuladorCredito')
} finally { Pop-Location }
