; Inno Setup 6 — یک فایل نصب واحد: NatiqStudio_Setup.exe
[Setup]
AppName=Natiq Studio
AppVersion=1.0
AppPublisher=Natiq
DefaultDirName={autopf}\NatiqStudio
DefaultGroupName=Natiq Studio
OutputDir=installer_out
OutputBaseFilename=NatiqStudio_Setup
Compression=lzma2/fast
SolidCompression=no
ArchitecturesInstallIn64BitMode=x64compatible
ArchitecturesAllowed=x64compatible
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
WizardStyle=modern
UninstallDisplayIcon={app}\NatiqStudio.exe

[Files]
Source: "dist\NatiqStudio\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion createallsubdirs

[Icons]
Name: "{group}\Natiq Studio"; Filename: "{app}\NatiqStudio.exe"
Name: "{autodesktop}\Natiq Studio"; Filename: "{app}\NatiqStudio.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "ساخت میان‌بر روی دسکتاپ"; Flags: checkedonce

[Run]
Filename: "{app}\NatiqStudio.exe"; Description: "اجرای Natiq Studio"; Flags: nowait postinstall skipifsilent
