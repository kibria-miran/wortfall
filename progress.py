"""Corruption-tolerant, atomic per-word progress persistence."""
import json, os, time
from pathlib import Path

class Progress:
    def __init__(self, path):
        self.path = Path(path).expanduser()
        self.data = {"words": {}, "high_score": 0}
        self.load()
    def load(self):
        try:
            obj = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(obj, dict):
                if isinstance(obj.get("words"), dict): self.data["words"] = obj["words"]
                if isinstance(obj.get("high_score"), int): self.data["high_score"] = obj["high_score"]
        except (OSError, ValueError, TypeError):
            pass
    def _record(self, de):
        return self.data["words"].setdefault(de, {"seen":0,"correct":0,"missed":0,"last_seen":None})
    def record_seen(self, de):
        r=self._record(de); r["seen"]+=1; r["last_seen"]=time.time()
    def record_correct(self, de): self._record(de)["correct"]+=1
    def record_missed(self, de): self._record(de)["missed"]+=1
    def update_high_score(self, score):
        self.data["high_score"] = max(self.data.get("high_score",0), int(score))
    def save(self):
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp=self.path.with_suffix(self.path.suffix+".tmp")
            tmp.write_text(json.dumps(self.data,ensure_ascii=False,indent=2),encoding="utf-8")
            os.replace(tmp,self.path)
        except OSError:
            # The game remains playable if the home directory is read-only.
            pass
