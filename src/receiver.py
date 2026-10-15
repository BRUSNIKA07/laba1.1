import json
import socket
import threading
import queue
import pygame
import os
import sys

PORT = 5000
PROTOCOL = "boom-v1"
events = queue.Queue()
running = True

pygame.init()
screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
W, H = screen.get_size()

folder = os.path.join(
    getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "Images"
)

files = sorted(
    os.path.join(folder, f) for f in os.listdir(folder)
    if f.lower().endswith((".png", ".jpg", ".jpeg", ".bmp"))
)

images = [
    pygame.transform.scale(pygame.image.load(f).convert(), (W, H))
    for f in files[:2]
]
current = 0


def client(conn):
    with conn:
        try:
            msg = b""
            while b"\n" not in msg:
                part = conn.recv(4096)
                if not part:
                    return
                msg += part

            data = json.loads(msg.split(b"\n")[0])
            ok = data.get("protocol") == PROTOCOL and data.get("type") == "CHANGE_IMAGE"
            if ok:
                events.put(1)

            conn.sendall((json.dumps({"status": "OK" if ok else "ERROR"}) + "\n").encode())
        except (OSError, ValueError):
            pass


def tcp():
    with socket.socket() as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(("", PORT))
        s.listen()
        s.settimeout(1)
        while running:
            try:
                conn, _ = s.accept()
                threading.Thread(target=client, args=(conn,), daemon=True).start()
            except socket.timeout:
                pass
            except OSError:
                break


def discovery():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind(("", PORT))
        s.settimeout(1)
        while running:
            try:
                raw, addr = s.recvfrom(4096)
                msg = json.loads(raw.decode())
                if msg.get("type") == "DISCOVER" and msg.get("protocol") == PROTOCOL:
                    reply = {"type": "RECEIVER", "protocol": PROTOCOL,
                             "name": "My Receiver", "tcp_port": PORT}
                    s.sendto((json.dumps(reply) + "\n").encode(), addr)
            except (socket.timeout, OSError, ValueError):
                pass


threading.Thread(target=tcp, daemon=True).start()
threading.Thread(target=discovery, daemon=True).start()

clock = pygame.time.Clock()
try:
    while running:
        for e in pygame.event.get():
            if e.type == pygame.QUIT or (e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE):
                running = False

        while not events.empty():
            events.get()
            current = 1 - current

        screen.blit(images[current], (0, 0))
        pygame.display.flip()
        clock.tick(60)
finally:
    running = False
    pygame.quit()