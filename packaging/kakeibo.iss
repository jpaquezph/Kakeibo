; Script de Inno Setup para generar KakeiboSetup.exe.
; Requiere haber generado antes build\windows con `flet build windows` (ver
; README.md, seccion "Empaquetado"). Se usa flet build (no flet pack) porque
; ese motor no depende de Windows Media Foundation (MFReadWrite.dll), que en
; algunas ediciones de Windows no viene instalado por defecto.
;
; Compilar con:
;   "C:\Users\<usuario>\AppData\Local\Programs\Inno Setup 6\ISCC.exe" packaging\kakeibo.iss

#define MyAppName "Kakeibo"
#define MyAppVersion "1.6.0"
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
; Al terminar de instalar/desinstalar avisa a Windows que refresque los iconos,
; para que el acceso directo no quede mostrando un icono viejo de la cache.
ChangesAssociations=yes

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

[Code]
{ El desinstalador solo borra lo que instalo. Lo que la app crea despues queda:
  la base (app\kakeibo.db, con TODOS los datos del usuario), los logs y la
  carpeta de datos de Flet en %APPDATA%\Kakeibo. Como incluye los datos, se
  pregunta antes de borrarlo; en una desinstalacion silenciosa no se borra. }
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
  begin
    { "Iniciar con Windows" (Configuracion > General): sin la app, la entrada
      de inicio quedaria apuntando a un ejecutable que ya no existe. }
    RegDeleteValue(HKEY_CURRENT_USER, 'Software\Microsoft\Windows\CurrentVersion\Run', '{#MyAppName}');
    if (not UninstallSilent) and
       (MsgBox('¿Querés borrar también tus datos de Kakeibo (usuarios, movimientos, tarjetas, ' +
               'inversiones y configuración)?' + #13#10#13#10 +
               'Si elegís Sí, se eliminan definitivamente y no se pueden recuperar. ' +
               'Si pensás volver a instalar Kakeibo, elegí No o hacé un backup antes.',
               mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES) then
    begin
      DelTree(ExpandConstant('{app}'), True, True, True);
      DelTree(ExpandConstant('{userappdata}\{#MyAppName}'), True, True, True);
    end;
  end;
end;
