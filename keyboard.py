import os
import socket
import struct
from pathlib import Path
from random import randint

from dotenv import load_dotenv
from pynput import keyboard

from utils import get_nanoleaf_object

# Load environment variables
load_dotenv(Path(__file__).resolve().parent / ".env")
NL_IP = os.getenv("NANOLEAF_IP")
NL_TOKEN = os.getenv("NANOLEAF_TOKEN")
NL_UDP_PORT = int(os.getenv("NANOLEAF_UDP_PORT", 60222))

# Corrected 3 columns x 5 rows grid mapping
grid_to_panel = {
    (0,0): 22456, (1,0): 42052, (2,0): 59244,
    (0,1): 42908, (1,1): 22942, (2,1): 42484,
    (0,2): 57447, (1,2): 14592, (2,2): 45431,
    (0,3): 5958,  (1,3): 45933, (2,3): 7160,
    (0,4): 56570, (1,4): 22098, (2,4): 8025,
}

# Track active key
active_keys = set()

# Init Nanoleaf object and UDP mode
nl = get_nanoleaf_object()
all_panel_ids = [p['panelId'] for p in nl.get_layout()['positionData']]
panel_map = [p for p in nl.get_layout()['positionData'] if p['panelId'] in grid_to_panel.values()]
#print(layout)
nl.enable_extcontrol()
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

def send_colors_to_panels(sock, panel_ids, color, transition=2):
    payload = struct.pack('>H', len(panel_ids))
    r, g, b = color

    for p in panel_ids:
        payload += struct.pack('>HBBBBH', p, r, g, b, 0, transition)

    sock.sendto(payload, (NL_IP, NL_UDP_PORT))


# Letter definitions in 3-wide × 5-high grid
letter_map = {
    # Letters A–Z
    "A": [(1,0), (0,1), (2,1), (0,2), (1,2), (2,2), (0,3), (2,3), (0,4), (2,4)],
    "B": [(0,0), (1,0), (0,1), (2,1), (0,2), (1,2), (2,2), (0,3), (2,3), (0,4), (1,4)],
    "C": [(1,0), (2,0), (0,1), (0,2), (0,3), (1,4), (2,4)],
    "D": [(0,0), (1,0), (0,1), (2,1), (0,2), (2,2), (0,3), (2,3), (0,4), (1,4)],
    "E": [(0,0), (1,0), (2,0), (0,1), (0,2), (1,2), (0,3), (0,4), (1,4), (2,4)],
    "F": [(0,0), (1,0), (2,0), (0,1), (0,2), (1,2), (0,3), (0,4)],
    "G": [(1,0), (2,0), (0,1), (0,2), (0,3), (1,3), (2,3), (2,2), (1,4), (2,4)],
    "H": [(0,0), (2,0), (0,1), (2,1), (0,2), (1,2), (2,2), (0,3), (2,3), (0,4), (2,4)],
    "I": [(0,0), (1,0), (2,0), (1,1), (1,2), (1,3), (0,4), (1,4), (2,4)],
    "J": [(0,0), (1,0), (2,0), (1,1), (1,2), (1,3), (0,4), (1,4)],
    "K": [(0,0), (0,1), (0,2), (1,2), (2,0), (1,1), (2,3), (1,3), (0,4), (2,4)],
    "L": [(0,0), (0,1), (0,2), (0,3), (0,4), (1,4), (2,4)],
    "M": [(0,0), (2,0), (0,1), (1,1), (2,1), (0,2), (2,2), (0,3), (2,3), (0,4), (2,4)],
    "N": [(0,0), (2,0), (0,1), (1,1), (2,1), (0,2), (1,2), (2,2), (0,3), (2,3), (0,4), (2,4)],
    "O": [(1,0), (0,1), (2,1), (0,2), (2,2), (0,3), (2,3), (1,4)],
    "P": [(0,0), (1,0), (0,1), (2,1), (0,2), (1,2), (0,3), (0,4)],
    "Q": [(1,0), (0,1), (2,1), (0,2), (2,2), (1,3), (2,3), (0,4), (2,4)],
    "R": [(0,0), (1,0), (0,1), (2,1), (0,2), (1,2), (0,3), (1,3), (2,3), (0,4), (2,4)],
    "S": [(1,0), (2,0), (0,1), (1,2), (2,2), (2,3), (0,4), (1,4)],
    "T": [(0,0), (1,0), (2,0), (1,1), (1,2), (1,3), (1,4)],
    "U": [(0,0), (2,0), (0,1), (2,1), (0,2), (2,2), (0,3), (2,3), (1,4)],
    "V": [(0,0), (2,0), (0,1), (2,1), (0,2), (2,2), (1,3), (1,4)],
    "W": [(0,0), (2,0), (0,1), (2,1), (0,2), (1,2), (2,2), (0,3), (2,3), (1,4)],
    "X": [(0,0), (2,0), (1,1), (1,2), (1,3), (0,4), (2,4)],
    "Y": [(0,0), (2,0), (1,1), (1,2), (1,3), (1,4)],
    "Z": [(0,0), (1,0), (2,0), (2,1), (1,2), (0,3), (0,4), (1,4), (2,4)],

    # Digits 0–9
    "0": [(1,0), (0,1), (2,1), (0,2), (2,2), (0,3), (2,3), (1,4)],
    "1": [(1,0), (1,1), (1,2), (1,3), (1,4)],
    "2": [(1,0), (2,0), (2,1), (1,2), (0,3), (0,4), (1,4), (2,4)],
    "3": [(1,0), (2,0), (2,1), (1,2), (2,2), (2,3), (1,4)],
    "4": [(2,0), (0,1), (2,1), (1,2), (2,2), (2,3), (2,4)],
    "5": [(0,0), (1,0), (2,0), (0,1), (1,1), (2,2), (2,3), (0,4), (1,4)],
    "6": [(1,0), (0,1), (0,2), (1,2), (2,2), (0,3), (2,3), (1,4)],
    "7": [(0,0), (1,0), (2,0), (2,1), (1,2), (1,3), (1,4)],
    "8": [(1,0), (0,1), (2,1), (1,2), (0,3), (2,3), (1,4)],
    "9": [(1,0), (0,1), (2,1), (1,2), (2,2), (2,3), (1,4)],
}


def on_press(key):
    send_colors_to_panels(sock, all_panel_ids, [0,0,0], transition=0)
    try:
        k = key.char.upper()
        if k in letter_map and k not in active_keys:
            panel_ids = [grid_to_panel[pos] for pos in letter_map[k]]
            send_colors_to_panels(sock, panel_ids, [randint(40, 255),randint(40, 255),randint(40, 255)], transition=2)
            active_keys.add(k)
    except AttributeError:
        pass  # special keys (ctrl, etc)

def on_release(key):
    try:
        k = key.char.upper()
        if k in letter_map and k in active_keys:
            panel_ids = [grid_to_panel[pos] for pos in letter_map[k]]
            send_colors_to_panels(sock, panel_ids, [0,0,0], transition=10)
            active_keys.remove(k)
    except AttributeError:
        pass

# Switch off all panels to start with
send_colors_to_panels(sock, all_panel_ids, [0,0,0], transition=10)

print("Listening for keys a-zfggfgfgfgfgfggfgfgfgfgfgfgffgfgfgfgfgfgfgfgfgfgffgfgfgfg and 0-9 on 3×5 grid...")
with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
    listener.join()

