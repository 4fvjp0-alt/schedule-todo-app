@echo off
chcp 65001 >nul
echo.
echo ========================================
echo  GitHub 업로드 (Render 배포 준비)
echo ========================================
echo.

cd /d "%~dp0"

echo [1/4] Git 저장소 초기화 중...
git init
git add .
git commit -m "초기 커밋: 일정/할일 관리 앱"

echo.
echo ========================================
echo  GitHub 사용자명을 입력하세요.
echo  (github.com 로그인 아이디)
echo ========================================
set /p USERNAME="GitHub 사용자명: "

echo.
echo [2/4] GitHub 저장소 연결 중...
git remote add origin https://github.com/%USERNAME%/schedule-todo-app.git
git branch -M main

echo.
echo [3/4] GitHub에 업로드 중...
echo (GitHub 로그인 창이 뜨면 로그인하세요)
echo.
git push -u origin main

echo.
if %ERRORLEVEL%==0 (
  echo ========================================
  echo  [완료] 업로드 성공!
  echo.
  echo  저장소 주소:
  echo  https://github.com/%USERNAME%/schedule-todo-app
  echo.
  echo  이제 render.com 에서 이 저장소를 배포하세요.
  echo ========================================
) else (
  echo ========================================
  echo  [오류] 업로드 실패했습니다.
  echo.
  echo  확인사항:
  echo  1. github.com 에서 'schedule-todo-app'
  echo     이름의 저장소를 먼저 만들었나요?
  echo  2. GitHub 사용자명이 정확한가요?
  echo ========================================
)
echo.
pause
