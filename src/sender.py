import json
import socket
import threading
import time


DISCOVERY_PORT = 5000
DEFAULT_TCP_PORT = 5000
PROTOCOL = "boom-v1"


def encode_message(data: dict) -> bytes:
    """Кодирует JSON-сообщение для TCP."""
    return (
        json.dumps(data, ensure_ascii=False) + "\n"
    ).encode("utf-8")


def recv_json_line(sock: socket.socket) -> dict:
    """Читает одно JSON-сообщение, заканчивающееся переводом строки."""
    data = bytearray()

    while len(data) < 65536:
        chunk = sock.recv(1)

        if not chunk:
            raise ConnectionError("Соединение закрыто Receiver.")

        if chunk == b"\n":
            return json.loads(data.decode("utf-8"))

        data.extend(chunk)

    raise ValueError("Слишком длинное сообщение.")


class Sender:
    def __init__(self):
        self.devices = []
        self.connected_device = None

        self._lock = threading.Lock()
        self._scan_thread = None
        self._busy = False

    @property
    def busy(self):
        with self._lock:
            return self._busy

    def _set_busy(self, value):
        with self._lock:
            self._busy = value

    def scan(self, callback):
        """
        Ищет Receiver в отдельном потоке.
        callback(devices, error) вызывается после завершения поиска.
        """

        if self.busy:
            return False

        self._set_busy(True)
        self._scan_thread = threading.Thread(
            target=self._scan_worker,
            args=(callback,),
            daemon=True,
        )
        self._scan_thread.start()
        return True

    def _scan_worker(self, callback):
        found = {}
        error = None

        try:
            with socket.socket(
                socket.AF_INET, socket.SOCK_DGRAM
            ) as sock:
                sock.setsockopt(
                    socket.SOL_SOCKET,
                    socket.SO_BROADCAST,
                    1,
                )
                sock.settimeout(0.2)

                deadline = time.monotonic() + 4.0

                while time.monotonic() < deadline:
                    request = {
                        "type": "DISCOVER",
                        "protocol": PROTOCOL,
                    }

                    sock.sendto(
                        encode_message(request),
                        ("255.255.255.255", DISCOVERY_PORT),
                    )

                    listen_until = min(
                        time.monotonic() + 0.7, deadline
                    )

                    while time.monotonic() < listen_until:
                        try:
                            raw, address = sock.recvfrom(4096)
                        except socket.timeout:
                            break

                        try:
                            message = json.loads(
                                raw.decode("utf-8").strip()
                            )
                        except (ValueError, UnicodeDecodeError):
                            continue

                        if (
                            message.get("type") != "RECEIVER"
                            or message.get("protocol") != PROTOCOL
                        ):
                            continue

                        name = message.get("name", "Receiver")
                        port = message.get(
                            "tcp_port", DEFAULT_TCP_PORT
                        )

                        if (
                            not isinstance(name, str)
                            or not isinstance(port, int)
                            or isinstance(port, bool)
                            or not 1 <= port <= 65535
                        ):
                            continue

                        device = {
                            "name": name[:80],
                            "ip": address[0],
                            "port": port,
                        }

                        found[(address[0], port)] = device

        except OSError as exc:
            error = str(exc)

        finally:
            self.devices = list(found.values())
            self._set_busy(False)
            callback(self.devices.copy(), error)

    def connect(self, device, callback):
        """Проверяет доступность Receiver в фоновом потоке."""

        if self.busy:
            return False

        self._set_busy(True)

        threading.Thread(
            target=self._connect_worker,
            args=(device.copy(), callback),
            daemon=True,
        ).start()

        return True

    def _connect_worker(self, device, callback):
        try:
            # Проверяем TCP-доступность сервера.
            with socket.create_connection(
                (device["ip"], device["port"]), timeout=3
            ):
                pass

            self.connected_device = device
            callback(True, f'Подключено к {device["name"]}')

        except OSError as exc:
            self.connected_device = None
            callback(False, f"Ошибка подключения: {exc}")

        finally:
            self._set_busy(False)

    def explode(self, callback):
        """Отправляет Receiver команду смены изображения."""

        if self.busy:
            return False

        device = self.connected_device

        if device is None:
            callback(False, "Сначала подключись к Receiver.")
            return False

        self._set_busy(True)

        threading.Thread(
            target=self._explode_worker,
            args=(device.copy(), callback),
            daemon=True,
        ).start()

        return True

    def _explode_worker(self, device, callback):
        try:
            with socket.create_connection(
                (device["ip"], device["port"]), timeout=3
            ) as sock:
                sock.settimeout(3)

                sock.sendall(encode_message({
                    "type": "CHANGE_IMAGE",
                    "protocol": PROTOCOL,
                }))

                reply = recv_json_line(sock)

                if reply.get("status") != "OK":
                    raise RuntimeError(
                        reply.get("message", "Команда отклонена.")
                    )

            callback(True, "💥 Команда отправлена!")

        except (
            OSError,
            ValueError,
            RuntimeError,
            ConnectionError,
        ) as exc:
            self.connected_device = None
            callback(False, f"Ошибка отправки: {exc}")

        finally:
            self._set_busy(False)

    def disconnect(self):
        """Забывает выбранное устройство."""
        self.connected_device = None