import json
import socket
import threading
import random
import queue
import pygame


DISCOVERY_PORT = 5000
TCP_PORT = 5000
PROTOCOL = "boom-v1"

WIDTH, HEIGHT = 800, 600

COLORS = [
    (255, 60, 60),
    (60, 220, 100),
    (60, 120, 255),
    (255, 220, 50),
    (220, 60, 255),
    (50, 220, 220),
]


def encode_message(data):
    return (
        json.dumps(data, ensure_ascii=False) + "\n"
    ).encode("utf-8")


def recv_json_line(sock):
    data = bytearray()

    while len(data) < 65536:
        chunk = sock.recv(1)

        if not chunk:
            raise ConnectionError("Connection closed")

        if chunk == b"\n":
            return json.loads(data.decode("utf-8"))

        data.extend(chunk)

    raise ValueError("Message too large")


class Receiver:
    def __init__(self):
        self.running = True
        self.events = queue.Queue()

        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Boom Receiver")

        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("Arial", 42, bold=True)

        self.background = (30, 30, 30)
        self.status = "Waiting for Sender..."

    # UDP: поиск ресивера
    def discovery_server(self):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("0.0.0.0", DISCOVERY_PORT))
            sock.settimeout(1)

            while self.running:
                try:
                    raw, address = sock.recvfrom(4096)
                    message = json.loads(raw.decode("utf-8").strip())

                    if (
                        message.get("type") != "DISCOVER"
                        or message.get("protocol") != PROTOCOL
                    ):
                        continue

                    response = {
                        "type": "RECEIVER",
                        "protocol": PROTOCOL,
                        "name": "My Receiver",
                        "tcp_port": TCP_PORT,
                    }

                    sock.sendto(encode_message(response), address)

                except socket.timeout:
                    continue
                except (OSError, ValueError):
                    if not self.running:
                        break

    # TCP: обработка команд
    def handle_client(self, conn, address):
        with conn:
            conn.settimeout(5)

            try:
                message = recv_json_line(conn)

                if message.get("protocol") != PROTOCOL:
                    conn.sendall(encode_message({
                        "status": "ERROR",
                        "message": "Invalid protocol",
                    }))
                    return

                if message.get("type") == "CHANGE_IMAGE":
                    self.events.put("CHANGE_IMAGE")
                    self.events.put(f"Command from {address[0]}")

                    conn.sendall(encode_message({
                        "status": "OK",
                        "message": "Image changed",
                    }))
                else:
                    conn.sendall(encode_message({
                        "status": "ERROR",
                        "message": "Unknown command",
                    }))

            except (OSError, ValueError, ConnectionError):
                pass

    def tcp_server(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind(("0.0.0.0", TCP_PORT))
            server.listen(10)
            server.settimeout(1)

            while self.running:
                try:
                    conn, address = server.accept()
                except socket.timeout:
                    continue
                except OSError:
                    break

                threading.Thread(
                    target=self.handle_client,
                    args=(conn, address),
                    daemon=True,
                ).start()

    # Pygame: отрисовка
    def draw(self):
        self.screen.fill(self.background)

        title = self.font.render(
            "BOOM RECEIVER",
            True,
            (255, 255, 255),
        )
        self.screen.blit(
            title,
            title.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 20)),
        )

        status_font = pygame.font.SysFont("Arial", 22)
        status_text = status_font.render(
            self.status, True, (240, 240, 240)
        )
        self.screen.blit(
            status_text,
            status_text.get_rect(center=(WIDTH // 2, HEIGHT - 60)),
        )

        pygame.display.flip()

    def run(self):
        threading.Thread(
            target=self.discovery_server, daemon=True
        ).start()

        threading.Thread(
            target=self.tcp_server, daemon=True
        ).start()

        try:
            while self.running:
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        self.running = False

                while not self.events.empty():
                    command = self.events.get_nowait()

                    if command == "CHANGE_IMAGE":
                        self.background = random.choice(COLORS)
                        self.status = "Image changed!"
                    else:
                        self.status = command

                self.draw()
                self.clock.tick(60)

        finally:
            self.running = False
            pygame.quit()


if __name__ == "__main__":
    Receiver().run()