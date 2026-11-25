"""Wortfall application entry point."""
import curses, locale, os, time
from config import CONFIG, PROGRESS_FILE
from vocab import load_vocab
from progress import Progress
from game import GameState
from input_handler import read_keys, handle_key
import renderer, audio, game, sfx
from renderer import draw, init_colors

CATEGORIES=["All","home","food","animals","people","family","places","nature","objects","time",
            "seasons","colors","verbs","numbers","body","clothes","adjectives","pronouns","questions",
            "greetings","weekdays","months","prepositions","connectors","transport","travel","school",
            "technology","shopping","leisure","daily","work"]

def run(stdscr):
    locale.setlocale(locale.LC_ALL,"")
    stdscr.nodelay(True); stdscr.keypad(True)
    try: curses.curs_set(0)
    except curses.error: pass
    init_colors(stdscr)
    game.set_solve_hook(audio.get_speaker().speak)   # speak each German word you type correctly
    game.set_event_hook(lambda name: sfx.get_sfx().play(name))  # native sound effects
    vocab=load_vocab(); progress=Progress(PROGRESS_FILE)
    category_index=0; articles=CONFIG["articles_mode"]; plural=CONFIG["plural_mode"]
    state=GameState(vocab,progress,articles_mode=articles,plural_mode=plural)
    mode="menu"; last=time.monotonic(); frame=1/CONFIG["fps"]
    esc_pending_until=0.0
    while True:
        now=time.monotonic(); dt=min(now-last,CONFIG["max_dt"]); last=now
        for key in read_keys(stdscr):
            # ESC pauses; a second ESC within 1.5s exits; a later ESC resumes.
            if key=="\x1b":
                if mode=="playing":
                    mode="paused"; esc_pending_until=time.monotonic()+1.5
                    state._feedback("Paused — ESC again exits, ESC later resumes",1.5); continue
                if mode=="paused":
                    if time.monotonic()<=esc_pending_until:
                        progress.save(); audio.get_speaker().stop(); sfx.get_sfx().stop(); return
                    mode="playing"; esc_pending_until=0.0; continue
                if mode in ("menu","summary"):
                    if time.monotonic()<=esc_pending_until:
                        progress.save(); audio.get_speaker().stop(); sfx.get_sfx().stop(); return
                    esc_pending_until=time.monotonic()+1.5
                    state._feedback("Press ESC again within 1.5 seconds to exit (any other key cancels)",1.5)
                    continue
                continue
            elif esc_pending_until:
                esc_pending_until=0.0
            if mode=="menu":
                if key in ("\n","\r",curses.KEY_ENTER):
                    state=GameState(vocab,progress,[CATEGORIES[category_index]] if category_index else None,articles,plural)
                    state.field_height=max(1,stdscr.getmaxyx()[0]-6); mode="playing"
                elif isinstance(key,str) and key.lower()=="q": progress.save(); return
                elif isinstance(key,str) and key.lower()=="a":
                    articles={"required":"optional","optional":"off","off":"required"}[articles]
                    state.articles_mode=articles
                elif isinstance(key,str) and key.lower()=="p": plural=not plural; state.plural_mode=plural
                elif isinstance(key,str) and key.lower()=="u": renderer.URDU_SHAPED=not renderer.URDU_SHAPED
                elif key==(curses.KEY_F0+2): audio.get_speaker().toggle()
                elif key==(curses.KEY_F0+3): sfx.get_sfx().toggle()
                elif isinstance(key,str) and key.lower()=="c":
                    category_index=(category_index+1)%len(CATEGORIES)
                elif isinstance(key,str) and key.lower()=="l":
                    state=GameState(vocab,progress,[CATEGORIES[category_index]] if category_index else None,articles,plural,True)
                    state.field_height=max(1,stdscr.getmaxyx()[0]-6); mode="playing"
            elif mode=="paused":
                if isinstance(key,str) and key.lower()=="q": progress.save(); return
            elif mode=="summary":
                if key in ("\n","\r",curses.KEY_ENTER):
                    state=GameState(vocab,progress,[CATEGORIES[category_index]] if category_index else None,articles,plural)
                    state.field_height=max(1,stdscr.getmaxyx()[0]-6); mode="playing"
                elif isinstance(key,str) and key.lower()=="m": mode="menu"
                elif isinstance(key,str) and key.lower()=="q": progress.save(); return
            else:
                signal=handle_key(key,state)
                if signal=="quit": progress.save(); return
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
                    progress.update_high_score(state.score); progress.save(); mode="summary"
            else:
                state.paused=True
        label=CATEGORIES[category_index]
        draw(stdscr,state,mode,progress.data.get("high_score",0),label)
        spent=time.monotonic()-now
        if frame>spent: time.sleep(frame-spent)

def main():
    os.environ.setdefault("ESCDELAY","25")
    try: curses.wrapper(run)
    except KeyboardInterrupt:
        # curses.wrapper restores terminal; best-effort progress is saved during normal exits.
        pass
if __name__=="__main__": main()
