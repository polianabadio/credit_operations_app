param(
    [Parameter(Mandatory = $true)][string]$PastaCompartilhada,
    [Parameter(Mandatory = $true)][string]$PastaDestino
)
$ErrorActionPreference = 'Stop'
$raiz = [System.IO.Path]::GetFullPath($PastaCompartilhada)
$inicializador = Join-Path $raiz 'Iniciar-Simulador.ps1'
if (-not (Test-Path -LiteralPath $inicializador)) { throw 'Inicializador não encontrado.' }
$shellAtalho = New-Object -ComObject WScript.Shell
$caminhoAtalho = Join-Path $PastaDestino 'Simulador de Crédito.lnk'
if (Test-Path -LiteralPath $caminhoAtalho) { throw "Já existe um atalho: $caminhoAtalho" }
$atalho = $shellAtalho.CreateShortcut($caminhoAtalho)
$atalho.TargetPath = Join-Path $env:SystemRoot 'System32/WindowsPowerShell/v1.0/powershell.exe'
$atalho.Arguments = '-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "' + $inicializador + '" -SemConsole'
$atalho.WorkingDirectory = $raiz
$atalho.IconLocation = (Join-Path $raiz 'Simulador.ico') + ',0'
$atalho.Description = 'Simulador de Operações de Crédito — Estado de Goiás'
$atalho.WindowStyle = 7
$atalho.Save()
Write-Host "Atalho criado: $caminhoAtalho"
