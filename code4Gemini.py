import os
import sys
import tkinter as tk
from tkinter import filedialog
from datetime import datetime

# ==============================
# 설정 영역
# ==============================

IGNORE_LIST = {
    ".git", ".svn", ".hg",
    "node_modules", "vendor", ".venv", "venv", "env", "__pycache__",
    "dist", "build", ".next", ".nuxt", "out", "target",
    ".idea", ".vscode", ".vs",
    ".DS_Store", "Thumbs.db", "$RECYCLE.BIN",
    ".cache", ".temp", ".tmp",
    ".gitignore", ".gitattributes", ".env", ".env.local",
}

OUTPUT_FILENAME = "merged_codebase.txt"
MAX_FILE_SIZE_MB = 10  # 너무 큰 파일 방지용 (원하면 None 처리)


# ==============================
# 유틸 함수
# ==============================

def is_ignored(name: str) -> bool:
    return name in IGNORE_LIST


def safe_read_file(filepath: str) -> str:
    """
    UTF-8 우선, 실패 시 fallback 시도
    """
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()
    except UnicodeDecodeError:
        try:
            with open(filepath, "r", encoding="cp949") as f:
                return f.read()
        except Exception as e:
            return f"# [ERROR] Encoding issue: {e}\n"
    except Exception as e:
        return f"# [ERROR] File read error: {e}\n"


# ==============================
# 트리 출력 + 수집
# ==============================

def build_tree_and_collect(path, prefix="", collected_files=None, visited=None):
    """
    - 트리 문자열 생성
    - 병합 대상 .py 파일 수집
    - 심볼릭 링크 루프 방지
    """
    if collected_files is None:
        collected_files = []

    if visited is None:
        visited = set()

    real_path = os.path.realpath(path)
    if real_path in visited:
        print(prefix + "⛔ [Symbolic Link Loop Detected]")
        return collected_files

    visited.add(real_path)

    try:
        entries = sorted(
            os.scandir(path),
            key=lambda e: (not e.is_dir(follow_symlinks=False), e.name.lower())
        )
    except PermissionError:
        print(prefix + "⛔ 접근 권한 없음")
        return collected_files

    entries = [e for e in entries if not is_ignored(e.name)]

    for i, entry in enumerate(entries):
        is_last = i == len(entries) - 1
        connector = "└── " if is_last else "├── "
        icon = "📁 " if entry.is_dir(follow_symlinks=False) else "📄 "
        print(prefix + connector + icon + entry.name)

        if entry.is_dir(follow_symlinks=False):
            extension = "    " if is_last else "│   "
            build_tree_and_collect(
                entry.path,
                prefix + extension,
                collected_files,
                visited
            )
        else:
            if entry.name.endswith(".py"):
                collected_files.append(entry.path)

    return collected_files


# ==============================
# 메인 로직
# ==============================

def main():
    root = tk.Tk()
    root.withdraw()

    folder_path = filedialog.askdirectory(title="병합할 폴더를 선택하세요")

    if not folder_path:
        print("폴더가 선택되지 않았습니다.")
        return

    folder_name = os.path.basename(folder_path)

    print(f"\n📂 {folder_path}")
    print(f"🚫 무시 목록: {', '.join(sorted(IGNORE_LIST))}\n")

    print(f"\n📂 {folder_name}")
    collected_files = build_tree_and_collect(folder_path)
    print("\n✅ 트리 출력 완료!")

    output_path = os.path.join(folder_path, OUTPUT_FILENAME)

    print(f"\n🔄 파일 병합 시작 ({len(collected_files)}개 .py 파일 발견)")

    try:
        with open(output_path, "w", encoding="utf-8") as outfile:
            # 헤더
            outfile.write("=" * 80 + "\n")
            outfile.write(f"MERGED CODEBASE\n")
            outfile.write(f"Generated: {datetime.now()}\n")
            outfile.write(f"Root Folder: {folder_path}\n")
            outfile.write("=" * 80 + "\n\n")

            # 폴더 구조도 같이 저장
            outfile.write("PROJECT STRUCTURE\n")
            outfile.write("=" * 80 + "\n\n")

            # 트리 재출력 (파일에 기록용)
            def write_tree(path, prefix=""):
                try:
                    entries = sorted(
                        os.scandir(path),
                        key=lambda e: (not e.is_dir(follow_symlinks=False), e.name.lower())
                    )
                except PermissionError:
                    outfile.write(prefix + "⛔ 접근 권한 없음\n")
                    return

                entries = [e for e in entries if not is_ignored(e.name)]

                for i, entry in enumerate(entries):
                    is_last = i == len(entries) - 1
                    connector = "└── " if is_last else "├── "
                    icon = "📁 " if entry.is_dir(follow_symlinks=False) else "📄 "
                    outfile.write(prefix + connector + icon + entry.name + "\n")

                    if entry.is_dir(follow_symlinks=False):
                        extension = "    " if is_last else "│   "
                        write_tree(entry.path, prefix + extension)

            write_tree(folder_path)

            outfile.write("\n\n")
            outfile.write("=" * 80 + "\n")
            outfile.write("PYTHON FILE CONTENTS\n")
            outfile.write("=" * 80 + "\n")

            # 파일 병합
            for filepath in sorted(collected_files):
                try:
                    if MAX_FILE_SIZE_MB:
                        size_mb = os.path.getsize(filepath) / (1024 * 1024)
                        if size_mb > MAX_FILE_SIZE_MB:
                            outfile.write(f"\n# [SKIPPED - TOO LARGE] {filepath}\n")
                            continue

                    outfile.write("\n\n" + "=" * 60 + "\n")
                    outfile.write(f"## FILE PATH: {filepath}\n")
                    outfile.write("=" * 60 + "\n\n")

                    content = safe_read_file(filepath)
                    outfile.write(content)

                except Exception as e:
                    outfile.write(f"\n# [ERROR] {filepath} - {e}\n")

        print(f"\n✅ 병합 완료: {output_path}")

    except Exception as e:
        print(f"❌ 출력 파일 생성 실패: {e}")


if __name__ == "__main__":
    main()