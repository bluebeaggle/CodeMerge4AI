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

DEFAULT_EXTENSIONS = {
    ".py", ".js", ".html", ".css",
    ".c", ".h", ".cpp", ".hpp",
    ".java", ".kt", ".rs", ".go",
    ".swift", ".php", ".rb",
    ".ts", ".tsx", ".vue",
    ".json", ".yaml", ".md",
}

CONFIG_DIR   = os.path.join(os.path.expanduser("~"), ".codebase_merger")
CACHE_DIR    = os.path.join(CONFIG_DIR, "cache")
HISTORY_FILE = os.path.join(CONFIG_DIR, "history.json")
CONFIG_FILE  = os.path.join(CONFIG_DIR, "config.json")
os.makedirs(CACHE_DIR, exist_ok=True)

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


# ─── 설정 파일 I/O ────────────────────────────────────────────────────────────

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return {"extensions": set(data.get("extensions", list(DEFAULT_EXTENSIONS)))}
        except Exception:
            pass
    return {"extensions": set(DEFAULT_EXTENSIONS)}


def save_config(config):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump({"extensions": sorted(list(config["extensions"]))}, f, ensure_ascii=False, indent=2)


def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def save_history(history):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


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
        entries = sorted(os.scandir(path),
                         key=lambda e: (not e.is_dir(follow_symlinks=False), e.name.lower()))
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


def collect_files(path, include_extensions, visited=None):
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
            files.extend(collect_files(entry.path, include_extensions, visited))
        else:
            if os.path.splitext(entry.name)[1].lower() in include_extensions:
                files.append(entry.path)
    return files


def merge_codebase(folder_path, output_path, log_fn, mode, include_extensions):
    folder_name = os.path.basename(folder_path)
    log_fn(f"📂 폴더: {folder_path}")
    log_fn(f"📎 포함 확장자: {', '.join(sorted(include_extensions))}")
    log_fn(f"⚙️  모드: {'전체 내용' if mode == 'full' else '폴더 구조만'}\n")

    tree_lines = build_tree_lines(folder_path)
    for line in [f"📂 {folder_name}"] + tree_lines:
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
            return

        files = collect_files(folder_path, include_extensions)
        log_fn(f"\n🔄 파일 병합 시작 ({len(files)}개 파일)")
        out.write("=" * 80 + "\n")
        out.write("FILE CONTENTS\n")
        out.write("=" * 80 + "\n")

        for filepath in sorted(files):
            size_mb = os.path.getsize(filepath) / (1024 * 1024)
            if size_mb > MAX_FILE_SIZE_MB:
                out.write(f"\n# [SKIPPED - TOO LARGE] {filepath}\n")
                log_fn(f"⚠️  스킵 (너무 큰 파일): {filepath}")
                continue
            out.write("\n\n" + "=" * 60 + "\n")
            out.write(f"## FILE PATH: {filepath}\n")
            out.write("=" * 60 + "\n\n")
            out.write(safe_read_file(filepath))
            log_fn(f"  ✓ {os.path.relpath(filepath, folder_path)}")

        log_fn("\n✅ 병합 완료!")


# ─── 확장자 관리 모달 ─────────────────────────────────────────────────────────

class ExtensionManagerDialog(ctk.CTkToplevel):
    """
    확장자 설정 팝업.
    ✕ 클릭 즉시 부모 앱에 반영 & 자동 저장 — 별도 저장 버튼 없음.
    """

    EXT_META = {
        ".py":    ("Python",     "#3b82f6"),
        ".js":    ("JavaScript", "#f59e0b"),
        ".ts":    ("TypeScript", "#2563eb"),
        ".tsx":   ("TSX",        "#06b6d4"),
        ".jsx":   ("JSX",        "#61dafb"),
        ".html":  ("HTML",       "#f97316"),
        ".css":   ("CSS",        "#a78bfa"),
        ".vue":   ("Vue",        "#4ade80"),
        ".svelte":("Svelte",     "#ff6b35"),
        ".c":     ("C",          "#64748b"),
        ".h":     ("C Header",   "#475569"),
        ".cpp":   ("C++",        "#7dd3fc"),
        ".hpp":   ("C++ Header", "#5eacd3"),
        ".java":  ("Java",       "#f87171"),
        ".kt":    ("Kotlin",     "#c084fc"),
        ".rs":    ("Rust",       "#fb923c"),
        ".go":    ("Go",         "#34d399"),
        ".swift": ("Swift",      "#ff6b6b"),
        ".php":   ("PHP",        "#818cf8"),
        ".rb":    ("Ruby",       "#f43f5e"),
        ".json":  ("JSON",       "#fbbf24"),
        ".yaml":  ("YAML",       "#a3e635"),
        ".yml":   ("YAML",       "#a3e635"),
        ".toml":  ("TOML",       "#9ca3af"),
        ".md":    ("Markdown",   "#94a3b8"),
        ".sql":   ("SQL",        "#38bdf8"),
        ".sh":    ("Shell",      "#4ade80"),
        ".bash":  ("Bash",       "#86efac"),
        ".zsh":   ("Zsh",        "#86efac"),
        ".xml":   ("XML",        "#fb923c"),
        ".ini":   ("Config",     "#9ca3af"),
        ".txt":   ("Text",       "#e2e8f0"),
        ".r":     ("R",          "#6ee7b7"),
        ".dart":  ("Dart",       "#22d3ee"),
        ".lua":   ("Lua",        "#a78bfa"),
        ".zig":   ("Zig",        "#f59e0b"),
        ".cs":    ("C#",         "#c084fc"),
    }

    def __init__(self, parent, get_extensions, on_change):
        """
        get_extensions : callable → 부모 앱의 현재 확장자 set 반환
        on_change      : callable(set) → 변경 시 즉시 호출
        """
        super().__init__(parent)
        self.title("Extension Settings")
        self.geometry("660x560")
        self.resizable(False, False)
        self.configure(fg_color="#0f0f13")
        self.grab_set()

        self._get_ext  = get_extensions
        self._on_change = on_change

        # 다이얼로그 자체 복사본 (렌더링 전용)
        self._local = set(get_extensions())

        self._build()
        self._render_tags()

    def _build(self):
        # 헤더
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=24, pady=(20, 4))
        ctk.CTkLabel(header, text="⚙️  EXTENSION",
                     font=ctk.CTkFont(family="Courier New", size=17, weight="bold"),
                     text_color="#a78bfa").pack(side="left")
        ctk.CTkLabel(header, text=" SETTINGS",
                     font=ctk.CTkFont(family="Courier New", size=17, weight="bold"),
                     text_color="#e2e8f0").pack(side="left")

        ctk.CTkLabel(self,
                     text="✕ 를 눌러 즉시 제거  ·  아래에서 추가  ·  변경사항은 자동 저장됩니다.",
                     font=ctk.CTkFont(size=11), text_color="#475569"
                     ).pack(anchor="w", padx=24, pady=(0, 14))

        # 태그 영역
        tag_outer = ctk.CTkFrame(self, fg_color="#0a0a0f", corner_radius=12,
                                  border_width=1, border_color="#1e1e2e")
        tag_outer.pack(fill="both", expand=True, padx=24, pady=(0, 14))

        tag_header = ctk.CTkFrame(tag_outer, fg_color="#1e1e2e", corner_radius=8)
        tag_header.pack(fill="x", padx=8, pady=(8, 6))

        self._count_label = ctk.CTkLabel(
            tag_header, text="",
            font=ctk.CTkFont(family="Courier New", size=10, weight="bold"),
            text_color="#6366f1")
        self._count_label.pack(side="left", padx=12, pady=6)

        ctk.CTkButton(tag_header, text="기본값 초기화", width=110, height=26,
                      font=ctk.CTkFont(size=10),
                      fg_color="#2d2d3d", hover_color="#991b1b",
                      text_color="#f87171", corner_radius=6,
                      command=self._reset_to_default).pack(side="right", padx=8, pady=4)

        ctk.CTkButton(tag_header, text="모두 제거", width=80, height=26,
                      font=ctk.CTkFont(size=10),
                      fg_color="#2d2d3d", hover_color="#4b2020",
                      text_color="#f87171", corner_radius=6,
                      command=self._clear_all).pack(side="right", padx=(0, 4), pady=4)

        self._tag_scroll = ctk.CTkScrollableFrame(
            tag_outer, fg_color="transparent",
            scrollbar_button_color="#2d2d3d", height=220)
        self._tag_scroll.pack(fill="both", expand=True, padx=6, pady=(0, 8))

        # 추가 영역
        add_card = ctk.CTkFrame(self, fg_color="#1e1e2e", corner_radius=12)
        add_card.pack(fill="x", padx=24, pady=(0, 14))

        ctk.CTkLabel(add_card, text="추가하기",
                     font=ctk.CTkFont(size=10, weight="bold"),
                     text_color="#6366f1").pack(anchor="w", padx=14, pady=(10, 4))

        add_row = ctk.CTkFrame(add_card, fg_color="transparent")
        add_row.pack(fill="x", padx=14, pady=(0, 10))

        self._add_var = tk.StringVar()
        entry = ctk.CTkEntry(add_row, textvariable=self._add_var,
                             placeholder_text=".ext  (예: .tsx  .wasm  .proto)",
                             font=ctk.CTkFont(family="Courier New", size=12),
                             fg_color="#0f0f13", border_color="#2d2d3d",
                             text_color="#e2e8f0", height=36)
        entry.pack(side="left", fill="x", expand=True)
        entry.bind("<Return>", lambda e: self._add_extension())

        ctk.CTkButton(add_row, text="  +  추가", width=90, height=36,
                      font=ctk.CTkFont(size=12, weight="bold"),
                      fg_color="#6366f1", hover_color="#4f46e5",
                      corner_radius=8,
                      command=self._add_extension).pack(side="left", padx=(8, 0))

        # 빠른 추가
        quick_frame = ctk.CTkFrame(add_card, fg_color="transparent")
        quick_frame.pack(fill="x", padx=14, pady=(0, 14))
        ctk.CTkLabel(quick_frame, text="빠른 추가:  ",
                     font=ctk.CTkFont(size=10), text_color="#475569").pack(side="left")

        for ext in [".sql", ".sh", ".xml", ".toml", ".dart", ".cs", ".lua", ".r", ".svelte"]:
            color = self.EXT_META.get(ext, (ext, "#64748b"))[1]
            ctk.CTkButton(quick_frame, text=ext, width=52, height=22,
                          font=ctk.CTkFont(size=10),
                          fg_color="#0f0f13", hover_color="#252538",
                          border_width=1, border_color="#2d2d3d",
                          text_color=color, corner_radius=6,
                          command=lambda e=ext: self._quick_add(e)).pack(side="left", padx=2)

        # 닫기 버튼
        ctk.CTkButton(self, text="✓  닫기", height=40,
                      font=ctk.CTkFont(size=12, weight="bold"),
                      fg_color="#6366f1", hover_color="#4f46e5",
                      corner_radius=8,
                      command=self.destroy).pack(fill="x", padx=24, pady=(0, 20))

    # ── 태그 렌더링 ───────────────────────────────────────────────────────────

    def _render_tags(self):
        for w in self._tag_scroll.winfo_children():
            w.destroy()

        sorted_exts = sorted(self._local)
        row_frame = None
        max_col = 5

        for idx, ext in enumerate(sorted_exts):
            if idx % max_col == 0:
                row_frame = ctk.CTkFrame(self._tag_scroll, fg_color="transparent")
                row_frame.pack(fill="x", pady=2)
            self._make_tag(row_frame, ext)

        self._count_label.configure(text=f"활성 확장자  ·  {len(self._local)}개")

    def _make_tag(self, parent, ext):
        meta  = self.EXT_META.get(ext, (ext[1:].upper(), "#64748b"))
        color = meta[1]

        chip = ctk.CTkFrame(parent, fg_color="#1a1a2e", corner_radius=8)
        chip.pack(side="left", padx=4, pady=2)

        dot = tk.Canvas(chip, width=8, height=8, bg="#1a1a2e", highlightthickness=0)
        dot.pack(side="left", padx=(8, 4), pady=8)
        dot.create_oval(1, 1, 7, 7, fill=color, outline="")

        ctk.CTkLabel(chip, text=ext,
                     font=ctk.CTkFont(family="Courier New", size=11, weight="bold"),
                     text_color=color).pack(side="left", pady=6)

        ctk.CTkLabel(chip, text=f"  {meta[0]}",
                     font=ctk.CTkFont(size=9),
                     text_color="#475569").pack(side="left", pady=6)

        rm = ctk.CTkLabel(chip, text=" ✕ ",
                          font=ctk.CTkFont(size=10, weight="bold"),
                          text_color="#4b5563", cursor="hand2")
        rm.pack(side="left", padx=(4, 6), pady=6)
        rm.bind("<Button-1>", lambda e, x=ext: self._remove_extension(x))
        rm.bind("<Enter>",    lambda e, w=rm: w.configure(text_color="#f87171"))
        rm.bind("<Leave>",    lambda e, w=rm: w.configure(text_color="#4b5563"))

        def _enter(e, f=chip): f.configure(fg_color="#252540")
        def _leave(e, f=chip): f.configure(fg_color="#1a1a2e")
        chip.bind("<Enter>", _enter)
        chip.bind("<Leave>", _leave)

    # ── 동작 ─────────────────────────────────────────────────────────────────

    def _commit(self):
        """로컬 상태를 부모에 즉시 반영 & 저장"""
        self._on_change(set(self._local))   # 복사본을 전달
        self._render_tags()

    def _add_extension(self):
        raw = self._add_var.get().strip().lower()
        if not raw:
            return
        ext = raw if raw.startswith(".") else f".{raw}"
        if ext in self._local:
            self._flash_error(f"'{ext}' 는 이미 추가되어 있습니다.")
            return
        if len(ext) < 2 or " " in ext:
            self._flash_error("올바른 확장자 형식이 아닙니다.")
            return
        self._local.add(ext)
        self._add_var.set("")
        self._commit()

    def _quick_add(self, ext):
        if ext not in self._local:
            self._local.add(ext)
            self._commit()

    def _remove_extension(self, ext):
        self._local.discard(ext)
        self._commit()

    def _clear_all(self):
        if messagebox.askyesno("확인", "모든 확장자를 제거하시겠습니까?", parent=self):
            self._local.clear()
            self._commit()

    def _reset_to_default(self):
        if messagebox.askyesno("확인", "기본값으로 초기화하시겠습니까?", parent=self):
            self._local = set(DEFAULT_EXTENSIONS)
            self._commit()

    def _flash_error(self, msg):
        lbl = ctk.CTkLabel(self, text=f"⚠  {msg}",
                           font=ctk.CTkFont(size=11),
                           fg_color="#4c1010", text_color="#fca5a5",
                           corner_radius=6, padx=12, pady=6)
        lbl.place(relx=0.5, rely=0.95, anchor="center")
        self.after(2000, lbl.destroy)


# ─── 메인 앱 ─────────────────────────────────────────────────────────────────

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Codebase Merger")
        self.geometry("1100x720")
        self.minsize(900, 620)
        self.configure(fg_color="#0f0f13")

        self._history = load_history()
        self._config  = load_config()

        # tk 변수는 반드시 super().__init__() 이후에 생성
        self.source_var   = tk.StringVar()
        self.output_var   = tk.StringVar(value=os.getcwd())
        self.filename_var = tk.StringVar(value="merged_codebase.txt")
        self._mode_var    = tk.StringVar(value="full")

        self._build_ui()
        self._refresh_history()

    # ── UI ───────────────────────────────────────────────────────────────────

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=3)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # 왼쪽 패널
        left = ctk.CTkFrame(self, fg_color="#14141c", corner_radius=0)
        left.grid(row=0, column=0, sticky="nsew", padx=(12, 6), pady=12)

        header = ctk.CTkFrame(left, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(20, 12))
        ctk.CTkLabel(header, text="⚡ CODEBASE",
                     font=ctk.CTkFont(family="Courier New", size=20, weight="bold"),
                     text_color="#a78bfa").pack(side="left")
        ctk.CTkLabel(header, text=" MERGER",
                     font=ctk.CTkFont(family="Courier New", size=20, weight="bold"),
                     text_color="#e2e8f0").pack(side="left")

        card = ctk.CTkFrame(left, fg_color="#1e1e2e", corner_radius=12)
        card.pack(fill="x", padx=20, pady=(0, 10))

        self._make_field(card, "SOURCE FOLDER", self.source_var,
                         "병합할 폴더 선택...", self._browse_source)
        self._make_field(card, "OUTPUT FOLDER", self.output_var,
                         "저장 위치...", self._browse_output)
        self._make_filename_field(card)
        self._make_mode_field(card)
        self._make_ext_field(card)

        self.run_btn = ctk.CTkButton(
            left, text="▶  RUN MERGE", height=44,
            font=ctk.CTkFont(family="Courier New", size=13, weight="bold"),
            fg_color="#6366f1", hover_color="#4f46e5",
            corner_radius=10, command=self._run)
        self.run_btn.pack(fill="x", padx=20, pady=(0, 6))

        ctk.CTkButton(left, text="📂  저장 폴더 열기", height=32,
                      font=ctk.CTkFont(size=12),
                      fg_color="#1e1e2e", hover_color="#252538",
                      border_width=1, border_color="#2d2d3d",
                      text_color="#94a3b8", corner_radius=8,
                      command=self._open_output_folder).pack(fill="x", padx=20, pady=(0, 10))

        log_header = ctk.CTkFrame(left, fg_color="transparent")
        log_header.pack(fill="x", padx=20, pady=(4, 4))
        ctk.CTkLabel(log_header, text="LOG",
                     font=ctk.CTkFont(size=10, weight="bold"),
                     text_color="#6366f1").pack(side="left")
        ctk.CTkButton(log_header, text="Clear Log", width=70, height=22,
                      font=ctk.CTkFont(size=10),
                      fg_color="#2d2d3d", hover_color="#3d3d5d",
                      text_color="#94a3b8", command=self._clear_log).pack(side="right")

        self.log_box = ctk.CTkTextbox(
            left, font=ctk.CTkFont(family="Courier New", size=11),
            fg_color="#0a0a0f", text_color="#4ade80",
            border_color="#2d2d3d", border_width=1,
            corner_radius=8, wrap="none", state="disabled")
        self.log_box.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        # 오른쪽 패널 (히스토리)
        right = ctk.CTkFrame(self, fg_color="#14141c", corner_radius=0)
        right.grid(row=0, column=1, sticky="nsew", padx=(0, 12), pady=12)

        hist_h = ctk.CTkFrame(right, fg_color="transparent")
        hist_h.pack(fill="x", padx=14, pady=(20, 8))
        ctk.CTkLabel(hist_h, text="HISTORY",
                     font=ctk.CTkFont(family="Courier New", size=13, weight="bold"),
                     text_color="#a78bfa").pack(side="left")

        ctk.CTkLabel(right, text="클릭 → 클립보드 복사",
                     font=ctk.CTkFont(size=9), text_color="#475569").pack(anchor="w", padx=14)

        self.hist_frame = ctk.CTkScrollableFrame(
            right, fg_color="#0f0f13",
            scrollbar_button_color="#2d2d3d", corner_radius=8)
        self.hist_frame.pack(fill="both", expand=True, padx=14, pady=(6, 8))

        ctk.CTkButton(right, text="🗑  캐시 삭제 (최근 1개 유지)",
                      height=36, font=ctk.CTkFont(size=11),
                      fg_color="#2d2d3d", hover_color="#991b1b",
                      text_color="#f87171", corner_radius=8,
                      command=self._clear_cache).pack(fill="x", padx=14, pady=(0, 20))

    # ── 카드 필드 빌더 ────────────────────────────────────────────────────────

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
        row.pack(fill="x", padx=16, pady=(0, 10))

        for value, label, desc in [
            ("full", "📄 전체 내용", "폴더 구조 + 파일 내용"),
            ("tree", "🌲 구조만",    "폴더 트리만 출력"),
        ]:
            item = ctk.CTkFrame(row, fg_color="#0f0f13", corner_radius=8, cursor="hand2")
            item.pack(side="left", expand=True, fill="x",
                      padx=(0, 6) if value == "full" else (0, 0))
            radio = ctk.CTkRadioButton(item, text=label, variable=self._mode_var, value=value,
                                        font=ctk.CTkFont(size=12, weight="bold"),
                                        text_color="#e2e8f0", fg_color="#6366f1",
                                        hover_color="#4f46e5", border_color="#3d3d5d")
            radio.pack(anchor="w", padx=10, pady=(8, 2))
            dl = ctk.CTkLabel(item, text=desc, font=ctk.CTkFont(size=9), text_color="#475569")
            dl.pack(anchor="w", padx=28, pady=(0, 8))

            def _sel(e, v=value):  self._mode_var.set(v)
            def _ein(e, f=item):   f.configure(fg_color="#1a1a2e")
            def _elv(e, f=item):   f.configure(fg_color="#0f0f13")
            for w in [item, radio, dl]:
                w.bind("<Button-1>", _sel)
                w.bind("<Enter>",    _ein)
                w.bind("<Leave>",    _elv)

    def _make_ext_field(self, parent):
        ctk.CTkFrame(parent, fg_color="#2d2d3d", height=1).pack(fill="x", padx=16, pady=(4, 10))

        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=(0, 14))

        info = ctk.CTkFrame(row, fg_color="transparent")
        info.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(info, text="INCLUDE EXTENSIONS",
                     font=ctk.CTkFont(size=10, weight="bold"),
                     text_color="#6366f1").pack(anchor="w")
        self._ext_count_label = ctk.CTkLabel(
            info, text=self._ext_preview(),
            font=ctk.CTkFont(family="Courier New", size=10),
            text_color="#64748b")
        self._ext_count_label.pack(anchor="w")

        ctk.CTkButton(row, text="⚙  관리", width=80, height=34,
                      font=ctk.CTkFont(size=11, weight="bold"),
                      fg_color="#252538", hover_color="#312e6e",
                      border_width=1, border_color="#4f46e5",
                      text_color="#a78bfa", corner_radius=8,
                      command=self._open_ext_manager).pack(side="right")

    def _ext_preview(self):
        exts = self._config["extensions"]
        preview = "  ".join(sorted(exts)[:6])
        more = f"  +{len(exts)-6}개" if len(exts) > 6 else ""
        return f"{preview}{more}   ({len(exts)}개 활성)"

    def _open_ext_manager(self):
        ExtensionManagerDialog(
            self,
            get_extensions=lambda: self._config["extensions"],
            on_change=self._on_ext_changed
        ).focus()

    def _on_ext_changed(self, new_extensions):
        """다이얼로그 변경 즉시 호출 → 저장 & UI 갱신"""
        self._config["extensions"] = new_extensions
        save_config(self._config)
        self._ext_count_label.configure(text=self._ext_preview())

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
        if not p or not os.path.isdir(p):
            messagebox.showwarning("알림", "유효한 출력 폴더가 없습니다.")
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
        fname = self.filename_var.get().strip() or "merged_codebase.txt"
        self.filename_var.set(fname)
        if not fname.endswith(".txt"):
            fname += ".txt"

        if not src or not os.path.isdir(src):
            messagebox.showerror("오류", "소스 폴더를 선택해주세요.")
            return
        if not out_dir:
            messagebox.showerror("오류", "출력 폴더를 선택해주세요.")
            return

        self.run_btn.configure(state="disabled", text="⏳  처리 중...")
        self._clear_log()

        include_exts = set(self._config["extensions"])

        def task():
            timestamp = datetime.now()
            cache_path = os.path.join(CACHE_DIR,
                                      f"{timestamp.strftime('%Y%m%d_%H%M%S')}_{fname}")
            os.makedirs(out_dir, exist_ok=True)
            real_path = os.path.join(out_dir, fname)
            try:
                merge_codebase(src, cache_path, self._log,
                               self._mode_var.get(), include_exts)
                shutil.copy2(cache_path, real_path)
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
                self._log(f"\n💾 저장 완료: {real_path}")
            except Exception as e:
                self._log(f"\n❌ 오류: {e}")
            finally:
                self.after(0, lambda: self.run_btn.configure(
                    state="normal", text="▶  RUN MERGE"))

        threading.Thread(target=task, daemon=True).start()

    # ── 히스토리 ─────────────────────────────────────────────────────────────

    def _refresh_history(self):
        for w in self.hist_frame.winfo_children():
            w.destroy()
        if not self._history:
            ctk.CTkLabel(self.hist_frame, text="아직 기록이 없습니다.",
                         font=ctk.CTkFont(size=11), text_color="#475569").pack(pady=20)
            return
        for i, entry in enumerate(self._history):
            self._make_hist_item(entry, i == 0)

    def _make_hist_item(self, entry, is_latest):
        frame = ctk.CTkFrame(self.hist_frame,
                             fg_color="#1e1e2e" if is_latest else "#161620",
                             corner_radius=8, cursor="hand2")
        frame.pack(fill="x", pady=3, padx=2)

        if is_latest:
            ctk.CTkLabel(frame, text="LATEST",
                         font=ctk.CTkFont(size=8, weight="bold"),
                         text_color="#4ade80", fg_color="#14532d",
                         corner_radius=4).pack(anchor="e", padx=8, pady=(6, 0))

        ctk.CTkLabel(frame, text=entry["display_time"],
                     font=ctk.CTkFont(family="Courier New", size=10),
                     text_color="#64748b").pack(anchor="w", padx=10, pady=(4 if is_latest else 8, 0))
        ctk.CTkLabel(frame, text=entry["filename"],
                     font=ctk.CTkFont(family="Courier New", size=11, weight="bold"),
                     text_color="#c4b5fd", wraplength=160).pack(anchor="w", padx=10)

        src_s = "..." + entry["source"][-22:] if len(entry["source"]) > 25 else entry["source"]
        ctk.CTkLabel(frame, text=src_s, font=ctk.CTkFont(size=9),
                     text_color="#475569").pack(anchor="w", padx=10, pady=(0, 8))

        cp = entry["cache_path"]
        for w in [frame] + list(frame.winfo_children()):
            w.bind("<Button-1>", lambda e, p=cp: self._copy_to_clipboard(p))
            w.bind("<Enter>",    lambda e, f=frame: f.configure(fg_color="#252538"))
            w.bind("<Leave>",    lambda e, f=frame, lat=is_latest:
                   f.configure(fg_color="#1e1e2e" if lat else "#161620"))

    def _copy_to_clipboard(self, cache_path):
        if not os.path.exists(cache_path):
            self._show_toast("⚠️ 캐시 파일 없음 (삭제됨)")
            return
        try:
            pyperclip.copy(safe_read_file(cache_path))
            self._show_toast("✅ 클립보드에 복사됨!")
        except Exception as e:
            self._show_toast(f"❌ 복사 실패: {e}")

    def _show_toast(self, msg):
        t = ctk.CTkLabel(self, text=msg,
                         font=ctk.CTkFont(size=12, weight="bold"),
                         fg_color="#1e1e2e", text_color="#e2e8f0",
                         corner_radius=8, padx=16, pady=8)
        t.place(relx=0.5, rely=0.95, anchor="center")
        self.after(2500, t.destroy)

    # ── 캐시 삭제 ─────────────────────────────────────────────────────────────

    def _clear_cache(self):
        if not self._history:
            messagebox.showinfo("알림", "삭제할 캐시가 없습니다.")
            return
        if not messagebox.askyesno("캐시 삭제",
                                    f"히스토리 {len(self._history)}개 중 최근 1개만 남기고 삭제할까요?"):
            return
        kept = self._history[0]
        deleted = 0
        for entry in self._history[1:]:
            p = entry.get("cache_path", "")
            if p and os.path.exists(p):
                try:
                    os.remove(p)
                    deleted += 1
                except Exception:
                    pass
        self._history = [kept]
        save_history(self._history)
        self._refresh_history()
        messagebox.showinfo("완료", f"캐시 {deleted}개 삭제 완료.")


# ─── 진입점 ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = App()
    app.mainloop()