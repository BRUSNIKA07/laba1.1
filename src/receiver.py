import json
import socket
import threading
import queue
import pygame
import os

PORT = 5000
PROTOCOL = "boom-v1"
events = queue.Queue()
running = True

pygame.init()
screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
W, H = screen.get_size()

folder = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Images")
files = [os.path.join(folder, f) for f in os.listdir(folder)
         if f.lower().endswith((".png", ".jpg", ".jpeg"))][:2]

images = [
    pygame.transform.scale(pygame.image.load(f).convert(), (W, H))
    for f in files
]

current = 0


def handle_client(conn):
    with conn:
        try:
            data = b""
            while b"\n" not in data:
                chunk = conn.recv(4096)
                if not chunk:
                    return
                data += chunk

            msg = json.loads(data.split(b"\n")[0])

            if msg.get("protocol") == PROTOCOL and msg.get("type") == "CHANGE_IMAGE":
                events.put(1)
                reply = {"status": "OK"}
            else:
                reply = {"status": "ERROR"}

            conn.sendall((json.dumps(reply) + "\n").encode())
        except (OSError, ValueError):
            pass


def tcp_server():
    with socket.socket() as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(("", PORT))
        s.listen()

        while running:
            try:
                s.settimeout(1)
                conn, _ = s.accept()
                threading.Thread(target=handle_client, args=(conn,), daemon=True).start()
            except socket.timeout:
                pass


def discovery_server():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind(("", PORT))
        s.settimeout(1)

        while running:
            try:
                data, addr = s.recvfrom(4096)
                msg = json.loads(data.decode())

                if msg.get("type") == "DISCOVER" and msg.get("protocol") == PROTOCOL:
                    reply = {
                        "type": "RECEIVER",
                        "protocol": PROTOCOL,
                        "name": "My Receiver",
                        "tcp_port": PORT
                    }
                    s.sendto((json.dumps(reply) + "\n").encode(), addr)
            except (socket.timeout, OSError, ValueError):
                pass


threading.Thread(target=tcp_server, daemon=True).start()
threading.Thread(target=discovery_server, daemon=True).start()

try:
    while running:
        for e in pygame.event.get():
            if e.type == pygame.QUIT or (
                e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE
            ):
                running = False

        while not events.empty():
            events.get()
            current = 1 - current

        screen.blit(images[current], (0, 0))
        pygame.display.flip()
finally:
    running = False
    pygame.quit()