$ErrorActionPreference = 'Stop'

try {
    $raiz = $PSScriptRoot
    $arquivoVersao = Join-Path $raiz 'versao-atual.txt'
    if (-not (Test-Path -LiteralPath $arquivoVersao)) {
        throw "Não encontrei versao-atual.txt em $raiz. Peça a publicação de uma versão."
    }
    $versao = (Get-Content -LiteralPath $arquivoVersao -Raw).Trim()
    if ($versao -notmatch '^\d+\.\d+\.\d+$') {
        throw "Número de versão inválido: $versao"
    }
    $origem = Join-Path (Join-Path $raiz 'versoes') $versao
    if (-not (Test-Path -LiteralPath (Join-Path $origem 'pronta.txt'))) {
        throw "A versão $versao ainda não terminou de ser publicada."
    }

    $local = Join-Path $env:LOCALAPPDATA 'SimuladorCredito'
    $destino = Join-Path (Join-Path $local 'versoes') $versao
    $dados = Join-Path $local 'dados'
    New-Item -ItemType Directory -Path $dados -Force | Out-Null
    if (-not (Test-Path -LiteralPath (Join-Path $destino 'pronta.txt'))) {
        New-Item -ItemType Directory -Path $destino -Force | Out-Null
        foreach ($arquivo in @('app.py', 'modelo.yaml', 'requirements-runtime.txt')) {
            Copy-Item -LiteralPath (Join-Path $origem $arquivo) -Destination $destino -Force
        }
        $srcLocal = Join-Path $destino 'src'
        New-Item -ItemType Directory -Path $srcLocal -Force | Out-Null
        Get-ChildItem -LiteralPath (Join-Path $origem 'src') | ForEach-Object {
            Copy-Item -LiteralPath $_.FullName -Destination $srcLocal -Recurse -Force
        }
        Set-Content -LiteralPath (Join-Path $destino 'pronta.txt') -Value $versao -Encoding ASCII
    }

    $venv = Join-Path $local 'venv'
    $python = Join-Path $venv 'Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $python)) {
        & py -3.13 -m venv $venv
        if ($LASTEXITCODE -ne 0) { throw 'Python 3.13 não está instalado. Instale-o e abra o atalho novamente.' }
    }
    $marcadorPacotes = Join-Path $venv 'versao-pacotes.txt'
    if (-not (Test-Path -LiteralPath $marcadorPacotes) -or (Get-Content -LiteralPath $marcadorPacotes -Raw).Trim() -ne $versao) {
        & $python -m pip install -r (Join-Path $destino 'requirements-runtime.txt')
        if ($LASTEXITCODE -ne 0) { throw 'Não foi possível instalar as dependências do Python. Verifique a conexão com a internet ou procure o suporte de TI.' }
        Set-Content -LiteralPath $marcadorPacotes -Value $versao -Encoding ASCII
    }

    $env:SIMULADOR_DATA_DIR = $dados
    Set-Location -LiteralPath $destino
    & $python (Join-Path $destino 'app.py')
    if ($LASTEXITCODE -ne 0) { throw "O simulador terminou com código $LASTEXITCODE." }
} catch {
    Write-Host "Erro ao iniciar o simulador: $_" -ForegroundColor Red
    Read-Host 'Pressione Enter para fechar'
    exit 1
}
