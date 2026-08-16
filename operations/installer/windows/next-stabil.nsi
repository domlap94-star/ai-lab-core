!include "MUI2.nsh"

!define APP_NAME "NEXT Stabil"
!define APP_VERSION "1.0.2"
!define APP_BUILD "8"
!define APP_PUBLISHER "NEXT Stabil"
!define APP_EXE "frontend.exe"
!define APP_ID "NEXTStabil"

Name "${APP_NAME}"
OutFile "C:\ai-lab-core\release-channel\stable\windows\NEXT-Stabil-Setup-1.0.2+8.exe"
InstallDir "$LOCALAPPDATA\Programs\NEXT Stabil"
RequestExecutionLevel user
Unicode true
SetCompressor /SOLID lzma

VIProductVersion "1.0.2.8"
VIAddVersionKey "ProductName" "${APP_NAME}"
VIAddVersionKey "ProductVersion" "${APP_VERSION}"
VIAddVersionKey "CompanyName" "${APP_PUBLISHER}"
VIAddVersionKey "FileDescription" "NEXT Stabil Windows Installer"
VIAddVersionKey "FileVersion" "1.0.2.8"

!define MUI_ABORTWARNING

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_UNPAGE_FINISH

!insertmacro MUI_LANGUAGE "Polish"
!insertmacro MUI_LANGUAGE "English"

Section "NEXT Stabil" SEC_MAIN
  SetOutPath "$INSTDIR"
  File /r "C:\ai-lab-core\frontend\build\windows\x64\runner\Release\*.*"
  WriteUninstaller "$INSTDIR\Uninstall.exe"

  CreateDirectory "$SMPROGRAMS\NEXT Stabil"
  CreateShortcut "$SMPROGRAMS\NEXT Stabil\NEXT Stabil.lnk" "$INSTDIR\${APP_EXE}"
  CreateShortcut "$DESKTOP\NEXT Stabil.lnk" "$INSTDIR\${APP_EXE}"

  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_ID}" "DisplayName" "${APP_NAME}"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_ID}" "DisplayVersion" "${APP_VERSION}"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_ID}" "Publisher" "${APP_PUBLISHER}"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_ID}" "InstallLocation" "$INSTDIR"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_ID}" "UninstallString" '"$INSTDIR\Uninstall.exe"'
  WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_ID}" "NoModify" 1
  WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_ID}" "NoRepair" 1
SectionEnd

Section "Uninstall"
  Delete "$DESKTOP\NEXT Stabil.lnk"
  Delete "$SMPROGRAMS\NEXT Stabil\NEXT Stabil.lnk"
  RMDir "$SMPROGRAMS\NEXT Stabil"
  DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_ID}"
  RMDir /r "$INSTDIR"
SectionEnd
