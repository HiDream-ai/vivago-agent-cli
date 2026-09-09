@echo off
setlocal
set "ARCH=%PROCESSOR_ARCHITECTURE%"
if /I "%PROCESSOR_ARCHITEW6432%"=="ARM64" set "ARCH=ARM64"
if /I "%PROCESSOR_ARCHITEW6432%"=="AMD64" set "ARCH=AMD64"
if /I "%ARCH%"=="ARM64" set "TARGET=windows-arm64"
if /I "%ARCH%"=="AMD64" set "TARGET=windows-amd64"
if not defined TARGET (
  echo {"ok":false,"data":null,"error":{"code":"UNSUPPORTED_PLATFORM","message":"No bundled VivagoAgent binary matches this CPU architecture."}}
  exit /b 40
)
set "BINARY=%~dp0..\..\..\bin\%TARGET%\vivago-agent.exe"
if not exist "%BINARY%" (
  echo {"ok":false,"data":null,"error":{"code":"PLUGIN_RUNTIME_MISSING","message":"The bundled VivagoAgent binary is missing; reinstall the plugin."}}
  exit /b 40
)
"%BINARY%" %*
exit /b %ERRORLEVEL%
