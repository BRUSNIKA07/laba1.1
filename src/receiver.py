import socket
import threading

HOST = "0.0.0.0"
PORT = 5000

clients = []
lock = threading.Lock()


def broadcast(message, sender):
    data = (message + "\n").encode("utf-8")

    with lock:
        targets = list(clients)

    for client in targets:
        if client != sender:
            try:
                client.sendall(data)
            except OSError:
                pass


def handle_client(client, address):
    print(f"Подключился: {address}")

    try:
        with client:
            file = client.makefile("r", encoding="utf-8")

            for line in file:
                message = line.rstrip("\r\n")
                print(f"{address}: {message}")
                broadcast(message, client)

    except (OSError, UnicodeError):
        pass
    finally:
        with lock:
            if client in clients:
                clients.remove(client)

        broadcast("[Игрок отключился]", client)
        print(f"Отключился: {address}")


server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind((HOST, PORT))
server.listen()

print(f"Сервер запущен на порту {PORT}")

try:
    while True:
        client, address = server.accept()

        with lock:
            clients.append(client)

        threading.Thread(
            target=handle_client,
            args=(client, address),
            daemon=True
        ).start()

except KeyboardInterrupt:
    print("Сервер остановлен")
finally:
    server.close()