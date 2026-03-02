# Codebase Merger GUI

## 실행 방법

### 방법 1: Python으로 바로 실행
```
pip install customtkinter pyperclip
python codebase_merger_app.py
```

### 방법 2: .exe로 빌드 (Windows)
```
build.bat 더블클릭
→ dist/CodebaseMerger.exe 생성됨
```

## 기능 설명

| 기능 | 설명 |
|------|------|
| SOURCE FOLDER | 병합할 Python 프로젝트 폴더 선택 |
| OUTPUT FOLDER | .txt 파일을 저장할 폴더 선택 |
| FILENAME | 저장될 파일명 (기본: merged_codebase.txt) |
| ▶ RUN MERGE | 실행 - 로그가 실시간으로 출력됨 |
| HISTORY 클릭 | 해당 병합 결과를 클립보드에 복사 (파일 없어도 OK) |
| 캐시 삭제 | 최근 1개만 남기고 캐시 파일 전체 삭제 |

## 캐시 위치
`C:\Users\{사용자}\\.codebase_merger\cache\`

## 주의사항
- HISTORY 항목 클릭 시 파일 내용이 클립보드에 복사됩니다
- "캐시 삭제" 버튼을 누르면 오래된 캐시는 지워지지만 마지막 실행 파일은 유지됩니다
- 실제 저장 파일은 OUTPUT FOLDER에 별도로 저장됩니다