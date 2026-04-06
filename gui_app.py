import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import os
import sys
import subprocess
import shutil
import urllib.request
import zipfile
import tempfile
import multiprocessing

# UI Colors
BG       = "#0d0d0d"
BG2      = "#141414"
BG3      = "#1c1c1c"
BG4      = "#222222"
ACCENT   = "#ff4e4e"
ACCENT2  = "#ffd93d"
TEXT     = "#f0f0f0"
TEXT_DIM = "#666666"
BORDER   = "#2a2a2a"
SUCCESS  = "#4eff91"
ERROR    = "#ff4e4e"

FFMPEG_DIR = os.path.join(os.path.dirname(sys.executable), "ffmpeg_bin")

def _center(win, w, h):
    win.update_idletasks()
    x = (win.winfo_screenwidth() - w) // 2
    y = (win.winfo_screenheight() - h) // 2
    win.geometry(f"{w}x{h}+{x}+{y}")

def _si():
    try:
        if sys.platform == "win32":
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            si.wShowWindow = subprocess.SW_HIDE
            return si
    except Exception:
        pass
    return None

def _pip(args, timeout=120):
    if getattr(sys, 'frozen', False) or not sys.executable.lower().endswith(("python.exe", "pythonw.exe")):
        class DummyResponse:
            returncode = 1
            stdout = ""
        return DummyResponse()
        
    return subprocess.run(
        [sys.executable, "-m", "pip"] + args,
        startupinfo=_si(),
        capture_output=True,
        text=True,
        timeout=timeout,
    )

def check_ytdlp():
    try:
        import yt_dlp
        return True
    except ImportError:
        return False

def check_ffmpeg():
    if shutil.which("ffmpeg"):
        return True
    local = os.path.join(FFMPEG_DIR, "ffmpeg.exe")
    if os.path.exists(local):
        if FFMPEG_DIR not in os.environ.get("PATH", ""):
            os.environ["PATH"] = FFMPEG_DIR + os.pathsep + os.environ.get("PATH", "")
        return True
    return False

def _install_ytdlp_bg():
    try:
        _pip(["install", "yt-dlp", "-q"])
    except Exception:
        pass

def _pip_show_ver():
    try:
        r = _pip(["show", "yt-dlp"], timeout=15)
        for line in r.stdout.splitlines():
            if line.startswith("Version:"):
                return line.split(":", 1)[1].strip()
    except Exception:
        pass
    return ""

def _update_ytdlp_bg():
    old_ver = _pip_show_ver()
    try:
        _pip(["install", "--upgrade", "yt-dlp", "-q"], timeout=120)
    except subprocess.TimeoutExpired:
        return False, "Slow connection, timeout expired."
    except Exception as e:
        return False, f"Error: {e}"
    new_ver = _pip_show_ver()
    if old_ver and new_ver and old_ver != new_ver:
        return True, f"Updated: {old_ver} -> {new_ver}"
    return False, f"Already up to date: {new_ver or old_ver}"

def _install_ffmpeg_bg(status_cb):
    URL = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
    try:
        os.makedirs(FFMPEG_DIR, exist_ok=True)
        tmp = os.path.join(tempfile.gettempdir(), "ffmpeg_dl.zip")

        def hook(c, b, t):
            if t > 0:
                status_cb(f"Downloading ffmpeg... %{min(int(c*b*100/t),100)}")

        urllib.request.urlretrieve(URL, tmp, hook)
        status_cb("Extracting ffmpeg...")
        with zipfile.ZipFile(tmp, "r") as z:
            for m in z.namelist():
                fn = os.path.basename(m)
                if fn in ("ffmpeg.exe", "ffprobe.exe", "ffplay.exe"):
                    with z.open(m) as src, open(os.path.join(FFMPEG_DIR, fn), "wb") as dst:
                        dst.write(src.read())
        os.remove(tmp)
        os.environ["PATH"] = FFMPEG_DIR + os.pathsep + os.environ.get("PATH", "")
        return True, "ffmpeg installed!"
    except Exception as e:
        return False, str(e)

def get_info(url):
    import yt_dlp
    opts = {"quiet": True, "no_warnings": True, "skip_download": True, "noplaylist": True}
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
        seen, qualities = set(), []
        for f in reversed(info.get("formats", [])):
            h = f.get("height")
            if h and h not in seen:
                seen.add(h)
                qualities.append(f"{h}p")
        return info, qualities

def download_video(url, path, audio_only, muted, quality, progress_cb, done_cb, error_cb):
    import yt_dlp
    def hook(d):
        if d["status"] == "downloading":
            pct = d.get("_percent_str", "0%").strip()
            spd = d.get("_speed_str", "").strip()
            try: val = float(pct.replace("%", ""))
            except: val = 0
            progress_cb(val, pct, spd)
        elif d["status"] == "finished":
            progress_cb(100, "100%", "")

    ffmpeg_ok = check_ffmpeg()
    opts = {
        "outtmpl": os.path.join(path, "%(title)s.%(ext)s"),
        "quiet": True, "no_warnings": True,
        "progress_hooks": [hook], "noplaylist": True,
    }

    if audio_only:
        opts["format"] = "bestaudio/best"
        if ffmpeg_ok:
            opts["postprocessors"] = [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}]
    elif muted:
        hf = f"[height<={quality.replace('p','')}]" if quality != "Best" else ""
        opts["format"] = f"bestvideo{hf}[ext=mp4]/bestvideo{hf}/bestvideo"
    else:
        h = quality.replace("p", "")
        if quality != "Best":
            opts["format"] = f"bestvideo[height<={h}][ext=mp4]+bestaudio[ext=m4a]/best[height<={h}]" if ffmpeg_ok else f"best[height<={h}]"
        else:
            opts["format"] = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best" if ffmpeg_ok else "best"

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            done_cb(info.get("title", "Video"))
    except Exception as e:
        error_cb(str(e))

class DevelopedDownloader(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Developed Downloader")
        self.geometry("700x730")
        self.resizable(False, False)
        self.configure(bg=BG)
        _center(self, 700, 730)
        
        self.is_downloading = False 
        self.protocol("WM_DELETE_WINDOW", self._on_close) 

        self.save_path    = tk.StringVar(value=os.path.join(os.path.expanduser("~"), "Downloads"))
        self.format_var   = tk.StringVar(value="video")
        self.muted_var    = tk.BooleanVar(value=False)
        self.quality_var  = tk.StringVar(value="Best")
        self.status_var   = tk.StringVar(value="Initializing...")
        self.speed_var    = tk.StringVar(value="")
        self.progress_var = tk.DoubleVar(value=0)
        self._ibar        = None

        self._build_ui()
        self.after(300, self._startup_check)

    def _on_close(self):
        if self.is_downloading:
            if messagebox.askyesno("Exit", "A download is in progress. Are you sure you want to exit?"):
                self.destroy()
        else:
            self.destroy()

    def _set_status(self, msg, color=TEXT_DIM):
        self.status_var.set(msg)
        self.status_lbl.config(fg=color)

    def _lock_ui(self, locked):
        self.is_downloading = locked
        state = "disabled" if locked else "normal"
        for btn in [self.preview_btn, self.dl_btn, self.update_btn, self.deps_btn]:
            btn.config(state=state)

    def _startup_check(self):
        ytdlp_ok, ffmpeg_ok = check_ytdlp(), check_ffmpeg()
        if ytdlp_ok and ffmpeg_ok:
            self._set_status("Ready - all components loaded", SUCCESS)
            return
        missing = []
        if not ytdlp_ok: missing.append("yt-dlp")
        if not ffmpeg_ok: missing.append("ffmpeg")
        self._set_status(f"Missing: {', '.join(missing)}", ACCENT2)
        self._show_install_bar(missing)

    def _show_install_bar(self, missing):
        bar = tk.Frame(self, bg="#1a1a00", pady=6, padx=16)
        bar.pack(fill="x", padx=24, pady=(0, 4))
        self._ibar = bar
        tk.Label(bar, text=f"Missing: {', '.join(missing)}. Install now?", font=("Courier New", 9), fg=ACCENT2, bg="#1a1a00").pack(side="left")
        tk.Button(bar, text="Yes", command=lambda: [bar.destroy(), self._install_missing(missing)], bg=SUCCESS, fg=BG, relief="flat", padx=10).pack(side="right", padx=4)
        tk.Button(bar, text="No", command=bar.destroy, bg=BG3, fg=TEXT, relief="flat", padx=10).pack(side="right")

    def _install_missing(self, missing):
        self._lock_ui(True)
        def run():
            if "yt-dlp" in missing: _install_ytdlp_bg()
            if "ffmpeg" in missing: _install_ffmpeg_bg(lambda s: self.after(0, lambda m=s: self._set_status(m, ACCENT2)))
            self.after(0, lambda: [self._lock_ui(False), self._set_status("Installation complete!", SUCCESS)])
        threading.Thread(target=run, daemon=True).start()

    def _build_ui(self):
        hdr = tk.Frame(self, bg=BG, pady=18)
        hdr.pack(fill="x")
        tk.Label(hdr, text="Developed Downloader", font=("Courier New", 26, "bold"), fg=ACCENT, bg=BG).pack()
        tk.Label(hdr, text="YouTube - TikTok - Twitter - Instagram - 1000+ sites", font=("Courier New", 9), fg=TEXT_DIM, bg=BG).pack()
        tk.Frame(self, bg=BORDER, height=1).pack(fill="x", padx=24)

        card = tk.Frame(self, bg=BG2, padx=28, pady=18)
        card.pack(fill="both", expand=True, padx=24, pady=12)

        tk.Label(card, text="VIDEO LINK", font=("Courier New", 8, "bold"), fg=TEXT_DIM, bg=BG2).pack(anchor="w")
        uf = tk.Frame(card, bg=BG3, highlightbackground=BORDER, highlightthickness=1)
        uf.pack(fill="x", pady=(4, 10))
        self.url_entry = tk.Entry(uf, font=("Courier New", 11), bg=BG3, fg=TEXT, insertbackground=ACCENT, relief="flat", bd=8)
        self.url_entry.pack(side="left", fill="x", expand=True)
        self._btn(uf, "Clear", lambda: self.url_entry.delete(0, 'end'), small=True).pack(side="right", padx=6, pady=6)

        r1 = tk.Frame(card, bg=BG2)
        r1.pack(fill="x", pady=(0, 6))
        for val, lbl in [("video", "MP4 Video"), ("audio", "MP3 Audio")]:
            tk.Radiobutton(r1, text=lbl, variable=self.format_var, value=val, font=("Courier New", 10), fg=TEXT, bg=BG2, selectcolor=BG3, command=self._on_format_change).pack(side="left", padx=8)

        self.muted_cb = tk.Checkbutton(card, text="Muted download (video only)", variable=self.muted_var, font=("Courier New", 10), fg=TEXT, bg=BG2, selectcolor=BG3)
        self.muted_cb.pack(anchor="w", padx=8)

        r3 = tk.Frame(card, bg=BG2)
        r3.pack(fill="x", pady=10)
        tk.Label(r3, text="QUALITY:", font=("Courier New", 8, "bold"), fg=TEXT_DIM, bg=BG2).pack(side="left")
        self.quality_menu = ttk.Combobox(r3, textvariable=self.quality_var, values=["Best"], state="readonly", width=14)
        self.quality_menu.pack(side="left", padx=10)

        tk.Label(card, text="SAVE PATH", font=("Courier New", 8, "bold"), fg=TEXT_DIM, bg=BG2).pack(anchor="w")
        pf = tk.Frame(card, bg=BG3, highlightbackground=BORDER, highlightthickness=1)
        pf.pack(fill="x", pady=(4, 12))
        tk.Entry(pf, textvariable=self.save_path, font=("Courier New", 9), bg=BG3, fg=TEXT_DIM, relief="flat", bd=8).pack(side="left", fill="x", expand=True)
        self._btn(pf, "Browse", self._pick_folder, small=True).pack(side="right", padx=6, pady=6)

        br = tk.Frame(card, bg=BG2)
        br.pack(fill="x", pady=10)
        self.preview_btn = self._btn(br, "Preview", self._on_preview)
        self.preview_btn.pack(side="left", expand=True, fill="x", padx=(0, 6))
        self.dl_btn = self._btn(br, "Download", self._on_download, accent=True)
        self.dl_btn.pack(side="left", expand=True, fill="x", padx=(6, 0))

        self.pbar = ttk.Progressbar(card, variable=self.progress_var, maximum=100)
        self.pbar.pack(fill="x", pady=(0, 6))

        sr = tk.Frame(card, bg=BG2)
        sr.pack(fill="x")
        self.status_lbl = tk.Label(sr, textvariable=self.status_var, font=("Courier New", 10, "bold"), fg=TEXT_DIM, bg=BG2)
        self.status_lbl.pack(side="left")
        tk.Label(sr, textvariable=self.speed_var, font=("Courier New", 9), fg=ACCENT2, bg=BG2).pack(side="right")

        self.info_frame = tk.Frame(card, bg=BG4, padx=14, pady=10)
        self.info_title = tk.Label(self.info_frame, text="", font=("Courier New", 10, "bold"), fg=TEXT, bg=BG4, wraplength=550)
        self.info_title.pack(anchor="w")

        toolbar = tk.Frame(self, bg=BG, pady=8)
        toolbar.pack(fill="x", padx=24)
        self.update_btn = self._btn(toolbar, "Update Core", self._on_update, small=True)
        self.update_btn.pack(side="left")
        self.deps_btn = self._btn(toolbar, "Check Dependencies", self._on_check_deps, small=True)
        self.deps_btn.pack(side="left", padx=8)

    def _btn(self, parent, text, cmd, accent=False, small=False):
        bg, fg = (ACCENT, "#0d0d0d") if accent else (BG3, TEXT)
        b = tk.Button(parent, text=text, command=cmd, font=("Courier New", 8 if small else 10, "bold"), bg=bg, fg=fg, relief="flat", cursor="hand2", padx=12, pady=6)
        return b

    def _on_format_change(self):
        is_audio = self.format_var.get() == "audio"
        self.muted_cb.config(state="disabled" if is_audio else "normal")
        self.quality_menu.config(state="disabled" if is_audio else "readonly")

    def _pick_folder(self):
        d = filedialog.askdirectory()
        if d: self.save_path.set(d)

    def _on_preview(self):
        url = self.url_entry.get().strip()
        if not url: return self._set_status("Please enter a link!", ACCENT2)
        self._set_status("Fetching info...", ACCENT2)
        def run():
            try:
                info, qualities = get_info(url)
                self.after(0, lambda: self._show_preview(info, qualities))
            except Exception as e:
                self.after(0, lambda: self._set_status(f"Error: {str(e)[:50]}", ERROR))
        threading.Thread(target=run, daemon=True).start()

    def _show_preview(self, info, qualities):
        self.info_title.config(text=info.get("title", "Unknown Title"))
        self.info_frame.pack(fill="x", pady=10)
        self.quality_menu.config(values=["Best"] + qualities)
        self.quality_var.set("Best")
        self._set_status("Preview loaded", SUCCESS)

    def _on_download(self):
        url = self.url_entry.get().strip()
        if not url: return self._set_status("Please enter a link!", ACCENT2)
        self._lock_ui(True)
        self._set_status("Downloading...", ACCENT2)
        threading.Thread(target=download_video, args=(url, self.save_path.get(), self.format_var.get() == "audio", self.muted_var.get(), self.quality_var.get(), 
                        lambda v, p, s: self.after(0, lambda: [self.progress_var.set(v), self.speed_var.set(s), self.status_var.set(f"Downloading... {p}")]),
                        lambda t: self.after(0, lambda: [self._lock_ui(False), self._set_status(f"Finished: {t[:50]}", SUCCESS)]),
                        lambda e: self.after(0, lambda: [self._lock_ui(False), self._set_status(f"Error: {e[:50]}", ERROR)])), daemon=True).start()

    def _on_update(self):
        self._set_status("Updating yt-dlp...", ACCENT2)
        threading.Thread(target=lambda: self.after(0, lambda: self._set_status(_update_ytdlp_bg()[1], SUCCESS)), daemon=True).start()

    def _on_check_deps(self):
        y, f = check_ytdlp(), check_ffmpeg()
        self._set_status(f"yt-dlp: {'OK' if y else 'MISSING'} | ffmpeg: {'OK' if f else 'MISSING'}", SUCCESS if y and f else ACCENT2)

if __name__ == "__main__":
    multiprocessing.freeze_support()
    app = DevelopedDownloader()
    app.mainloop()