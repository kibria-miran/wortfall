"""Pure game rules and session state; no curses dependency."""
import random, time
from collections import defaultdict, deque
from config import CONFIG, random_word_colors
from textnorm import normalize, strip_article, edit_distance, display_width
from vocab import Picker, filter_by_category, eligible_words, word_key
from word import FallingWord, WordState

# Optional callback(text) fired when a word spawns, so pronunciation is heard
# while the meaning is still on screen (set by main.py for audio).
SPAWN_HOOK = None
def set_spawn_hook(fn):
    global SPAWN_HOOK; SPAWN_HOOK = fn

# Optional callback(name) fired on game events for sound effects.
# Names: "wrong", "miss", "level_up", "life", "streak", "game_over"
# (Correctly typed words stay silent: no chime, no repeated speech.)
EVENT_HOOK = None
def set_event_hook(fn):
    global EVENT_HOOK; EVENT_HOOK = fn

def _event(name):
    if EVENT_HOOK:
        try: EVENT_HOOK(name)
        except Exception: pass

def make_parts(answer, entry, plural=False):
    """German == English (+ pl. marker) == Urdu pieces for one falling word."""
    en = entry["en"]
    if plural:
        en = f"{en} (pl.)"
    return tuple(x for x in (answer, en, entry.get("ur")) if x)

def spawn_interval(level,cfg=CONFIG): return max(cfg["min_spawn_interval"],cfg["base_spawn_interval"]-cfg["spawn_decay"]*(level-1))
def max_words(level,cfg=CONFIG): return min(cfg["max_words_cap"],2+(level-1)//2)
def speed_for(level,cfg=CONFIG): return cfg["base_fall_speed"]*min(cfg["speed_cap"],cfg["speed_growth"]**(level-1))

class GameState:
    def __init__(self,vocab,progress,categories=None,articles_mode=None,plural_mode=None,
                 learn_mode=False,recall_mode=None,weighted=None):
        self.all_vocab=list(vocab); self.categories=set(categories or [])
        filtered=filter_by_category(self.all_vocab,self.categories or None)
        self.vocab=eligible_words(filtered, CONFIG["plural_mode"] if plural_mode is None else plural_mode)
        self.progress=progress
        self.articles_mode=articles_mode or CONFIG["articles_mode"]
        self.plural_mode=CONFIG["plural_mode"] if plural_mode is None else plural_mode
        if self.plural_mode: self.vocab=eligible_words(self.vocab,True)
        self.learn_mode=learn_mode
        self.recall_mode=CONFIG["recall_mode"] if recall_mode is None else recall_mode
        self.weighted=CONFIG["weak_word_review"] if weighted is None else weighted
        self.cheated=False   # TAB / <1.0x speed used: no high score from this session
        self.picker=Picker(self.vocab,progress.data["words"],CONFIG["recent_words_memory"],
                           weighted=self.weighted)
        self.score=0; self.lives=CONFIG["start_lives"]; self.infinite_lives=False
        self.speed_scale=1.0; self.level=1; self.streak=0
        self.clock=0.0
        self.correct_count=0; self.mistakes=0; self.words=[]; self.input_buffer=""
        self.spawn_timer=0.5; self.feedback=""; self.feedback_until=0
        self.missed_log=defaultdict(int); self.words_seen=set(); self.learn_turn=0
        self.learn_current=None; self.learn_due=deque(); self.started_at=time.monotonic()
        self.game_over=False; self.paused=False; self.field_height=20
        self.level_message_until=0; self.last_level=self.level
    def spawn_interval(self): return spawn_interval(self.level)
    def max_words(self): return 1 if self.learn_mode else max_words(self.level)
    def speed(self): return 0 if self.learn_mode else speed_for(self.level) * self.speed_scale
    def recordable(self):
        """True when this session's score may enter the high score (no TAB, >=1.0x speed)."""
        return not self.cheated and self.speed_scale >= 1.0 and not self.learn_mode
    def change_speed(self, amount):
        old=self.speed_scale
        new=max(0.25, min(3.0, round(old+amount, 2)))
        if new==old:
            self._feedback(f"Fall speed limit: {self.speed_scale:.2f}x", 1.2); return
        ratio=new/old
        for word in self.words:
            if word.state == WordState.FALLING:
                word.speed = max(0.05, word.speed * ratio)
                word.fall_time = self.field_height / max(word.speed, 0.01)
        self.speed_scale=new
        if new<1.0: self.cheated=True
        self._feedback(f"Fall speed: {self.speed_scale:.2f}x", 1.2)
    def toggle_infinite_lives(self):
        self.infinite_lives = not self.infinite_lives
        if self.infinite_lives:
            self.cheated=True
            self.lives = max(self.lives, CONFIG["start_lives"])
        elif self.lives<1:
            self.lives=1
        self._feedback("Infinite lives: ON" if self.infinite_lives else "Infinite lives: OFF", 1.5)
    def _feedback(self,msg,seconds=2): self.feedback=msg; self.feedback_until=time.monotonic()+seconds
    def spawn_word(self,field_width=80):
        active=[word_key({"de":w.answer}) for w in self.words if w.state==WordState.FALLING]
        entry=self.picker.pick(active)
        if not entry: return None
        plural=self.plural_mode and entry.get("pl")
        answer=entry["pl"] if plural else entry["de"]
        # German == English == Urdu, e.g. [ Hallo == Hello == ہیلو ]
        parts=make_parts(answer,entry,plural); prompt=" == ".join(parts)
        label=f"[ {prompt} ]"; max_x=max(0,field_width-display_width(label)-2)
        x=random.randint(0,max_x) if max_x else 0
        w=FallingWord(entry,prompt,answer,x,self.speed(),time.monotonic(),self.field_height,
                      spawn_clock=self.clock,
                      parts=parts,colors=random_word_colors())
        # long words get proportionally more time to be typed (3.1)
        w.fall_time += CONFIG["time_per_char"]*len(answer)
        w.speed = self.field_height/max(w.fall_time,0.01)
        self.words.append(w); self.words_seen.add(entry["de"]); self.progress.record_seen(entry["de"])
        if SPAWN_HOOK:
            try: SPAWN_HOOK(answer)
            except Exception: pass
        return w
    def _forms(self,w):
        answer=normalize(w.answer); forms=[(answer,CONFIG["article_bonus"])]
        if not self.plural_mode and w.entry["pos"]=="noun":
            # SPACE resets typing, so the article-free form is always accepted too.
            if self.articles_mode in ("optional","off"):
                forms.append((normalize(strip_article(w.answer)),1.0))
        return forms
    def _keys(self,w):
        """Accepted typed forms; spaces are ignored so multi-word answers also match
        spaceless (SPACE resets typing, it is never part of a German answer)."""
        keys=set()
        for form,_ in self._forms(w):
            keys.add(form); keys.add(form.replace(" ",""))
        return keys
    def prefix_ok(self,value):
        """False when the buffer is no prefix of any falling word's answer (2.5)."""
        flat=normalize(value).replace(" ","")
        if not flat: return True
        for w in self.words:
            if w.state==WordState.FALLING:
                for key in self._keys(w):
                    if key.startswith(flat): return True
        return False
    def try_match(self,value):
        norm=normalize(value); flat=norm.replace(" ","")
        if not flat: return False
        matches=[]
        for w in self.words:
            if w.state==WordState.FALLING:
                for form,mult in self._forms(w):
                    if flat in (form,form.replace(" ","")): matches.append((w,mult))
        if not matches: return False
        w,mult=max(matches,key=lambda pair:pair[0].y)
        self.solve(w,mult); return True
    def dead_typing(self,value):
        """A buffer that cannot become any falling word: count it, clear it (2.5)."""
        self.mistakes+=1
        self._feedback(f"✗ {value} — no word starts like this",1.2)
        self.input_buffer=""
        _event("wrong")
    def submit(self):
        value=self.input_buffer.strip(); flat=normalize(value).replace(" ","")
        if not flat: return
        if self.try_match(value):
            self.input_buffer=""; return
        # Missing article gets a teaching prompt, not a penalty.
        for w in self.words:
            if w.state==WordState.FALLING and w.entry["pos"]=="noun" and self.articles_mode=="required":
                if flat==normalize(strip_article(w.answer)).replace(" ",""):
                    self._feedback(f"Need the article: {w.answer}",2); self.streak=0; self.input_buffer=""; return
        near=None
        for w in self.words:
            if w.state==WordState.FALLING:
                for key in self._keys(w):
                    if edit_distance(flat,key)==1: near=w; break
            if near: break
        if near:
            self._feedback(f"Almost! {value} → {near.answer}",2); self.streak=0; self.input_buffer=""; return
        self.score=max(0,self.score-CONFIG["wrong_penalty"]); self.streak=0; self.mistakes+=1
        self._feedback(f"Wrong: {value} — no matching word",1.5); self.input_buffer=""
        _event("wrong")
    def solve(self,w,multiplier=1.0):
        if w.state!=WordState.FALLING: return
        elapsed=self.clock-w.spawn_clock
        bonus=(CONFIG["speed_bonus_points"]
               if not self.learn_mode and elapsed<=w.fall_time*CONFIG["speed_bonus_fraction"] else 0)
        self.streak+=1; raw=10*self.level+bonus
        factor=2 if self.streak>=5 else 1.5 if self.streak>=3 else 1
        points=round(raw*factor*multiplier); self.score+=points
        self.correct_count+=1; self.progress.record_correct(w.entry["de"])
        w.state=WordState.SOLVED; w.resolve_time=time.monotonic()
        if self.streak>=5: _event("streak")
        if self.streak%5==0:
            self.lives=min(CONFIG["max_lives"],self.lives+1); _event("life")
        old=self.level; self.level=1+self.correct_count//CONFIG["level_up_every"]
        if self.level>old:
            self._feedback(f"LEVEL UP! Level {self.level} — speed increased",2); _event("level_up")
        else: self._feedback(f"+{points}  {w.answer}",1.2)
        if self.learn_mode:
            self.learn_turn+=1; self.learn_current=None
    def lose_life(self,w):
        if w.state!=WordState.FALLING: return
        w.state=WordState.MISSED; w.resolve_time=time.monotonic()
        if not self.learn_mode and not self.infinite_lives:
            self.lives-=1; _event("miss")
            if self.lives<=0: _event("game_over")
        if self.infinite_lives: _event("miss")
        self.streak=0; self.mistakes+=1; self.missed_log[w.entry["de"]]+=1
        self.progress.record_missed(w.entry["de"])
        self._feedback(f"Missed: {w.answer} = {w.entry['en']}",2)
        if self.learn_mode:
            self.learn_turn+=1
            self.learn_due.append((self.learn_turn+CONFIG["learn_requeue_turns"],w.entry))
    def learn_skip(self):
        """Reveal the answer of the learn-mode word (counts as a miss and re-queues)."""
        if not self.learn_mode: return
        for w in self.words:
            if w.state==WordState.FALLING:
                self._feedback(f"'?' skips — it was: {w.answer} = {w.entry['en']}",2)
                self.lose_life(w)
                return
    def update(self,dt,field_width=80):
        if self.paused or self.game_over: return
        now=time.monotonic()
        self.clock+=dt
        if self.feedback and now>self.feedback_until: self.feedback=""
        if self.learn_mode:
            self.words=[w for w in self.words if w.state==WordState.FALLING]
            if not self.words:
                if self.learn_due and self.learn_due[0][0]<=self.learn_turn:
                    _,entry=self.learn_due.popleft()
                    self._spawn_specific(entry,field_width)
                elif self.learn_current is None:
                    self.spawn_word(field_width)
            return
        self.spawn_timer-=dt
        if self.spawn_timer<=0 and sum(w.state==WordState.FALLING for w in self.words)<self.max_words():
            self.spawn_word(field_width); self.spawn_timer=self.spawn_interval()
        for w in self.words:
            if w.state==WordState.FALLING:
                w.update(dt)
                if w.y>=self.field_height: self.lose_life(w)
        now=time.monotonic()
        self.words=[w for w in self.words if w.state==WordState.FALLING
                    or w.resolve_time is None
                    or now-w.resolve_time<CONFIG["explosion_time"]]
        if self.lives<=0 and not self.infinite_lives: self.game_over=True
    def _spawn_specific(self,entry,field_width):
        parts=make_parts(entry["de"],entry); prompt=" == ".join(parts)
        label=f"[ {prompt} ]"
        x=max(0,min(field_width-display_width(label)-2,2))
        w=FallingWord(entry,prompt,entry["de"],x,0,time.monotonic(),self.field_height,
                      spawn_clock=self.clock,
                      parts=parts,colors=random_word_colors())
        self.words.append(w); self.learn_current=w; self.words_seen.add(entry["de"])
        self.progress.record_seen(entry["de"])
        if SPAWN_HOOK:
            try: SPAWN_HOOK(entry["de"])
            except Exception: pass
    def summary(self):
        total=self.correct_count+self.mistakes
        accuracy=100*self.correct_count/total if total else 0
        return {"score":self.score,"level":self.level,"correct":self.correct_count,
                "mistakes":self.mistakes,"accuracy":accuracy,"words_seen":len(self.words_seen),
                "missed":sorted(self.missed_log.items(),key=lambda x:-x[1])}
