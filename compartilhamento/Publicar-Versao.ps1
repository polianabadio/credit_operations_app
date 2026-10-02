param(
    [Parameter(Mandatory = $true)]
    [string]$PastaCompartilhada,
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^\d+\.\d+\.\d+$')]
    [string]$Versao
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

New-Item -ItemType Directory -Path $destino -Force | Out-Null
try {
    foreach ($arquivo in @('app.py', 'modelo.yaml', 'requirements-runtime.txt')) {
        Copy-Item -LiteralPath (Join-Path $origem $arquivo) -Destination $destino -ErrorAction Stop
    }
    Copy-Item -LiteralPath (Join-Path $origem 'src') -Destination (Join-Path $destino 'src') -Recurse -ErrorAction Stop
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'Iniciar-Simulador.ps1') -Destination (Join-Path $raiz 'Iniciar-Simulador.ps1') -Force
    Set-Content -LiteralPath (Join-Path $destino 'pronta.txt') -Value $Versao -Encoding UTF8
    Set-Content -LiteralPath (Join-Path $raiz 'versao-atual.txt') -Value $Versao -Encoding ASCII
    Write-Host "Versão $Versao publicada em $destino"
    Write-Host 'A equipe receberá a versão ao fechar e abrir o atalho novamente.'
} catch {
    Write-Error "Publicação incompleta. O marcador versao-atual.txt não foi alterado. Detalhe: $_"
    exit 1
}
