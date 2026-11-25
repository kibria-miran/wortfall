"""Native sound effects, zero dependencies beyond stdlib + your audio stack.

Synthesized offline with the stdlib `wave`/`struct`/`math` modules into small
WAV files, cached in ~/.wortfall/sfx on first use, then played natively:

  1. paplay  — PipeWire/PulseAudio (the Arch default stack)
  2. aplay   — ALSA (works on bare-bones setups)
  3. ffplay  — ffmpeg fallback
  4. afplay  — macOS
  5. terminal bell (\\a) if no native player exists

Non-blocking: play() returns immediately; playback runs in a child process.
Toggle with F3 in-game.
"""
import math
import shutil
import struct
import subprocess
import sys
import threading
import wave
from pathlib import Path

from config import APP_DIR, CONFIG

SFX_DIR = APP_DIR / "sfx"
RATE = 22050  # 22.05 kHz mono 16-bit — tiny files, plenty for UI blips

# note sequences: (frequency Hz, duration s) — None = silence
EFFECTS = {
    "solve":     ((1047, .07), (1319, .07), (1568, .12)),          # C6 E6 G6 chime
    "wrong":     ((150, .10), (110, .14)),                          # low double-buzz
    "miss":      ((392, .10), (294, .10), (220, .16)),              # falling C-G-C
    "level_up":  ((523, .08), (659, .08), (784, .08), (1047, .18)), # C5 E5 G5 C6 fanfare
    "life":      ((1319, .05), (1568, .05), (2093, .10)),           # rising sparkle
    "streak":    ((784, .05), (988, .05), (1175, .05), (1568, .12)),
    "game_over": ((330, .18), (262, .18), (220, .30), (165, .40)),  # sad descent
    "spawn":     ((880, .03),),
    "keystroke": None,                                              # not used: gets annoying
}

_PLAYERS = (
    ("paplay", ("paplay",)),                                         # PipeWire/PulseAudio
    ("aplay", ("aplay", "-q")),                                      # ALSA
    ("ffplay", ("ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet")),
    ("afplay", ("afplay",)),                                         # macOS
)


def _samples(notes, volume):
    out = bytearray()
    for freq, dur in notes:
        n = int(RATE * dur)
        step = math.pi * 2 * freq / RATE
        for i in range(n):
            t = i / RATE
            attack = min(1.0, t / 0.004)
            decay = 1.0 - (i / n) ** 1.6
            sample = math.sin(step * i) * attack * decay * volume
            out += struct.pack("<h", max(-32767, min(32767, int(sample * 32767))))
    return bytes(out)


def _write_wav(path, notes):
    data = _samples(notes, CONFIG["sfx_volume"])
    with wave.open(str(path), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(RATE)
        f.writeframes(data)


def _find_player():
    for name, prefix in _PLAYERS:
        path = shutil.which(name)
        if path:
            return name, [path] + list(prefix[1:])
    return "bell", None


def ensure_effect(name):
    """Materialize the cached WAV for an effect; returns path or None."""
    notes = EFFECTS.get(name)
    if not notes:
        return None
    SFX_DIR.mkdir(parents=True, exist_ok=True)
    path = SFX_DIR / f"{name}.wav"
    if not path.exists():
        _write_wav(path, notes)
    return path


class SFX:
    def __init__(self):
        self.enabled = CONFIG["sfx_enabled"]
        self.backend, self.cmd = _find_player()
        self._proc = None
        self._lock = threading.Lock()

    @property
    def available(self):
        return self.backend != "bell"

    def toggle(self):
        self.enabled = not self.enabled
        self.stop()
        return self.enabled

    def label(self):
        if not self.available:
            return "SFX: bell only (install pipewire or alsa-utils)"
        return f"SFX: {'ON' if self.enabled else 'OFF'} ({self.backend})"

    def stop(self):
        with self._lock:
            if self._proc and self._proc.poll() is None:
                try:
                    self._proc.terminate()
                except OSError:
                    pass
            self._proc = None

    def play(self, name):
        if not self.enabled or name not in EFFECTS:
            return
        if self.backend == "bell":
            sys.stdout.write("\a")
            sys.stdout.flush()
            return
        with self._lock:
            if self._proc and self._proc.poll() is None:
                return  # don't stack identical blips
            try:
                path = ensure_effect(name)
                if path:
                    self._proc = subprocess.Popen(
                        self.cmd + [str(path)],
                        stdin=subprocess.DEVNULL,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
            except OSError:
                self._proc = None


_sfx = None


def get_sfx():
    global _sfx
    if _sfx is None:
        _sfx = SFX()
    return _sfx
