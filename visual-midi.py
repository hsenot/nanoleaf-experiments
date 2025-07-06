import os
import socket
from pathlib import Path
from random import randint
from time import sleep

import mido
from dotenv import load_dotenv

from utils import get_nanoleaf_object

# Load environment variables
load_dotenv(Path(__file__).resolve().parent / ".env")
NL_IP = os.getenv("NANOLEAF_IP")
NL_TOKEN = os.getenv("NANOLEAF_TOKEN")
NL_UDP_PORT = int(os.getenv("NANOLEAF_UDP_PORT", 60222))
CAMERA_INDEX = int(os.getenv("CAMERA_INDEX", 1))

# Init NanoleafDigitalTwin
nl = get_nanoleaf_object()
layout = nl.get_layout()
print(layout)

# This starts the UDP extcontrol mode
nl.enable_extcontrol()

panel_ids = [i for i in nl.get_ids() if i!=0]
print(panel_ids)
n_panels = len(panel_ids)
n_panels_b = n_panels.to_bytes(2, "big")


def test_udp():
    nanoleaf_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, 0)
    while True:

        send_data = b""
        send_data += n_panels_b
        transition = 10

        for panel_id in panel_ids:
            if panel_id != 0:
                panel_id_b = panel_id.to_bytes(2, "big")
                send_data += panel_id_b
                red = randint(40, 255)
                send_data += red.to_bytes(1, "big")
                green = randint(40, 255)
                send_data += green.to_bytes(1, "big")
                blue =randint(40, 255)
                send_data += blue.to_bytes(1, "big")
                white = randint(0, 0)
                send_data += white.to_bytes(1, "big")
                send_data += transition.to_bytes(2, "big")

        print(send_data)

        nanoleaf_socket.sendto(send_data, (NL_IP, NL_UDP_PORT))
        sleep(1)

    nanoleaf_socket.close()


def map_key_to_panel(key):
    return panel_ids[key % n_panels]

def send_color_to_panel(sock, p_id, rgb, transition=10):
    send_data = b""
    one_panel = 1
    white = 0
    send_data += one_panel.to_bytes(2, "big")

    if not rgb:
        red = randint(40, 255)
        green = randint(40, 255)
        blue = randint(40, 255)
    else:
        red, green, blue = rgb

    send_data += p_id.to_bytes(2, "big")
    send_data += red.to_bytes(1, "big")
    send_data += green.to_bytes(1, "big")
    send_data += blue.to_bytes(1, "big")
    send_data += white.to_bytes(1, "big")
    send_data += transition.to_bytes(2, "big")
    sock.sendto(send_data, (NL_IP, NL_UDP_PORT))

# This seems to change from session to session ..
print("Available MIDI input ports:")
for port in mido.get_input_names():
    print(port)

# Listen to MIDI
with mido.open_input('Launchkey Mini MK3:Launchkey Mini MK3 Launchkey Mi 16:0') as port:
    nanoleaf_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, 0)
    while True:
        msg = port.receive()
        if msg.type == 'note_on' and msg.velocity > 0:
            print(msg)
            send_color_to_panel(nanoleaf_socket, map_key_to_panel(int(msg.note)), None, 1)
        elif msg.type in ('note_off', 'note_on') and msg.velocity == 0:
            send_color_to_panel(nanoleaf_socket, map_key_to_panel(int(msg.note)), (0,0,0), 25)

    nanoleaf_socket.close()