import os
import time
from pathlib import Path

from dotenv import load_dotenv
from nanoleafapi import Nanoleaf
from zeroconf import ServiceBrowser, Zeroconf

# Automatically load .env from the same folder as this utils.py file
dotenv_path = Path(__file__).resolve().parent / '.env'
load_dotenv(dotenv_path)


class NanoleafListener:
    def __init__(self):
        self.devices = []

    def add_service(self, zeroconf, service_type, name):
        info = zeroconf.get_service_info(service_type, name)
        if info and 'nanoleaf' in name.lower():
            ip = ".".join(map(str, info.addresses[0]))
            print(f"Found Nanoleaf: {name} at {ip}")
            self.devices.append({'name': name, 'ip': ip})

    def update_service(self, zeroconf, service_type, name):
        # Required by Zeroconf >= 0.39 — safe to leave empty
        pass


def get_nanoleaf_credentials():
    zeroconf = Zeroconf()
    listener = NanoleafListener()
    browser = ServiceBrowser(zeroconf, "_nanoleafapi._tcp.local.", listener)
    time.sleep(2)  # Give time for discovery
    zeroconf.close()

    # auto-detect IP, fallback on env file
    if listener.devices:
        ip = listener.devices[0]['ip']
        print(f"IP from auto-detect: {ip}")
    else:
        ip = os.getenv("NANOLEAF_IP")
        print(f"IP from .end file: {ip}")

    token = os.getenv("NANOLEAF_TOKEN")
    if not ip or not token:
        raise ValueError("Missing NANOLEAF_IP or NANOLEAF_TOKEN in .env file")
    return ip, token


def get_nanoleaf_object():
    ip, token = get_nanoleaf_credentials()
    nl = Nanoleaf(ip, token)
    # clear any existing color
    nl.set_color((0,0,0))
    return nl


def map_layout_no_overlap(panels, viewport_size=(320, 240), gap_px=0, stretch=True):
    """
    Maps Nanoleaf panel layout to a webcam viewport.
    
    Parameters:
        panels (list): List of panel dicts with x, y, shapeType.
        viewport_size (tuple): (width, height) in pixels.
        gap_px (int): Margin inside each panel's bbox to avoid overlap.
        stretch (bool): 
            - If True: stretches layout to fill viewport (may distort shape)
            - If False: preserves aspect ratio and centers layout in viewport.
    
    Returns:
        List of dicts with mapped bbox and center in pixels.
    """
    # Define physical panel sizes in mm
    size_map_mm = {33: 130.0, 34: 65.0}  # large, small squares

    # Step 1: Compute layout bounds in mm
    xs, ys = [], []
    for p in panels:
        half = size_map_mm[p['shapeType']] / 2
        xs += [p['x'] - half, p['x'] + half]
        ys += [p['y'] - half, p['y'] + half]

    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    layout_w_mm = max_x - min_x
    layout_h_mm = max_y - min_y

    vp_w, vp_h = viewport_size

    # Step 2: Calculate scale and offset
    if stretch:
        scale_x = vp_w / layout_w_mm
        scale_y = vp_h / layout_h_mm
        offset_x = 0
        offset_y = 0
    else:
        scale = min(vp_w / layout_w_mm, vp_h / layout_h_mm)
        scale_x = scale_y = scale

        # Compute center offsets to align layout in the middle of viewport
        layout_px_w = layout_w_mm * scale
        layout_px_h = layout_h_mm * scale
        offset_x = (vp_w - layout_px_w) / 2
        offset_y = (vp_h - layout_px_h) / 2

    # Step 3: Map each panel
    mapped_panels = []
    for p in panels:
        size_mm = size_map_mm[p['shapeType']]

        # Scaled center position
        cx_px = (p['x'] - min_x) * scale_x + offset_x
        cy_px = (p['y'] - min_y) * scale_y + offset_y

        # Scaled panel size in px
        half_w_px = (size_mm * scale_x) / 2
        half_h_px = (size_mm * scale_y) / 2

        # Apply optional inner gap
        half_w_px -= gap_px / 2
        half_h_px -= gap_px / 2

        # Compute bounding box (rounded)
        bbox = (
            round(cx_px - half_w_px),
            round(cy_px - half_h_px),
            round(cx_px + half_w_px),
            round(cy_px + half_h_px)
        )

        mapped_panels.append({
            "panelId": p["panelId"],
            "shapeType": p["shapeType"],
            "center": (round(cx_px), round(cy_px)),
            "bbox": bbox
        })

    return mapped_panels
