#define MyAppName "FAMD Tool ni Yeol"
#define MyAppPublisher "FAMD"
#define MyAppExeName "FAMDTool.exe"

#ifndef MyAppVersion
#define MyAppVersion "1.5.1"
#endif

[Setup]
AppId={{12D74A5A-A821-4C7E-9D95-91F42B69017D}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\FAMDTool
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\release
OutputBaseFilename=FAMDTool-v{#MyAppVersion}-windows-setup
SetupIconFile=..\assets\FAMDTool.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"; Flags: unchecked

[Files]
Source: "..\dist\FAMDTool\FAMDTool.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\FAMDTool\_internal\*"; DestDir: "{app}\_internal"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\dist\FAMDTool\assets\*"; DestDir: "{app}\assets"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\dist\FAMDTool\README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\FAMDTool\config.cfg"; DestDir: "{app}"; Flags: onlyifdoesntexist

[Dirs]
Name: "{app}\attachments"
Name: "{app}\exports"
Name: "{app}\logs"

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent
