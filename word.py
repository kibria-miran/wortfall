from enum import Enum
from dataclasses import dataclass, field
import random

class WordState(str, Enum):
    FALLING="falling"; SOLVED="solved"; MISSED="missed"

@dataclass
class FallingWord:
    entry: dict
    prompt: str
    answer: str
    x: int
    speed: float
    spawn_time: float
    field_height: int
    state: WordState=WordState.FALLING
    resolve_time: float=None         # when SOLVED/MISSED, for the death animation
    hinted_50: bool=False
    hinted_75: bool=False
    parts: tuple=()      # (German, English, Urdu) text shown while falling
    colors: tuple=()     # (German, English, Urdu) Dracula accent names
    def __post_init__(self):
        self.speed *= random.uniform(0.9,1.1)
        self.y=0.0
        self.fall_time=self.field_height/max(self.speed,0.01)
    def update(self,dt):
        if self.state == WordState.FALLING: self.y += self.speed*dt
    def elapsed_fraction(self):
        return min(1.0,self.y/max(self.field_height,1))
    def label(self): return f"[ {self.prompt} ]"
    def explosion_frame(self, now=None):
        """Frame index 0..3 for the solved/missed animation (time-based, 30fps-independent)."""
        if self.resolve_time is None: return None
        import time
        now = now if now is not None else time.monotonic()
        step = int((now-self.resolve_time) / 0.14)
        return min(step, 3)
