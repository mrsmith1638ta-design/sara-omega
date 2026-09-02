@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\railway-consume-verified-build.ps1" %*
exit /b %ERRORLEVEL%
