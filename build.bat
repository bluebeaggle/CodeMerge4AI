@echo off
setlocal

echo ====================================
echo  Codebase Merger - .exe 빌드 스크립트
echo ====================================
echo.

echo [1/4] 가상환경 생성 중...
python -m venv build_env
if errorlevel 1 (
    echo [ERROR] 가상환경 생성 실패. Python이 설치되어 있는지 확인하세요.
    goto CLEANUP
)
echo     완료.
echo.

echo [2/4] 패키지 설치 중 (requirements.txt)...
build_env\Scripts\pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo [ERROR] 패키지 설치 실패.
    goto CLEANUP
)
echo     완료.
echo.

echo [3/4] .exe 빌드 중... (약 1~3분 소요)

for /f "delims=" %%i in ('build_env\Scripts\python -c "import customtkinter, os; print(os.path.dirname(customtkinter.__file__))"') do set CTK_PATH=%%i
echo     customtkinter 경로: %CTK_PATH%
echo.

build_env\Scripts\pyinstaller ^
  --onefile ^
  --windowed ^
  --name "CodebaseMerger" ^
  --add-data "%CTK_PATH%;customtkinter" ^
  --noconfirm ^
  codebase_merger_app.py

echo.
if exist dist\CodebaseMerger.exe (
    echo [SUCCESS] 빌드 성공!
    echo    실행 파일 위치: dist\CodebaseMerger.exe
) else (
    echo [FAILED] 빌드 실패. 위 로그를 확인해주세요.
)

:CLEANUP
echo.
echo [4/4] 가상환경 삭제 중...
if exist build_env (
    rmdir /s /q build_env
    echo     삭제 완료.
) else (
    echo     가상환경 없음. 스킵.
)

echo.
echo ====================================
echo  완료
echo ====================================
echo.
pause
endlocal