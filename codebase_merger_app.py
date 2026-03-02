import os
import sys
import json
import shutil
import threading
import subprocess
import tkinter as tk
from tkinter import filedialog, messagebox
from datetime import datetime
import customtkinter as ctk
import pyperclip

# ─── 설정 ────────────────────────────────────────────────────────────────────

IGNORE_LIST = {
    ".git", ".svn", ".hg",
    "node_modules", "vendor", ".venv", "venv", "env", "__pycache__",
    "dist", "build", ".next", ".nuxt", "out", "target",
    ".idea", ".vscode", ".vs",
    ".DS_Store", "Thumbs.db", "$RECYCLE.BIN",
    ".cache", ".temp", ".tmp",
    ".gitignore", ".gitattributes", ".env", ".env.local",
}
MAX_FILE_SIZE_MB = 10


INCLUDE_EXTENSIONS = {
    ".py",      # backend
    ".js",      # frontend
    ".html",
    ".css",
    ".c",
    ".h",
    ".cpp",
    ".hpp",
    ".java",
    ".kt",
    ".rs",
    ".go",
    ".swift",
    ".php",
    ".rb",
    ".ts",
    ".tsx",
    ".vue",
}


CACHE_DIR = os.path.join(os.path.expanduser("~"), ".codebase_merger", "cache")
HISTORY_FILE = os.path.join(os.path.expanduser("~"), ".codebase_merger", "history.json")
os.makedirs(CACHE_DIR, exist_ok=True)

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


# ─── 유틸 ────────────────────────────────────────────────────────────────────

def is_ignored(name):
    return name in IGNORE_LIST


def safe_read_file(filepath):
    for enc in ("utf-8", "cp949"):
        try:
            with open(filepath, "r", encoding=enc) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
        except Exception as e:
            return f"# [ERROR] {e}\n"
    return "# [ERROR] Could not decode file\n"


def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def save_history(history):
    os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


# ─── 코어 로직 ────────────────────────────────────────────────────────────────

def build_tree_lines(path, prefix="", visited=None):
    if visited is None:
        visited = set()
    real_path = os.path.realpath(path)
    if real_path in visited:
        return ["[Symbolic Link Loop]"]
    visited.add(real_path)
    lines = []
    try:
        entries = sorted(
            os.scandir(path),
            key=lambda e: (not e.is_dir(follow_symlinks=False), e.name.lower())
        )
    except PermissionError:
        return [prefix + "⛔ 접근 권한 없음"]
    entries = [e for e in entries if not is_ignored(e.name)]
    for i, entry in enumerate(entries):
        is_last = i == len(entries) - 1
        connector = "└── " if is_last else "├── "
        icon = "📁 " if entry.is_dir(follow_symlinks=False) else "📄 "
        lines.append(prefix + connector + icon + entry.name)
        if entry.is_dir(follow_symlinks=False):
            ext = "    " if is_last else "│   "
            lines.extend(build_tree_lines(entry.path, prefix + ext, visited))
    return lines


def collect_py_files(path, visited=None):
    if visited is None:
        visited = set()
    real_path = os.path.realpath(path)
    if real_path in visited:
        return []
    visited.add(real_path)
    files = []
    try:
        entries = sorted(os.scandir(path), key=lambda e: e.name.lower())
    except PermissionError:
        return []
    for entry in entries:
        if is_ignored(entry.name):
            continue
        if entry.is_dir(follow_symlinks=False):
            files.extend(collect_py_files(entry.path, visited))
        else:
            ext = os.path.splitext(entry.name)[1].lower()
            if ext in INCLUDE_EXTENSIONS:
                files.append(entry.path)

    return files


def merge_codebase(folder_path, output_path, log_fn, mode="full"):
    folder_name = os.path.basename(folder_path)
    log_fn(f"📂 폴더: {folder_path}")
    log_fn(f"🚫 무시 목록: {', '.join(sorted(IGNORE_LIST))}\n")
    log_fn(f"⚙️  모드: {'전체 내용' if mode == 'full' else '폴더 구조만'}\n")

    tree_lines = build_tree_lines(folder_path)
    log_fn(f"📂 {folder_name}")
    for line in tree_lines:
        log_fn(line)
    log_fn("\n✅ 트리 출력 완료!")

    with open(output_path, "w", encoding="utf-8") as out:
        out.write("=" * 80 + "\n")
        out.write("MERGED CODEBASE\n")
        out.write(f"Generated: {datetime.now()}\n")
        out.write(f"Root Folder: {folder_path}\n")
        out.write(f"Mode: {'Full Content' if mode == 'full' else 'Tree Only'}\n")
        out.write("=" * 80 + "\n\n")
        out.write("PROJECT STRUCTURE\n")
        out.write("=" * 80 + "\n\n")
        out.write(f"📂 {folder_name}\n")
        for line in tree_lines:
            out.write(line + "\n")
        out.write("\n\n")

        if mode == "tree":
            log_fn("\n✅ 폴더 구조 저장 완료!")
        else:
            py_files = collect_py_files(folder_path)
            log_fn(f"\n🔄 파일 병합 시작 ({len(py_files)}개 파일 발견)")

            out.write("=" * 80 + "\n")
            out.write("FILE CONTENTS\n")
            out.write("=" * 80 + "\n")

            for filepath in sorted(py_files):
                if MAX_FILE_SIZE_MB:
                    size_mb = os.path.getsize(filepath) / (1024 * 1024)
                    if size_mb > MAX_FILE_SIZE_MB:
                        out.write(f"\n# [SKIPPED - TOO LARGE] {filepath}\n")
                        log_fn(f"⚠️ 스킵 (너무 큰 파일): {filepath}")
                        continue
                out.write("\n\n" + "=" * 60 + "\n")
                out.write(f"## FILE PATH: {filepath}\n")
                out.write("=" * 60 + "\n\n")
                out.write(safe_read_file(filepath))
                log_fn(f"  ✓ {os.path.relpath(filepath, folder_path)}")

            log_fn(f"\n✅ 병합 완료!")


# ─── GUI ──────────────────────────────────────────────────────────────────────

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Codebase Merger")
        self.geometry("1100x700")
        self.minsize(900, 600)
        self.configure(fg_color="#0f0f13")
        self._history = load_history()
        self._mode_var = tk.StringVar(value="full")  # "full" | "tree"
        self._build_ui()
        self._refresh_history()

    # ── UI 빌드 ───────────────────────────────────────────────────────────────

    def _build_ui(self):
        # 메인 레이아웃: 좌(설정+로그) / 우(히스토리)
        self.grid_columnconfigure(0, weight=3)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ── 왼쪽 패널 ───────────────────────────────────────────────────────
        left = ctk.CTkFrame(self, fg_color="#14141c", corner_radius=0)
        left.grid(row=0, column=0, sticky="nsew", padx=(12, 6), pady=12)
        left.grid_rowconfigure(1, weight=1)
        left.grid_columnconfigure(0, weight=1)

        # 제목
        title_frame = ctk.CTkFrame(left, fg_color="transparent")
        title_frame.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 10))

        ctk.CTkLabel(
            title_frame, text="⚡ CODEBASE",
            font=ctk.CTkFont(family="Courier New", size=22, weight="bold"),
            text_color="#a78bfa"
        ).pack(side="left")
        ctk.CTkLabel(
            title_frame, text=" MERGER",
            font=ctk.CTkFont(family="Courier New", size=22, weight="bold"),
            text_color="#e2e8f0"
        ).pack(side="left")

        # 설정 카드
        card = ctk.CTkFrame(left, fg_color="#1e1e2e", corner_radius=12)
        card.grid(row=0, column=0, sticky="ew", padx=20, pady=(60, 6))
        card.grid_columnconfigure(1, weight=1)

        row = 0

        # 소스 폴더
        ctk.CTkLabel(card, text="SOURCE", font=ctk.CTkFont(size=10, weight="bold"),
                     text_color="#6366f1").grid(row=row, column=0, sticky="w", padx=(16, 8), pady=(14, 2))
        row += 1
        self.source_var = tk.StringVar()
        self.source_entry = ctk.CTkEntry(card, textvariable=self.source_var,
                                         placeholder_text="병합할 폴더 선택...",
                                         font=ctk.CTkFont(family="Courier New", size=12),
                                         fg_color="#0f0f13", border_color="#2d2d3d",
                                         text_color="#e2e8f0", height=36)
        self.source_entry.grid(row=row, column=0, columnspan=2, sticky="ew", padx=(16, 8), pady=(0, 8))
        ctk.CTkButton(card, text="Browse", width=80, height=36,
                      fg_color="#6366f1", hover_color="#4f46e5",
                      font=ctk.CTkFont(size=12),
                      command=self._browse_source).grid(row=row, column=2, padx=(0, 16), pady=(0, 8))
        row += 1

        # 출력 폴더
        ctk.CTkLabel(card, text="OUTPUT FOLDER", font=ctk.CTkFont(size=10, weight="bold"),
                     text_color="#6366f1").grid(row=row, column=0, sticky="w", padx=(16, 8), pady=(4, 2))
        row += 1
        self.output_var = tk.StringVar(value=os.getcwd())
        self.output_entry = ctk.CTkEntry(card, textvariable=self.output_var,
                                          placeholder_text="저장 위치...",
                                          font=ctk.CTkFont(family="Courier New", size=12),
                                          fg_color="#0f0f13", border_color="#2d2d3d",
                                          text_color="#e2e8f0", height=36)
        self.output_entry.grid(row=row, column=0, columnspan=2, sticky="ew", padx=(16, 8), pady=(0, 8))
        ctk.CTkButton(card, text="Browse", width=80, height=36,
                      fg_color="#6366f1", hover_color="#4f46e5",
                      font=ctk.CTkFont(size=12),
                      command=self._browse_output).grid(row=row, column=2, padx=(0, 16), pady=(0, 8))
        row += 1

        # 파일명
        ctk.CTkLabel(card, text="FILENAME", font=ctk.CTkFont(size=10, weight="bold"),
                     text_color="#6366f1").grid(row=row, column=0, sticky="w", padx=(16, 8), pady=(4, 2))
        row += 1
        self.filename_var = tk.StringVar(value="merged_codebase.txt")
        self.filename_entry = ctk.CTkEntry(card, textvariable=self.filename_var,
                                            font=ctk.CTkFont(family="Courier New", size=12),
                                            fg_color="#0f0f13", border_color="#2d2d3d",
                                            text_color="#e2e8f0", height=36)
        self.filename_entry.grid(row=row, column=0, columnspan=3, sticky="ew", padx=16, pady=(0, 16))

        # RUN 버튼
        self.run_btn = ctk.CTkButton(
            left, text="▶  RUN MERGE", height=46,
            font=ctk.CTkFont(family="Courier New", size=14, weight="bold"),
            fg_color="#6366f1", hover_color="#4f46e5",
            corner_radius=10, command=self._run
        )
        self.run_btn.grid(row=0, column=0, sticky="ew", padx=20, pady=(0, 0))
        # (위치 재조정은 아래서 grid 순서로)

        # 재배치: card → run_btn → log
        card.grid(row=0, column=0, sticky="ew", padx=20, pady=(50, 0))
        self.run_btn.grid(row=0, column=0, sticky="ew", padx=20, pady=(0, 0))

        # 실제로는 frame 내부에서 pack 방식으로 다시 구성
        # tkinter grid 충돌 방지를 위해 inner_left 사용
        left.grid_forget()

        # ── 전체 재구성 (pack 방식으로) ─────────────────────────────────────
        left.destroy()
        left = ctk.CTkFrame(self, fg_color="#14141c", corner_radius=0)
        left.grid(row=0, column=0, sticky="nsew", padx=(12, 6), pady=12)

        # 헤더
        header = ctk.CTkFrame(left, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(20, 12))
        ctk.CTkLabel(header, text="⚡ CODEBASE",
                     font=ctk.CTkFont(family="Courier New", size=20, weight="bold"),
                     text_color="#a78bfa").pack(side="left")
        ctk.CTkLabel(header, text=" MERGER",
                     font=ctk.CTkFont(family="Courier New", size=20, weight="bold"),
                     text_color="#e2e8f0").pack(side="left")

        # 설정 카드 (재생성)
        card = ctk.CTkFrame(left, fg_color="#1e1e2e", corner_radius=12)
        card.pack(fill="x", padx=20, pady=(0, 10))

        self._make_field(card, "SOURCE FOLDER", self.source_var,
                         "병합할 폴더 선택...", self._browse_source)
        self._make_field(card, "OUTPUT FOLDER", self.output_var,
                         "저장 위치...", self._browse_output)
        self._make_filename_field(card)
        self._make_mode_field(card)

        # RUN 버튼
        self.run_btn = ctk.CTkButton(
            left, text="▶  RUN MERGE", height=44,
            font=ctk.CTkFont(family="Courier New", size=13, weight="bold"),
            fg_color="#6366f1", hover_color="#4f46e5",
            corner_radius=10, command=self._run
        )
        self.run_btn.pack(fill="x", padx=20, pady=(0, 6))

        # 저장 폴더 열기 버튼
        ctk.CTkButton(
            left, text="📂  저장 폴더 열기", height=32,
            font=ctk.CTkFont(size=12),
            fg_color="#1e1e2e", hover_color="#252538",
            border_width=1, border_color="#2d2d3d",
            text_color="#94a3b8",
            corner_radius=8, command=self._open_output_folder
        ).pack(fill="x", padx=20, pady=(0, 10))

        # 로그 레이블
        log_header = ctk.CTkFrame(left, fg_color="transparent")
        log_header.pack(fill="x", padx=20, pady=(4, 4))
        ctk.CTkLabel(log_header, text="LOG",
                     font=ctk.CTkFont(size=10, weight="bold"),
                     text_color="#6366f1").pack(side="left")
        ctk.CTkButton(log_header, text="Clear Log", width=70, height=22,
                      font=ctk.CTkFont(size=10),
                      fg_color="#2d2d3d", hover_color="#3d3d5d",
                      text_color="#94a3b8",
                      command=self._clear_log).pack(side="right")

        # 로그 창
        self.log_box = ctk.CTkTextbox(
            left, font=ctk.CTkFont(family="Courier New", size=11),
            fg_color="#0a0a0f", text_color="#4ade80",
            border_color="#2d2d3d", border_width=1,
            corner_radius=8, wrap="none",
            state="disabled"
        )
        self.log_box.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        # ── 오른쪽 패널 (히스토리) ──────────────────────────────────────────
        right = ctk.CTkFrame(self, fg_color="#14141c", corner_radius=0)
        right.grid(row=0, column=1, sticky="nsew", padx=(0, 12), pady=12)

        hist_header = ctk.CTkFrame(right, fg_color="transparent")
        hist_header.pack(fill="x", padx=14, pady=(20, 8))
        ctk.CTkLabel(hist_header, text="HISTORY",
                     font=ctk.CTkFont(family="Courier New", size=13, weight="bold"),
                     text_color="#a78bfa").pack(side="left")

        ctk.CTkLabel(right,
                     text="클릭 → 클립보드 복사",
                     font=ctk.CTkFont(size=9),
                     text_color="#475569").pack(anchor="w", padx=14)

        self.hist_frame = ctk.CTkScrollableFrame(
            right, fg_color="#0f0f13",
            scrollbar_button_color="#2d2d3d",
            corner_radius=8
        )
        self.hist_frame.pack(fill="both", expand=True, padx=14, pady=(6, 8))

        # 캐시 삭제 버튼
        ctk.CTkButton(
            right, text="🗑  캐시 삭제 (최근 1개 유지)",
            height=36, font=ctk.CTkFont(size=11),
            fg_color="#2d2d3d", hover_color="#991b1b",
            text_color="#f87171",
            corner_radius=8, command=self._clear_cache
        ).pack(fill="x", padx=14, pady=(0, 20))

    def _make_field(self, parent, label, var, placeholder, browse_cmd):
        ctk.CTkLabel(parent, text=label,
                     font=ctk.CTkFont(size=10, weight="bold"),
                     text_color="#6366f1").pack(anchor="w", padx=16, pady=(12, 2))
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=(0, 4))
        ctk.CTkEntry(row, textvariable=var, placeholder_text=placeholder,
                     font=ctk.CTkFont(family="Courier New", size=11),
                     fg_color="#0f0f13", border_color="#2d2d3d",
                     text_color="#e2e8f0", height=34).pack(side="left", fill="x", expand=True)
        ctk.CTkButton(row, text="⋯", width=40, height=34,
                      fg_color="#6366f1", hover_color="#4f46e5",
                      font=ctk.CTkFont(size=14),
                      command=browse_cmd).pack(side="left", padx=(6, 0))

    def _make_filename_field(self, parent):
        ctk.CTkLabel(parent, text="FILENAME",
                     font=ctk.CTkFont(size=10, weight="bold"),
                     text_color="#6366f1").pack(anchor="w", padx=16, pady=(12, 2))
        ctk.CTkEntry(parent, textvariable=self.filename_var,
                     font=ctk.CTkFont(family="Courier New", size=11),
                     fg_color="#0f0f13", border_color="#2d2d3d",
                     text_color="#e2e8f0", height=34).pack(fill="x", padx=16, pady=(0, 6))

    def _make_mode_field(self, parent):
        ctk.CTkLabel(parent, text="OUTPUT MODE",
                     font=ctk.CTkFont(size=10, weight="bold"),
                     text_color="#6366f1").pack(anchor="w", padx=16, pady=(8, 6))

        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=(0, 14))

        for value, label, desc in [
            ("full",  "📄 전체 내용",   "폴더 구조 + 파일 내용"),
            ("tree",  "🌲 구조만",      "폴더 트리만 출력"),
        ]:
            item = ctk.CTkFrame(row, fg_color="#0f0f13", corner_radius=8, cursor="hand2")
            item.pack(side="left", expand=True, fill="x", padx=(0, 6) if value == "full" else (0, 0))

            radio = ctk.CTkRadioButton(
                item,
                text=label,
                variable=self._mode_var,
                value=value,
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color="#e2e8f0",
                fg_color="#6366f1",
                hover_color="#4f46e5",
                border_color="#3d3d5d",
            )
            radio.pack(anchor="w", padx=10, pady=(8, 2))

            desc_label = ctk.CTkLabel(
                item, text=desc,
                font=ctk.CTkFont(size=9),
                text_color="#475569"
            )
            desc_label.pack(anchor="w", padx=28, pady=(0, 8))

            # 박스 전체 클릭 시 선택
            def _select(e, v=value):
                self._mode_var.set(v)

            for widget in [item, radio, desc_label]:
                widget.bind("<Button-1>", _select)

            # 호버 시 박스 밝아지게
            def _on_enter(e, f=item):
                f.configure(fg_color="#1a1a2e")
            def _on_leave(e, f=item):
                f.configure(fg_color="#0f0f13")

            for widget in [item, radio, desc_label]:
                widget.bind("<Enter>", _on_enter)
                widget.bind("<Leave>", _on_leave)

    # ── 브라우저 ──────────────────────────────────────────────────────────────

    def _browse_source(self):
        p = filedialog.askdirectory(title="병합할 소스 폴더 선택")
        if p:
            self.source_var.set(p)

    def _browse_output(self):
        p = filedialog.askdirectory(title="출력 폴더 선택")
        if p:
            self.output_var.set(p)

    def _open_output_folder(self):
        p = self.output_var.get().strip()
        if not p:
            messagebox.showwarning("알림", "출력 폴더가 설정되지 않았습니다.")
            return
        if not os.path.isdir(p):
            messagebox.showwarning("알림", f"폴더가 존재하지 않습니다:\n{p}")
            return
        if sys.platform == "win32":
            os.startfile(p)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", p])
        else:
            subprocess.Popen(["xdg-open", p])

    # ── 로그 ─────────────────────────────────────────────────────────────────

    def _log(self, msg):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", msg + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _clear_log(self):
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")

    # ── 실행 ─────────────────────────────────────────────────────────────────

    def _run(self):
        src = self.source_var.get().strip()
        out_dir = self.output_var.get().strip()
        fname = self.filename_var.get().strip()

        if not src or not os.path.isdir(src):
            messagebox.showerror("오류", "소스 폴더를 선택해주세요.")
            return
        if not out_dir:
            messagebox.showerror("오류", "출력 폴더를 선택해주세요.")
            return
        if not fname:
            fname = "merged_codebase.txt"
            self.filename_var.set(fname)

        if not fname.endswith(".txt"):
            fname += ".txt"

        self.run_btn.configure(state="disabled", text="⏳  처리 중...")
        self._clear_log()

        def task():
            timestamp = datetime.now()
            ts_str = timestamp.strftime("%Y%m%d_%H%M%S")
            cache_filename = f"{ts_str}_{fname}"
            cache_path = os.path.join(CACHE_DIR, cache_filename)

            # 실제 출력 경로
            os.makedirs(out_dir, exist_ok=True)
            real_path = os.path.join(out_dir, fname)

            try:
                mode = self._mode_var.get()
                merge_codebase(src, cache_path, self._log, mode)

                # 실제 파일도 복사
                shutil.copy2(cache_path, real_path)

                # 히스토리 저장
                entry = {
                    "timestamp": timestamp.isoformat(),
                    "display_time": timestamp.strftime("%m/%d %H:%M"),
                    "filename": fname,
                    "cache_path": cache_path,
                    "real_path": real_path,
                    "source": src,
                }
                self._history.insert(0, entry)
                save_history(self._history)
                self.after(0, self._refresh_history)
                self._log(f"\n💾 실제 파일: {real_path}")
                self._log(f"📄 저장 경로: {real_path}")

            except Exception as e:
                self._log(f"\n❌ 오류 발생: {e}")
            finally:
                self.after(0, lambda: self.run_btn.configure(
                    state="normal", text="▶  RUN MERGE"))

        threading.Thread(target=task, daemon=True).start()

    # ── 히스토리 ─────────────────────────────────────────────────────────────

    def _refresh_history(self):
        for widget in self.hist_frame.winfo_children():
            widget.destroy()

        if not self._history:
            ctk.CTkLabel(self.hist_frame, text="아직 기록이 없습니다.",
                         font=ctk.CTkFont(size=11),
                         text_color="#475569").pack(pady=20)
            return

        for i, entry in enumerate(self._history):
            self._make_hist_item(entry, i == 0)

    def _make_hist_item(self, entry, is_latest):
        frame = ctk.CTkFrame(
            self.hist_frame,
            fg_color="#1e1e2e" if is_latest else "#161620",
            corner_radius=8,
            cursor="hand2"
        )
        frame.pack(fill="x", pady=3, padx=2)

        if is_latest:
            ctk.CTkLabel(frame, text="LATEST",
                         font=ctk.CTkFont(size=8, weight="bold"),
                         text_color="#4ade80",
                         fg_color="#14532d", corner_radius=4).pack(anchor="e", padx=8, pady=(6, 0))

        ctk.CTkLabel(frame, text=entry["display_time"],
                     font=ctk.CTkFont(family="Courier New", size=10),
                     text_color="#64748b").pack(anchor="w", padx=10, pady=(4 if is_latest else 8, 0))

        ctk.CTkLabel(frame, text=entry["filename"],
                     font=ctk.CTkFont(family="Courier New", size=11, weight="bold"),
                     text_color="#c4b5fd",
                     wraplength=160).pack(anchor="w", padx=10)

        src_short = "..." + entry["source"][-22:] if len(entry["source"]) > 25 else entry["source"]
        ctk.CTkLabel(frame, text=src_short,
                     font=ctk.CTkFont(size=9),
                     text_color="#475569").pack(anchor="w", padx=10, pady=(0, 8))

        # 클릭 이벤트
        cache_path = entry["cache_path"]
        for widget in [frame] + frame.winfo_children():
            widget.bind("<Button-1>", lambda e, p=cache_path: self._copy_to_clipboard(p))
            widget.bind("<Enter>", lambda e, f=frame: f.configure(fg_color="#252538"))
            widget.bind("<Leave>", lambda e, f=frame, latest=is_latest:
                        f.configure(fg_color="#1e1e2e" if latest else "#161620"))

    def _copy_to_clipboard(self, cache_path):
        if not os.path.exists(cache_path):
            self._show_toast("⚠️ 캐시 파일이 없습니다 (삭제됨)")
            return
        try:
            content = safe_read_file(cache_path)
            pyperclip.copy(content)
            self._show_toast("✅ 클립보드에 복사됨!")
        except Exception as e:
            self._show_toast(f"❌ 복사 실패: {e}")

    def _show_toast(self, msg):
        toast = ctk.CTkLabel(
            self, text=msg,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#1e1e2e", text_color="#e2e8f0",
            corner_radius=8, padx=16, pady=8
        )
        toast.place(relx=0.5, rely=0.95, anchor="center")
        self.after(2500, toast.destroy)

    # ── 캐시 삭제 ────────────────────────────────────────────────────────────

    def _clear_cache(self):
        if not self._history:
            messagebox.showinfo("알림", "삭제할 캐시가 없습니다.")
            return

        answer = messagebox.askyesno(
            "캐시 삭제",
            f"히스토리 {len(self._history)}개 중 최근 1개만 남기고\n나머지 캐시 파일을 삭제할까요?"
        )
        if not answer:
            return

        kept = self._history[0] if self._history else None
        deleted = 0

        for entry in self._history[1:]:
            p = entry.get("cache_path", "")
            if p and os.path.exists(p):
                try:
                    os.remove(p)
                    deleted += 1
                except Exception:
                    pass

        self._history = [kept] if kept else []
        save_history(self._history)
        self._refresh_history()
        messagebox.showinfo("완료", f"캐시 {deleted}개 삭제 완료.\n최근 파일 1개는 유지됩니다.")


# ─── 진입점 ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = App()
    app.mainloop()