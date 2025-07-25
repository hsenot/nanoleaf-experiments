import os
import socket
import struct
import time
from pathlib import Path

import cv2
import numpy as np
import sounddevice as sd
from dotenv import load_dotenv
from scipy.signal import sawtooth

from utils import get_nanoleaf_object, map_layout_no_overlap

# Load environment variables
load_dotenv(Path(__file__).resolve().parent / ".env")
NL_IP = os.getenv("NANOLEAF_IP")
NL_TOKEN = os.getenv("NANOLEAF_TOKEN")
CAMERA_INDEX = int(os.getenv("CAMERA_INDEX", 1))
NL_UDP_PORT = int(os.getenv("NANOLEAF_UDP_PORT", 60222))

# Init Nanoleaf object and UDP mode
nl = get_nanoleaf_object()
layout = [p for p in nl.get_layout()['positionData'] if p['panelId'] != 0]
#print(layout)
nl.enable_extcontrol()
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# Assume your final viewport is width × height
# Is performance much impacted by viewport size? => display FPS to understand that
viewport_width = 640
viewport_height = 480
SAMPLE_RATE = 44100
FRAME_SIZE = 1024

def dominant_color(block): #mean
    # OpenCV returns BGR
    return tuple(map(int, block.mean(axis=(0, 1))[::-1]))

# Map each panel to normalized screen space
# stretching so as to maximise the useful area of the viewport
panel_map = map_layout_no_overlap(layout, viewport_size=(viewport_width, viewport_height), stretch=False)
print(panel_map)

# Map panel IDs to note frequencies
panel_note_map = {
    56018: 261.63,  # C4
    30027: 293.66,  # D4
    56570: 329.63,  # E4
}

# Active state: panel_id -> bool
active_panels = {pid: False for pid in panel_note_map}

# Store tone settings and phase per panel
note_phases = {pid: 0.0 for pid in panel_note_map}
note_freqs = panel_note_map.copy()


# Adjustable tone generator
def generate_pleasant_wave(freq, t, phase):
    # Single blended waveform: sine + triangle
    waveform = (
        0.5 * np.sin(2 * np.pi * freq * t + phase) +
        0.3 * sawtooth(2 * np.pi * freq * t + phase, 0.5)
    )
    return waveform

def audio_callback(outdata, frames, time_info, status):
    global note_phases
    t = np.arange(frames) / SAMPLE_RATE
    out = np.zeros(frames)

    for pid, freq in note_freqs.items():
        if active_panels.get(pid):
            phase = note_phases[pid]
            wave = generate_pleasant_wave(freq, t, phase)
            out += wave
            note_phases[pid] = (phase + 2 * np.pi * freq * frames / SAMPLE_RATE) % (2 * np.pi)

    # Apply global soft fade-in/out on the entire output buffer if desired
    out *= 0.3  # final volume
    outdata[:] = out.reshape(-1, 1)


# Start audio stream in background
stream = sd.OutputStream(
    channels=1,
    callback=audio_callback,
    samplerate=SAMPLE_RATE,
    blocksize=FRAME_SIZE
)
stream.start()

def is_skin_tone(r, g, b):
    # OpenCV uses BGR → HSV
    bgr = np.uint8([[[b, g, r]]])
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)[0][0]
    h, s, v = hsv

    return (
        0 <= h <= 25 and
        20 <= s <= 150 and
        v >= 150
    )

# UDP is bloody fast
# 0 transition to too choppy, 5 transition is too laggy
def send_colors_to_panels(sock, rgbs, transition=2):
    payload = struct.pack('>H', len(panel_map))

    for p in panel_map:
        r, g, b = rgbs[p['panelId']]
        payload += struct.pack('>HBBBBH', p['panelId'], r, g, b, 0, transition)

    sock.sendto(payload, (NL_IP, NL_UDP_PORT))


# Open the USB camera
cap = cv2.VideoCapture(CAMERA_INDEX)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, viewport_width)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, viewport_height)

print("🎥 Mood Mirror (Digital Twin) running... Press Ctrl+C to stop.")

try:
    # TODO: display the FPS and improve fluidity
    FPS = 30
    rgbs = {k['panelId']: None for k in panel_map}
    while True:
        ret, frame = cap.read()
        if not ret:
            print("❌ Could not read frame from webcam")
            break

        #frame = cv2.flip(frame, 1)  # Flip if needed
        preview = frame.copy()
        h, w, _ = frame.shape

        # Set colors to panels
        for p in panel_map:
            pid = p['panelId']
            x1,y1,x2,y2 = p['bbox']

            # Sample a portion of the viewport mapped to a square
            block = frame[y1:y2, x1:x2]
            # attempt at compensating the diluted average on larger squares
            # same sized object e.g. hand will impact less the color for larger squares
            # as their viewport is 4x the size of smaller squares ... 
            r, g, b = dominant_color(block)
            #r, g, b = apply_gamma((r, g, b))
            #r, g, b = boost_saturation(r, g, b, factor=1.5)

            # Check if this panel has a note assigned and is "pink"
            if pid in panel_note_map:
                is_pink = is_skin_tone(r, g, b)
                #is_pink= is_pinkish_block(block)
                if is_pink and not active_panels[pid]:
                    print(f"▶️ Start tone for panel {pid}")
                    cv2.circle(preview, (x1+5, y1+10), 5, (0, 255, 255), -1)  # yellow dot
                    active_panels[pid] = True
                elif not is_pink and active_panels[pid]:
                    print(f"⏹️ Stop tone for panel {pid}")
                    active_panels[pid] = False

            cv2.rectangle(preview, (x1, y1), (x2, y2), (int(b), int(g), int(r)), 2)
            cv2.putText(preview, str(pid), (x1, y1 + 10), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (255, 255, 255), 1)

            rgbs[pid] = (r, g, b)

        send_colors_to_panels(sock, rgbs)  # Push updates in one go (efficient)
        preview = cv2.flip(preview, 1)
        cv2.imshow("Webcam theremin Preview", preview)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
        time.sleep(1 / FPS)

except KeyboardInterrupt:
    print("\n🛑 Mood Mirror stopped by user.")

finally:
    cap.release()
    cv2.destroyAllWindows()
    stream.stop()
    stream.close()
