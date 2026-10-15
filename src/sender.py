import socket
import threading

HOST = input("IP сервера: ")
PORT = 5000

sock = socket.create_connection((HOST, PORT))


def receive():
    try:
        file = sock.makefile("r", encoding="utf-8")

        for line in file:
            print("\nПолучено:", line.rstrip())

    except OSError:
        pass

    print("Соединение закрыто")


threading.Thread(target=receive, daemon=True).start()

try:
    while True:
        message = input("> ")
        sock.sendall((message + "\n").encode("utf-8"))
except (KeyboardInterrupt, OSError):
    pass
finally:
    sock.close()