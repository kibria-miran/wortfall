"""Pronunciation audio for German words (non-blocking, with graceful fallbacks).

Backends, best first:
  1. gTTS (natural Google voice, needs internet the first time; cached in ~/.wortfall/audio)
     plus an mp3 player: mpv, ffplay, mpg123 or cvlc
  2. espeak-ng / espeak (offline, robotic but instant)
  3. spd-say (speech-dispatcher)
If nothing is found the game still runs, silently.
"""
import hashlib, importlib.util, re, shutil, subprocess, threading
from pathlib import Path
from config import APP_DIR

CACHE_DIR = APP_DIR / "audio"
MP3_PLAYERS = (("mpv", ["--no-video", "--really-quiet"]), ("ffplay", ["-nodisp", "-autoexit", "-loglevel", "quiet"]),
               ("mpg123", ["-q"]), ("cvlc", ["--play-and-exit", "--quiet"]))

def clean_text(text):
    """Make a vocabulary entry speakable: drop '...' placeholders and stray symbols."""
    text = re.sub(r"\.{2,}|…", " ", str(text))
    return " ".join(text.replace("/", " ").split())

def find_mp3_player():
    for name, args in MP3_PLAYERS:
        path = shutil.which(name)
        if path: return [path] + args
    return None

def pick_backend():
    """Return (name, info) for the best available backend, or ("none", None)."""
    player = find_mp3_player()
    if player and importlib.util.find_spec("gtts"): return "gtts", player
    for exe in ("espeak-ng", "espeak"):
        if shutil.which(exe): return "espeak", [shutil.which(exe), "-v", "de", "-s", "135"]
    if shutil.which("spd-say"): return "spd-say", [shutil.which("spd-say"), "-l", "de", "-w"]
    return "none", None

class Speaker:
    def __init__(self):
        self.enabled = True
        self.backend, self.cmd = pick_backend()
        self._proc = None
        self._lock = threading.Lock()

    @property
    def available(self): return self.backend != "none"
    def toggle(self): self.enabled = not self.enabled; self.stop(); return self.enabled
    def label(self):
        if not self.available: return "SOUND: no audio tool found"
        return f"SOUND: {'ON' if self.enabled else 'OFF'} ({self.backend})"

    def stop(self):
        with self._lock:
            if self._proc and self._proc.poll() is None:
                try: self._proc.terminate()
                except OSError: pass
            self._proc = None

    def _run(self, cmd):
        with self._lock:
            try:
                self._proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                              stderr=subprocess.DEVNULL)
            except OSError: self._proc = None

    def speak(self, text):
        """Start speaking `text` and return immediately."""
        text = clean_text(text)
        if not (self.enabled and self.available and text): return
        self.stop()
        if self.backend == "gtts":
            threading.Thread(target=self._speak_gtts, args=(text,), daemon=True).start()
        else:
            self._run(self.cmd + [text])

    def _speak_gtts(self, text):
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            mp3 = CACHE_DIR / (hashlib.sha1(text.lower().encode()).hexdigest()[:16] + ".mp3")
            if not mp3.exists():
                from gtts import gTTS
                gTTS(text=text, lang="de").save(str(mp3))
            self._run(self.cmd + [str(mp3)])
        except Exception:
            # Offline or gTTS failed: fall back to an offline voice if one exists.
            for exe in ("espeak-ng", "espeak"):
                if shutil.which(exe):
                    self._run([shutil.which(exe), "-v", "de", "-s", "135", text]); return

_speaker = None
def get_speaker():
    global _speaker
    if _speaker is None: _speaker = Speaker()
    return _speaker
