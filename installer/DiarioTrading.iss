; Instalador por usuario (sin permisos de administrador). Compilar con: iscc /DAppVersion=0.2.0 installer\DiarioTrading.iss
#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{6B1D2C5E-8F43-4A7B-9E1A-3D5C7A9B2E10}
AppName=Diario de Trading
AppVersion={#AppVersion}
AppPublisher=Diario de Trading
DefaultDirName={localappdata}\Programs\DiarioTrading
DefaultGroupName=Diario de Trading
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=DiarioTrading-Setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
DisableProgramGroupPage=yes
UninstallDisplayName=Diario de Trading
CloseApplications=yes

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "Crear un acceso directo en el escritorio"; GroupDescription: "Accesos directos:"

[Files]
Source: "..\dist\DiarioTrading.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\Diario de Trading"; Filename: "{app}\DiarioTrading.exe"
Name: "{autodesktop}\Diario de Trading"; Filename: "{app}\DiarioTrading.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\DiarioTrading.exe"; Description: "Abrir Diario de Trading"; Flags: nowait postinstall skipifsilent

; Los datos viven en %APPDATA%\DiarioTrading\datos y no se borran al desinstalar ni al actualizar.
