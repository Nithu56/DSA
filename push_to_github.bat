@echo off
setlocal
cd /d "%~dp0"

echo ==============================================
echo   Push the Event Scheduler project to GitHub
echo ==============================================
echo.

where git >nul 2>nul
if errorlevel 1 (
  echo Git was not found. Install Git for Windows, then run this helper again.
  pause
  exit /b 1
)

if not exist README.md (
  echo README.md is missing. Run this helper from the project folder.
  pause
  exit /b 1
)

git rev-parse --is-inside-work-tree >nul 2>nul
if errorlevel 1 (
  echo Setting up Git for this project...
  git init
  if errorlevel 1 goto failed
)

echo Adding the project files. Local schedule data and logs are ignored.
git add .gitignore README.md index.html style.css app.js dsa.py server.py run_windows.bat run_python_demo.bat push_to_github.bat tests
if errorlevel 1 goto failed

git diff --cached --quiet
if not errorlevel 1 goto no_changes

set /p COMMIT_MESSAGE=Commit message (Enter for "Update event scheduler"): 
if "%COMMIT_MESSAGE%"=="" set COMMIT_MESSAGE=Update event scheduler
git commit -m "%COMMIT_MESSAGE%"
if errorlevel 1 goto failed

git branch -M main
set /p REPO_URL=Paste your GitHub repository HTTPS URL: 
if "%REPO_URL%"=="" goto missing_url

git remote get-url origin >nul 2>nul
if errorlevel 1 (
  git remote add origin "%REPO_URL%"
) else (
  git remote set-url origin "%REPO_URL%"
)
if errorlevel 1 goto failed

echo.
echo Pushing the project to GitHub...
git push -u origin main
if errorlevel 1 goto failed

echo.
echo Done. Your project is on GitHub.
pause
exit /b 0

:no_changes
echo No new file changes to commit. Continuing to the GitHub push.
git branch -M main
set /p REPO_URL=Paste your GitHub repository HTTPS URL: 
if "%REPO_URL%"=="" goto missing_url
git remote get-url origin >nul 2>nul
if errorlevel 1 (
  git remote add origin "%REPO_URL%"
) else (
  git remote set-url origin "%REPO_URL%"
)
if errorlevel 1 goto failed
git push -u origin main
if errorlevel 1 goto failed
echo.
echo Done. Your project is on GitHub.
pause
exit /b 0

:missing_url
echo No repository URL was entered. Nothing was pushed.
pause
exit /b 1

:failed
echo.
echo Git reported an error. Check the message above and try again.
echo If GitHub asks you to sign in, complete the sign-in and rerun this helper.
pause
exit /b 1
