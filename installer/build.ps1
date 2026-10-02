param(
    [string]$InnoCompiler = ''
)

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$appExe = Join-Path $repoRoot 'dist\Operations_Credit_v2.1.0.exe'

Push-Location $repoRoot
try {
    & python -m PyInstaller --noconfirm --onefile --windowed `
        --name Operations_Credit_v2.1.0 `
        --icon assets/icon.ico `
        --add-data 'src/web;src/web' `
        --add-data 'modelo.yaml;.' `
        app.py
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $appExe)) {
        throw 'A geração do executável falhou.'
    }

    if (-not $InnoCompiler) {
        $command = Get-Command ISCC.exe -ErrorAction SilentlyContinue
        if ($command) { $InnoCompiler = $command.Source }
    }
    if (-not $InnoCompiler) {
        foreach ($candidate in @(
            'C:\Program Files (x86)\Inno Setup 6\ISCC.exe',
            'C:\Program Files\Inno Setup 6\ISCC.exe',
            'C:\Program Files (x86)\Inno Setup 7\ISCC.exe',
            'C:\Program Files\Inno Setup 7\ISCC.exe'
        )) {
            if (Test-Path -LiteralPath $candidate) { $InnoCompiler = $candidate; break }
        }
    }
    if (-not $InnoCompiler -or -not (Test-Path -LiteralPath $InnoCompiler)) {
        throw "Executável atualizado em $appExe. Para gerar o instalador, instale Inno Setup e execute este script novamente, ou informe -InnoCompiler com o caminho de ISCC.exe."
    }

    & $InnoCompiler (Join-Path $PSScriptRoot 'SimuladorOperacoesCredito.iss')
    if ($LASTEXITCODE -ne 0) { throw 'A compilação do instalador falhou.' }
    Write-Host (Join-Path $PSScriptRoot 'output\SimuladorOperacoesCredito-Setup-2.1.0.exe')
}
finally {
    Pop-Location
}
