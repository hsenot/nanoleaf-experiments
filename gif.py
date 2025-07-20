import os
import socket
import struct
import sys
import time
from pathlib import Path

import cv2
import numpy as np
from dotenv import load_dotenv
from PIL import Image, ImageSequence

from utils import get_nanoleaf_object, map_layout_no_overlap

# Load environment variables
load_dotenv(Path(__file__).resolve().parent / ".env")
NL_IP = os.getenv("NANOLEAF_IP")
NL_TOKEN = os.getenv("NANOLEAF_TOKEN")
NL_UDP_PORT = int(os.getenv("NANOLEAF_UDP_PORT", 60222))

GIF_PATH = "assets/rainbow.gif"
if len(sys.argv) == 2:
    GIF_PATH = "assets/"+sys.argv[1]

# Init Nanoleaf object and UDP mode
nl = get_nanoleaf_object()
layout = [p for p in nl.get_layout()['positionData'] if p['panelId'] != 0]
nl.enable_extcontrol()
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# Final display size (rescaled GIF size)
viewport_width = 640
viewport_height = 480

def dominant_color(block):
    return tuple(map(int, block.mean(axis=(0, 1))[::-1]))  # Convert BGR to RGB

panel_map = map_layout_no_overlap(layout, viewport_size=(viewport_width, viewport_height), stretch=False)
print(f"🟩 Panel map: {len(panel_map)} panels mapped.")

def send_colors_to_panels(sock, rgbs, transition=2):
    payload = struct.pack('>H', len(panel_map))
    for p in panel_map:
        r, g, b = rgbs[p['panelId']]
        payload += struct.pack('>HBBBBH', p['panelId'], r, g, b, 0, transition)
    sock.sendto(payload, (NL_IP, NL_UDP_PORT))

# --- Load GIF frames using PIL ---
gif = Image.open(GIF_PATH)
frames = []
durations = []

for frame in ImageSequence.Iterator(gif):
    rgb_frame = frame.convert("RGB")
    np_frame = np.array(rgb_frame)
    # The red/blue channel flip is due to OpenCV using BGR, while PIL and Nanoleaf expect RGB
    resized = cv2.cvtColor(cv2.resize(np_frame, (viewport_width, viewport_height)), cv2.COLOR_BGR2RGB)
    flipped = cv2.flip(resized, 1)
    frames.append(flipped)
    durations.append(frame.info.get("duration", 100))  # Duration in ms

print(f"🎞️ Loaded {len(frames)} GIF frames")

# --- Loop through GIF frames ---
rgbs = {k['panelId']: None for k in panel_map}
print("🎥 Playing animated GIF to Nanoleaf. Press Ctrl+C to stop.")

try:
    while True:
        for i, frame in enumerate(frames):
            preview = frame.copy()
            h, w, _ = frame.shape

            for p in panel_map:
                pid = p['panelId']
                x1, y1, x2, y2 = p['bbox']
                block = frame[y1:y2, x1:x2]
                r, g, b = dominant_color(block)

                # Draw overlay for debugging
                cv2.rectangle(preview, (x1, y1), (x2, y2), (int(b), int(g), int(r)), 2)
                cv2.putText(preview, str(pid), (x1, y1 + 10), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 255, 255), 1)
                rgbs[pid] = (r, g, b)

            send_colors_to_panels(sock, rgbs)
            preview = cv2.flip(preview, 1)
            cv2.imshow("GIF Mood Preview", preview)

            delay = durations[i] / 1000.0
            if cv2.waitKey(int(delay * 1000)) & 0xFF == ord('q'):
                raise KeyboardInterrupt
            time.sleep(delay)

except KeyboardInterrupt:
    print("\n🛑 Playback stopped by user.")

finally:
    cv2.destroyAllWindows()
