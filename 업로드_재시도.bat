@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo.

echo [1] 현재 상태 확인 중...
git status
echo.

echo [2] 파일 추가 및 커밋...
git add .
git commit -m "초기 커밋: 일정/할일 관리 앱"
echo.

echo [3] 브랜치를 main 으로 설정...
git branch -M main
echo.

echo [4] GitHub 업로드...
git push -u origin main --force
echo.

if %ERRORLEVEL%==0 (
  echo [완료] 업로드 성공!
) else (
  echo [오류] 실패. 아래 내용을 복사해서 알려주세요:
  git log --oneline -5
  git branch
)
echo.
pause
