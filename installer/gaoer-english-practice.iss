#ifndef MyAppVersion
  #define MyAppVersion "0.1.0"
#endif

#define MyAppName "高二英语智能练习"
#define MyAppPublisher "Gaoer English Practice"
#define MyAppExeName "pythonw.exe"

[Setup]
AppId={{8D77E8F8-69E2-4AF4-9A6C-BB7E1E3BF111}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\GaoerEnglishPractice
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist\windows
OutputBaseFilename=GaoerEnglishPractice-Setup
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
UninstallDisplayName={#MyAppName}
CloseApplications=no
SetupLogging=yes

[Languages]
Name: "chinesesimp"; MessagesFile: "ChineseSimplified.isl"

[Files]
Source: "..\dist\windows\package\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{userdesktop}\{#MyAppName}"; Filename: "{app}\runtime\python\{#MyAppExeName}"; Parameters: """{app}\desktop\launcher.pyw"""; WorkingDir: "{app}"; IconFilename: "{app}\runtime\python\{#MyAppExeName}"
Name: "{group}\启动 {#MyAppName}"; Filename: "{app}\runtime\python\{#MyAppExeName}"; Parameters: """{app}\desktop\launcher.pyw"""; WorkingDir: "{app}"
Name: "{group}\停止服务"; Filename: "{app}\runtime\python\{#MyAppExeName}"; Parameters: """{app}\desktop\stop.pyw"""; WorkingDir: "{app}"
Name: "{group}\卸载 {#MyAppName}"; Filename: "{uninstallexe}"

[Run]
Filename: "{app}\runtime\python\{#MyAppExeName}"; Parameters: """{app}\desktop\launcher.pyw"""; WorkingDir: "{app}"; Description: "启动 {#MyAppName}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{app}\runtime\python\{#MyAppExeName}"; Parameters: """{app}\desktop\stop.pyw"""; WorkingDir: "{app}"; Flags: runhidden waituntilterminated; RunOnceId: "StopGaoerEnglishPractice"

[UninstallDelete]
Type: filesandordirs; Name: "{app}"
