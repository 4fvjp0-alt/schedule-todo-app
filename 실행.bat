@echo off
chcp 65001 >nul
echo.
echo ================================
echo   일정/할일 관리 앱 시작 중...
echo ================================
echo.

REM Get local IP
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /R "IPv4"') do (
  set IP=%%a
  goto :found
)
:found
set IP=%IP: =%

echo  PC 접속주소:     http://localhost:5000
echo  모바일 접속주소: http://%IP%:5000
echo.
echo  (모바일은 같은 WiFi에 연결되어 있어야 합니다)
echo  (종료하려면 이 창을 닫거나 Ctrl+C 를 누르세요)
echo.

start http://localhost:5000
C:\Users\4fvjp\AppData\Local\Programs\Python\Python312\python.exe "%~dp0app.py"
pause
