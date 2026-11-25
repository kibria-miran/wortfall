"""Wortfall application entry point."""
import curses
import locale
import os
import time

from config import CONFIG, PROGRESS_FILE
from vocab import load_vocab, count_words
from progress import Progress
from game import GameState
from input_handler import read_keys, handle_key
import renderer
import audio
import game
import sfx
from renderer import draw, init_colors

CATEGORIES=["All","home","food","animals","people","family","places","nature","objects","time",
            "seasons","colors","verbs","numbers","body","clothes","adjectives","pronouns","questions",
            "greetings","weekdays","months","prepositions","connectors","transport","travel","school",
            "technology","shopping","leisure","daily","work"]

def finish(progress,state):
    """Fold the session into the high score when it was played fairly (2.7)."""
    if state.recordable():
        progress.update_high_score(state.score)

def run(stdscr):
    stdscr.nodelay(True); stdscr.keypad(True)
    try: curses.curs_set(0)
    except curses.error: pass
    init_colors(stdscr)
    game.set_spawn_hook(audio.get_speaker().speak)   # hear each word as it spawns
    game.set_event_hook(lambda name: sfx.get_sfx().play(name))  # native sound effects
    vocab=load_vocab(); progress=Progress(PROGRESS_FILE)
    category_index=0; articles=CONFIG["articles_mode"]; plural=CONFIG["plural_mode"]
    recall=CONFIG["recall_mode"]; weighted=CONFIG["weak_word_review"]
    state=GameState(vocab,progress,articles_mode=articles,plural_mode=plural,
                    recall_mode=recall,weighted=weighted)
    mode="menu"; last=time.monotonic(); frame=1/CONFIG["fps"]
    esc_pending_until=0.0; summary_ready_at=0.0; last_save=last
    try:
        while True:
            now=time.monotonic(); dt=min(now-last,CONFIG["max_dt"]); last=now
            if now-last_save>CONFIG["autosave_seconds"]:
                progress.save(); last_save=now                  # 2.9 autosave
            for key in read_keys(stdscr):
                # ESC pauses the game; from menus it arms a double-press exit.
                if key=="\x1b":
                    if mode=="playing":
                        mode="paused"
                        state._feedback("Paused — any key resumes, Q saves & quits",2)
                        continue
                    if mode in ("menu","summary"):
                        if time.monotonic()<=esc_pending_until:
                            finish(progress,state)
                            progress.save(); audio.get_speaker().stop(); sfx.get_sfx().stop(); return
                        esc_pending_until=time.monotonic()+1.5
                        state._feedback("Press ESC again within 1.5 seconds to exit (any other key cancels)",1.5)
                        continue
                    continue
                elif esc_pending_until:
                    esc_pending_until=0.0
                if mode=="menu":
                    if key in ("\n","\r",curses.KEY_ENTER):
                        cats=[CATEGORIES[category_index]] if category_index else None
                        if count_words(vocab,cats,plural)==0:      # 2.15
                            state._feedback("No words with these settings — pick another category",2.5)
                            continue
                        state=GameState(vocab,progress,cats,articles,plural,recall_mode=recall,weighted=weighted)
                        state.field_height=max(1,stdscr.getmaxyx()[0]-6); mode="playing"
                    elif isinstance(key,str) and key.lower()=="q": finish(progress,state); progress.save(); return
                    elif isinstance(key,str) and key.lower()=="a":
                        articles={"required":"optional","optional":"off","off":"required"}[articles]
                        state.articles_mode=articles
                    elif isinstance(key,str) and key.lower()=="p":
                        candidate=not plural
                        cats=[CATEGORIES[category_index]] if category_index else None
                        if candidate and count_words(vocab,cats,True)==0:   # 2.15
                            state._feedback("No plurals in this category",2)
                        else:
                            plural=candidate; state.plural_mode=plural
                    elif isinstance(key,str) and key.lower()=="u": renderer.URDU_SHAPED=not renderer.URDU_SHAPED
                    elif isinstance(key,str) and key.lower()=="r":
                        recall=not recall; state.recall_mode=recall
                    elif isinstance(key,str) and key.lower()=="w":
                        weighted=not weighted; state.weighted=weighted
                    elif key==(curses.KEY_F0+2): audio.get_speaker().toggle()
                    elif key==(curses.KEY_F0+3): sfx.get_sfx().toggle()
                    elif isinstance(key,str) and key.lower()=="c":
                        for _ in range(len(CATEGORIES)):          # skip empty categories (2.15)
                            category_index=(category_index+1)%len(CATEGORIES)
                            cats=[CATEGORIES[category_index]] if category_index else None
                            if not plural or cats is None or count_words(vocab,cats,True)>0:
                                break
                    elif isinstance(key,str) and key.lower()=="l":
                        cats=[CATEGORIES[category_index]] if category_index else None
                        if count_words(vocab,cats,False)==0:
                            state._feedback("No words in this category",2)
                        else:
                            state=GameState(vocab,progress,cats,articles,plural,True,recall_mode=recall,weighted=weighted)
                            state.field_height=max(1,stdscr.getmaxyx()[0]-6); mode="playing"
                elif mode=="paused":
                    # any key resumes; only Q ends the session (2.12)
                    if isinstance(key,str) and key.lower()=="q":
                        finish(progress,state); progress.save()
                        audio.get_speaker().stop(); sfx.get_sfx().stop(); return
                    mode="playing"
                elif mode=="summary":
                    if time.monotonic()<summary_ready_at:        # 2.14: swallow leftover Enter
                        continue
                    if key in ("\n","\r",curses.KEY_ENTER):
                        cats=[CATEGORIES[category_index]] if category_index else None
                        if count_words(vocab,cats,plural)==0:
                            state._feedback("No words with these settings — pick another category",2.5)
                            continue
                        state=GameState(vocab,progress,cats,articles,plural,recall_mode=recall,weighted=weighted)
                        state.field_height=max(1,stdscr.getmaxyx()[0]-6); mode="playing"
                    elif isinstance(key,str) and key.lower()=="m": mode="menu"
                    elif isinstance(key,str) and key.lower()=="q": finish(progress,state); progress.save(); return
                else:
                    signal=handle_key(key,state)
                    if signal=="quit": finish(progress,state); progress.save(); return
                    if signal=="resize":
                        h,w=stdscr.getmaxyx(); state.field_height=max(1,h-6)
                        for word in state.words:
                            word.x=max(0,min(word.x,max(0,w-len(word.label())-2)))
                            word.y=max(0,min(word.y,state.field_height-0.1))
            if mode=="playing":
                h,w=stdscr.getmaxyx()
                if h>=24 and w>=80:
                    state.field_height=max(1,h-6); state.update(dt,w)
                    if state.game_over:
                        sfx.get_sfx().play("game_over")
                        finish(progress,state)
                        progress.save(); last_save=now
                        summary_ready_at=time.monotonic()+1.0    # 2.14
                        mode="summary"
                else:
                    state.paused=True
            label=CATEGORIES[category_index]
            draw(stdscr,state,mode,progress.data.get("high_score",0),label)
            spent=time.monotonic()-now
            if frame>spent: time.sleep(frame-spent)
    finally:
        try: progress.save()
        except Exception: pass

def main():
    locale.setlocale(locale.LC_ALL,"")          # before initscr (2.17)
    os.environ.setdefault("ESCDELAY","25")
    try: curses.wrapper(run)
    except KeyboardInterrupt:
        # progress is saved in run()'s finally block; terminal already restored (2.9)
        pass
if __name__=="__main__": main()
