import time

from bluepy.btle import Peripheral

DEVICE_MAC = "11:75:58:58:01:A3"
CHAR_UUID = "49535343-8841-43f4-a8d4-ecbe34729bb3"
# P45 watch FF:A1:A0:05:96:87


def make_payload():
    header = bytes([0x01, 0x00])
    pixels = []
    for y in range(0, 32):
        x = y  # draw a diagonal
        pixels.extend([x, y, 255, 0, 0])  # red
    return header + bytes(pixels)


payload = make_payload()

# Send BLE chunks
def send_frame(payload):
    print("Connecting to Pixoo...")
    dev = Peripheral(DEVICE_MAC)
    char = dev.getCharacteristics(uuid=CHAR_UUID)[0]
    print("Connected. Sending frame...")

    for i in range(0, len(payload), 20):
        chunk = payload[i:i+20]
        char.write(chunk, withResponse=False)
        time.sleep(0.05)  # BLE safety delay

    print("Done.")
    dev.disconnect()

send_frame(payload)