import math
import os
import socket
import struct
import time
from collections import defaultdict
from colorsys import hsv_to_rgb
from pathlib import Path

from dotenv import load_dotenv

from utils import get_nanoleaf_object

# Load environment variables
load_dotenv(Path(__file__).resolve().parent / ".env")
NL_IP = os.getenv("NANOLEAF_IP")
NL_TOKEN = os.getenv("NANOLEAF_TOKEN")
NL_UDP_PORT = int(os.getenv("NANOLEAF_UDP_PORT", 60222))

# Init NanoleafDigitalTwin
nl = get_nanoleaf_object()
layout = nl.get_layout()
print(layout)
panels = [p for p in layout['positionData'] if p['panelId'] 
# not in (7824,25891,35132)
]

# This starts the UDP extcontrol mode
nl.enable_extcontrol()

# Build adjacency graph based on proximity threshold
def build_adjacency(panels, threshold=75):
    graph = defaultdict(list)
    for p1 in panels:
        for p2 in panels:
            if p1['panelId'] == p2['panelId']:
                continue
            dx = p1['x'] - p2['x']
            dy = p1['y'] - p2['y']
            dist = math.hypot(dx, dy)
            if dist <= threshold:
                graph[p1['panelId']].append(p2['panelId'])
    return graph

adj_graph = build_adjacency(panels)
print(adj_graph)

def compute_ripple_levels(graph, origin_id):
    from collections import deque
    visited = {origin_id: 0}
    queue = deque([origin_id])

    while queue:
        node = queue.popleft()
        for neighbor in graph[node]:
            if neighbor not in visited:
                visited[neighbor] = visited[node] + 1
                queue.append(neighbor)
    return visited  # panelId -> ripple level

origin_id = 45933  # start ripple from here
ripple_levels = compute_ripple_levels(adj_graph, origin_id)
print(ripple_levels)

# Ripple params
PERIOD = 3.0                # seconds per wave
WAVES_PER_COLOR = 2
COLOR_CYCLE_TIME = PERIOD * WAVES_PER_COLOR
FPS = 30
TRANSITION = 5

# Networking
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# Re-init the 3 big squares
payload = struct.pack('>H', 3)
for p in [7824,25891,35132]:
    payload += struct.pack('>HBBBBH', p, 0, 0, 0, 0, 0)
sock.sendto(payload, (NL_IP, NL_UDP_PORT))

while True:
    t = time.time()

    # 🔁 Cycle color every N waves using HSV hue
    wave_index = int(t / COLOR_CYCLE_TIME)
    hue = (wave_index * 0.2) % 1.0  # rotate hue [0.0, 1.0]
    r_f, g_f, b_f = hsv_to_rgb(hue, 1.0, 1.0)
    COLOR = (int(r_f * 255), int(g_f * 255), int(b_f * 255))

    # Build UDP payload
    payload = struct.pack('>H', len(panels))
    for p in panels:
        lvl = ripple_levels.get(p['panelId'], 99)
        delay = lvl * 0.1
        wave_phase = (t - delay) % PERIOD
        intensity = (math.cos(2 * math.pi * wave_phase / PERIOD) + 1) / 2
        r, g, b = [int(intensity * c) for c in COLOR]
        payload += struct.pack('>HBBBBH', p['panelId'], r, g, b, 0, TRANSITION)

    sock.sendto(payload, (NL_IP, NL_UDP_PORT))
    time.sleep(1 / FPS)