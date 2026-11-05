param(
    [Parameter(Mandatory = $true)]
    [string]$PastaCompartilhada,
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^\d+\.\d+\.\d+$')]
    [string]$Versao,
    [string]$ExecutavelPortatil = ''
)

$ErrorActionPreference = 'Stop'
$origem = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$raiz = [System.IO.Path]::GetFullPath($PastaCompartilhada)
if (-not (Test-Path -LiteralPath $raiz -PathType Container)) {
    throw "A pasta compartilhada não existe ou não está acessível: $raiz"
}

$pastaVersoes = Join-Path $raiz 'versoes'
$destino = Join-Path $pastaVersoes $Versao
if (Test-Path -LiteralPath $destino) {
    throw "A versão $Versao já existe. Escolha outro número; versões publicadas não devem ser alteradas."
}

if (-not $ExecutavelPortatil) {
    & (Join-Path $PSScriptRoot 'Empacotar-Portatil.ps1')
    $ExecutavelPortatil = Join-Path $origem 'dist/rede/SimuladorCredito'
}
if (-not (Test-Path -LiteralPath (Join-Path $ExecutavelPortatil 'SimuladorCredito.exe'))) {
    throw 'A publicação exige o aplicativo portátil com Python e bibliotecas incluídos.'
}

New-Item -ItemType Directory -Path $destino -Force | Out-Null
try {
    foreach ($arquivo in @('app.py', 'modelo.yaml', 'requirements-runtime.txt', 'LICENSE.md')) {
        Copy-Item -LiteralPath (Join-Path $origem $arquivo) -Destination $destino -ErrorAction Stop
    }
    $origemSrc = Join-Path $origem 'src'
    Get-ChildItem -LiteralPath $origemSrc -Recurse -File | Where-Object {
        $_.FullName -notmatch '\\(__pycache__|\.pytest_cache|node_modules)\\' -and
        $_.Extension -notin @('.pyc', '.pyo', '.db', '.log')
    } | ForEach-Object {
        $relativo = $_.FullName.Substring($origemSrc.Length + 1)
        $arquivoDestino = Join-Path (Join-Path $destino 'src') $relativo
        New-Item -ItemType Directory -Path (Split-Path -Parent $arquivoDestino) -Force | Out-Null
        Copy-Item -LiteralPath $_.FullName -Destination $arquivoDestino -ErrorAction Stop
    }
    if ($ExecutavelPortatil) {
        if (-not (Test-Path -LiteralPath (Join-Path $ExecutavelPortatil 'SimuladorCredito.exe'))) { throw 'Executável portátil não encontrado.' }
        Copy-Item -LiteralPath $ExecutavelPortatil -Destination (Join-Path $destino 'runtime') -Recurse -Force
    }
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'Iniciar-Simulador.ps1') -Destination (Join-Path $raiz 'Iniciar-Simulador.ps1') -Force
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'Abrir-Simulador.cmd') -Destination (Join-Path $raiz 'Abrir-Simulador.cmd') -Force
    Copy-Item -LiteralPath (Join-Path $origem 'assets/icon.ico') -Destination (Join-Path $raiz 'Simulador.ico') -Force
    if (-not (Test-Path -LiteralPath (Join-Path $raiz 'Simulador de Crédito.lnk'))) {
        & (Join-Path $PSScriptRoot 'Criar-Atalho.ps1') -PastaCompartilhada $raiz -PastaDestino $raiz
    }
    Copy-Item -LiteralPath (Join-Path $origem 'docs\Compartilhar sem instalador.md') -Destination (Join-Path $raiz 'LEIA-ME.md') -Force
    Set-Content -LiteralPath (Join-Path $destino 'pronta.txt') -Value $Versao -Encoding UTF8
    Set-Content -LiteralPath (Join-Path $raiz 'versao-atual.txt') -Value $Versao -Encoding ASCII -Force
    # O atalho é a única entrada visível para a equipe.
    foreach ($nomeSuporte in @('cache', 'versoes', 'Abrir-Simulador.cmd', 'Iniciar-Simulador.ps1', 'LEIA-ME.md', 'Simulador.ico', 'versao-atual.txt')) {
        $itemSuporte = Get-Item -LiteralPath (Join-Path $raiz $nomeSuporte) -Force -ErrorAction SilentlyContinue
        if ($null -ne $itemSuporte) { $itemSuporte.Attributes = $itemSuporte.Attributes -bor [System.IO.FileAttributes]::Hidden }
    }
    Write-Host "Versão $Versao publicada em $destino"
    Write-Host 'A equipe receberá a versão ao fechar e abrir o atalho novamente.'
} catch {
    Write-Error "Publicação incompleta. O marcador versao-atual.txt não foi alterado. Detalhe: $_"
    exit 1
}
