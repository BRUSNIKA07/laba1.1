import json
import socket
import threading
import time

PORT = 5000
PROTOCOL = "boom-v1"


def send_message(sock, data):
    sock.sendall((json.dumps(data) + "\n").encode())


def recv_message(sock):
    data = b""
    while b"\n" not in data:
        chunk = sock.recv(4096)
        if not chunk:
            raise ConnectionError("Receiver отключился")
        data += chunk
    return json.loads(data.split(b"\n", 1)[0])


class Sender:
    def __init__(self):
        self.devices = []
        self.connected = None
        self.busy = False

    def scan(self, callback):
        if self.busy:
            return

        self.busy = True
        threading.Thread(
            target=self._scan, args=(callback,), daemon=True
        ).start()

    def _scan(self, callback):
        found = {}
        error = None

        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                sock.settimeout(0.5)

                end = time.monotonic() + 4

                while time.monotonic() < end:
                    request = {
                        "type": "DISCOVER",
                        "protocol": PROTOCOL
                    }
                    sock.sendto(
                        json.dumps(request).encode(),
                        ("255.255.255.255", PORT)
                    )

                    try:
                        data, addr = sock.recvfrom(4096)
                        msg = json.loads(data.decode())

                        if (
                            msg.get("type") == "RECEIVER"
                            and msg.get("protocol") == PROTOCOL
                        ):
                            device = {
                                "name": msg.get("name", "Receiver"),
                                "ip": addr[0],
                                "port": msg.get("tcp_port", PORT)
                            }
                            found[(addr[0], device["port"])] = device
                    except socket.timeout:
                        pass

        except OSError as exc:
            error = str(exc)

        self.devices = list(found.values())
        self.busy = False
        callback(self.devices, error)

    def connect(self, device, callback):
        if self.busy:
            return

        self.busy = True
        threading.Thread(
            target=self._connect,
            args=(device, callback),
            daemon=True
        ).start()

    def _connect(self, device, callback):
        try:
            with socket.create_connection(
                (device["ip"], device["port"]), timeout=3
            ):
                pass

            self.connected = device
            callback(True, "Подключено к " + device["name"])

        except OSError as exc:
            self.connected = None
            callback(False, str(exc))

        finally:
            self.busy = False

    def explode(self, callback):
        if self.busy:
            return

        if not self.connected:
            callback(False, "Сначала подключись к Receiver")
            return

        self.busy = True
        threading.Thread(
            target=self._explode, args=(callback,), daemon=True
        ).start()

    def _explode(self, callback):
        try:
            with socket.create_connection(
                (self.connected["ip"], self.connected["port"]),
                timeout=3
            ) as sock:
                sock.settimeout(3)
                send_message(sock, {
                    "type": "CHANGE_IMAGE",
                    "protocol": PROTOCOL
                })

                reply = recv_message(sock)

                if reply.get("status") != "OK":
                    raise RuntimeError("Receiver отклонил команду")

            callback(True, "💥 Картинка переключена!")

        except (OSError, ValueError, RuntimeError) as exc:
            self.connected = None
            callback(False, "Ошибка: " + str(exc))

        finally:
            self.busy = False

    def disconnect(self):
        self.connected = None