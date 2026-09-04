@echo off
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0SARA_OMEGA_Integrated_Completion_Campaign_RESUME.ps1" %*
set EXITCODE=%ERRORLEVEL%
echo.
if "%EXITCODE%"=="0" (
  echo SARA OMEGA resume completed successfully.
) else (
  echo SARA OMEGA resume finished with status code %EXITCODE%. Review the resume report under completion\campaign-20260903-170559\resume-reports.
)
exit /b %EXITCODE%
