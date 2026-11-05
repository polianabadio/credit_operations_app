param([switch]$SemConsole, [switch]$VerificarDistribuicao)
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
        $runtimeOrigem = Join-Path $origem 'runtime'
        if (Test-Path -LiteralPath $runtimeOrigem) {
            $runtimeLocal = Join-Path $destino 'runtime'
            New-Item -ItemType Directory -Path $runtimeLocal -Force | Out-Null
            Get-ChildItem -LiteralPath $runtimeOrigem | ForEach-Object {
                Copy-Item -LiteralPath $_.FullName -Destination $runtimeLocal -Recurse -Force
            }
        }
        Set-Content -LiteralPath (Join-Path $destino 'pronta.txt') -Value $versao -Encoding ASCII
    }

    $env:SIMULADOR_DATA_DIR = $dados
    $cacheCompartilhado = Join-Path $raiz 'cache'
    New-Item -ItemType Directory -Path $cacheCompartilhado -Force | Out-Null
    $env:SIMULADOR_CACHE_DIR = $cacheCompartilhado
    $env:SIMULADOR_RELEASE_ROOT = $raiz
    $env:SIMULADOR_RELEASE_VERSION = $versao
    Set-Location -LiteralPath $destino
    $executavelPortatil = Join-Path $destino 'runtime/SimuladorCredito.exe'
    if (Test-Path -LiteralPath $executavelPortatil) {
        $opcoesProcesso = @{FilePath=$executavelPortatil; WorkingDirectory=$destino; WindowStyle='Hidden'; Wait=$true; PassThru=$true}
        if ($VerificarDistribuicao) { $opcoesProcesso.ArgumentList = '--verificar-distribuicao' }
        $processoSimulador = Start-Process @opcoesProcesso
        if ($processoSimulador.ExitCode -ne 0) { throw "O simulador terminou com código $($processoSimulador.ExitCode)." }
    } else {
        $venv = Join-Path $local 'venv'
        $python = Join-Path $venv 'Scripts\python.exe'
        if (-not (Test-Path -LiteralPath $python)) {
            & py -3.12 -m venv $venv
            if ($LASTEXITCODE -ne 0) { throw 'Python 3.12 não está instalado. Instale-o e abra o atalho novamente.' }
        }
        $marcadorPacotes = Join-Path $venv 'versao-pacotes.txt'
        if (-not (Test-Path -LiteralPath $marcadorPacotes) -or (Get-Content -LiteralPath $marcadorPacotes -Raw).Trim() -ne $versao) {
            & $python -m pip install -r (Join-Path $destino 'requirements-runtime.txt')
            if ($LASTEXITCODE -ne 0) { throw 'Não foi possível instalar as dependências do Python. Verifique a conexão com a internet ou procure o suporte de TI.' }
            Set-Content -LiteralPath $marcadorPacotes -Value $versao -Encoding ASCII
        }

        & $python (Join-Path $destino 'app.py')
        if ($LASTEXITCODE -ne 0) { throw "O simulador terminou com código $LASTEXITCODE." }
    }

} catch {
    if ($SemConsole) {
        Add-Type -AssemblyName System.Windows.Forms
        [System.Windows.Forms.MessageBox]::Show("Não foi possível abrir o simulador.`n`n$_", 'Simulador de Operações de Crédito', 'OK', 'Error') | Out-Null
        exit 1
    }
    Write-Host "Erro ao iniciar o simulador: $_" -ForegroundColor Red
    Read-Host 'Pressione Enter para fechar'
    exit 1
}
