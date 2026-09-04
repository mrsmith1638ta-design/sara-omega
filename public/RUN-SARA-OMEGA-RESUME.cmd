@echo off
setlocal
cd /d "%~dp0\.."
powershell -NoProfile -ExecutionPolicy Bypass -File "%CD%\SARA_OMEGA_Integrated_Completion_Campaign_RESUME.ps1" %*
exit /b %ERRORLEVEL%
