"""get_wch-based input, preserving Unicode characters such as ä and ß."""
import curses
import audio
import sfx
BACKSPACE_KEYS={8,127,curses.KEY_BACKSPACE,"\x08","\x7f"}
def read_keys(stdscr):
    keys=[]
    while True:
        try: key=stdscr.get_wch()
        except curses.error: break
        keys.append(key)
    return keys
def handle_key(key,state):
    if key==curses.KEY_RESIZE: return "resize"
    if key==(curses.KEY_F0+2):                      # F2: pronunciation on/off
        on=audio.get_speaker().toggle(); state._feedback("Sound: ON" if on else "Sound: OFF",1.2); return None
    if key==(curses.KEY_F0+3):                      # F3: native sound effects on/off
        on=sfx.get_sfx().toggle(); state._feedback(f"SFX: {'ON' if on else 'OFF'} ({sfx.get_sfx().backend})",1.2); return None
    if key=="\t": state.toggle_infinite_lives(); return None   # Tab: infinite lives
    if key in ("+","="): state.change_speed(0.25); return None
    if key in ("-","_"): state.change_speed(-0.25); return None
    if key in ("\x03",): return "quit"
    if key in BACKSPACE_KEYS: state.input_buffer=state.input_buffer[:-1]; return None
    if key in ("\n","\r",curses.KEY_ENTER): state.submit(); return None
    if key=="\x1b": return "pause"
    if key==" ": state.input_buffer=""; state._feedback("Typing reset",0.8); return None
    if isinstance(key,str) and key.isprintable() and len(state.input_buffer)<40:
        state.input_buffer+=key
        if state.try_match(state.input_buffer): state.input_buffer=""
    return None
