; -- packaging/installer.iss --
; WordMem Windows 安装包脚本（Inno Setup 6，按用户级安装、免管理员权限）。
; 用法：ISCC.exe /DAPP_VERSION=1.0.0 packaging\installer.iss
; 产物：dist/WordMem-<版本>-setup.exe

#ifndef APP_VERSION
#define APP_VERSION "1.0.0"
#endif

#define APP_NAME "WordMem"
#define APP_PUBLISHER "WordMem Team"
#define APP_EXE "WordMem.exe"

[Setup]
AppId={{7A3D6F52-91C4-4E08-A2B6-3F5D8C1E9B07}
AppName={#APP_NAME}
AppVersion={#APP_VERSION}
AppPublisher={#APP_PUBLISHER}
DefaultDirName={localappdata}\Programs\{#APP_NAME}
DisableProgramGroupPage=yes
; 无中文语言文件时自动回退英文向导，不阻断编译
OutputDir=..\dist
OutputBaseFilename=WordMem-{#APP_VERSION}-setup
SetupIconFile=app.ico
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
UninstallDisplayIcon={app}\{#APP_EXE}
CloseApplications=yes
SetupLogging=yes

[Languages]
#if FileExists(AddBackslash(SourcePath) + "Languages\ChineseSimplified.isl")
Name: "chinesesimplified"; MessagesFile: "Languages\ChineseSimplified.isl"
#endif
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; \
    GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\WordMem\*"; DestDir: "{app}"; \
    Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#APP_NAME}"; Filename: "{app}\{#APP_EXE}"
Name: "{autodesktop}\{#APP_NAME}"; Filename: "{app}\{#APP_EXE}"; \
    Tasks: desktopicon

[Run]
Filename: "{app}\{#APP_EXE}"; Description: "{cm:LaunchProgram,{#APP_NAME}}"; \
    Flags: nowait postinstall skipifsilent
