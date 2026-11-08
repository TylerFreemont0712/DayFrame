Unicode True
!include "MUI2.nsh"
Name "DayFrame"
OutFile "..\dist\DayFrame-Setup-0.6.0.exe"
InstallDir "$LOCALAPPDATA\Programs\DayFrame"
RequestExecutionLevel user
SetCompressor /SOLID lzma
!define MUI_ICON "..\assets\DayFrame.ico"
!define MUI_UNICON "..\assets\DayFrame.ico"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "English"

Section "DayFrame"
  SetShellVarContext current
  SetOutPath "$INSTDIR"
  File /r "..\dist\DayFrame\*"
  WriteUninstaller "$INSTDIR\Uninstall.exe"
  CreateDirectory "$SMPROGRAMS\DayFrame"
  CreateShortcut "$SMPROGRAMS\DayFrame\DayFrame.lnk" "$INSTDIR\DayFrame.exe"
  CreateShortcut "$SMPROGRAMS\DayFrame\Uninstall.lnk" "$INSTDIR\Uninstall.exe"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\DayFrame" "DisplayName" "DayFrame"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\DayFrame" "DisplayVersion" "0.6.0"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\DayFrame" "UninstallString" '"$INSTDIR\Uninstall.exe"'
  WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\DayFrame" "NoModify" 1
  WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\DayFrame" "NoRepair" 1
SectionEnd

Section "Uninstall"
  SetShellVarContext current
  !include "uninstall-files.nsh"
  Delete "$INSTDIR\Uninstall.exe"
  RMDir "$INSTDIR"
  Delete "$SMPROGRAMS\DayFrame\DayFrame.lnk"
  Delete "$SMPROGRAMS\DayFrame\Uninstall.lnk"
  RMDir "$SMPROGRAMS\DayFrame"
  DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\DayFrame"
SectionEnd
