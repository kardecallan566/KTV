; Inno Setup script for KTV App
#define AppName "KTV App"
#define AppVersion "0.1.0"
#define AppPublisher "KTV"
#define AppExeName "KTV-App.exe"

[Setup]
AppId={{A8B54A6D-64D8-4E57-A5C9-0E5C9A91D201}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\KTV App
DefaultGroupName={#AppName}
OutputDir=installer-output
OutputBaseFilename=KTV-App-Setup
ArchitecturesInstallIn64BitMode=x64
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
UninstallDisplayIcon={app}\{#AppExeName}

[Files]
Source: "..\dist\KTV-App\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{group}\KTV App"; Filename: "{app}\{#AppExeName}"
Name: "{autodesktop}\KTV App"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na área de trabalho"; GroupDescription: "Atalhos:"; Flags: unchecked

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Abrir KTV App"; Flags: postinstall nowait skipifsilent
