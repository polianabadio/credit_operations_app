#define AppVersion "2.1.0"
#define AppExe "Operations_Credit_v2.1.0.exe"

[Setup]
AppId=SimuladorOperacoesCreditoGO
AppName=Simulador de Operações de Crédito
AppVersion={#AppVersion}
DefaultDirName={localappdata}\Programs\SimuladorOperacoesCredito
DefaultGroupName=Simulador de Operações de Crédito
PrivilegesRequired=lowest
OutputDir=output
OutputBaseFilename=SimuladorOperacoesCredito-Setup-{#AppVersion}
SetupIconFile=..\assets\icon.ico
UninstallDisplayIcon={app}\{#AppExe}
Compression=lzma
SolidCompression=yes
WizardStyle=modern

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na área de trabalho"; GroupDescription: "Atalhos adicionais:"

[Files]
Source: "..\dist\{#AppExe}"; DestDir: "{app}"; Flags: ignoreversion
Source: "settings.ini"; DestDir: "{app}"; Flags: onlyifdoesntexist uninsneveruninstall

[Icons]
Name: "{group}\Simulador de Operações de Crédito"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\Simulador de Operações de Crédito"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "Abrir Simulador de Operações de Crédito"; Flags: nowait postinstall skipifsilent
