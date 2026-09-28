; Script de Inno Setup para generar KakeiboSetup.exe.
; Requiere haber generado antes build\windows con `flet build windows` (ver
; README.md, seccion "Empaquetado"). Se usa flet build (no flet pack) porque
; ese motor no depende de Windows Media Foundation (MFReadWrite.dll), que en
; algunas ediciones de Windows no viene instalado por defecto.
;
; Compilar con:
;   "C:\Users\<usuario>\AppData\Local\Programs\Inno Setup 6\ISCC.exe" packaging\kakeibo.iss

#define MyAppName "Kakeibo"
#define MyAppVersion "1.0.1"
#define MyAppPublisher "Kakeibo"
#define MyAppExeName "Kakeibo.exe"

[Setup]
AppId={{6F1B0D9B-6E9B-4E9A-8B8B-1A6B7B4B4F0E}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableDirPage=yes
DisableProgramGroupPage=yes
DisableReadyPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\installer
OutputBaseFilename=KakeiboSetup
Compression=lzma2
SolidCompression=yes
UninstallDisplayIcon={app}\{#MyAppExeName}
SetupIconFile=..\assets\icon.ico
WizardStyle=modern

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "Crear un ícono en el Escritorio"; GroupDescription: "Íconos adicionales:"; Flags: checkedonce

[Files]
Source: "..\build\windows\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Abrir {#MyAppName}"; Flags: nowait postinstall skipifsilent
