@echo off
echo ====================================
echo  Codebase Merger - .exe 빌드 스크립트
echo ====================================
echo.

REM 필요 패키지 설치
echo [1/3] 패키지 설치 중...
pip install customtkinter pyperclip pyinstaller

echo.
echo [2/3] .exe 빌드 중... (약 1~3분 소요)

pyinstaller ^
  --onefile ^
  --windowed ^
  --name "CodebaseMerger" ^
  --icon NONE ^
  --add-data "%LOCALAPPDATA%\Programs\Python\Python312\Lib\site-packages\customtkinter;customtkinter" ^
  codebase_merger_app.py

echo.
echo [3/3] 완료!
echo.
echo   실행 파일 위치: dist\CodebaseMerger.exe
echo.

pause