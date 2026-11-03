"""Lanzador: arranca el servidor local y abre el navegador."""
import os
import socket
import sys
import threading
import webbrowser

from app import db
from app.server import app

HOST, PORT = "127.0.0.1", 8765

if sys.stdout is None or sys.stderr is None:  # versión instalada sin consola
    sys.stdout = sys.stderr = open(os.devnull, "w")


def port_in_use():
    with socket.socket() as s:
        return s.connect_ex((HOST, PORT)) == 0


if __name__ == "__main__":
    url = f"http://{HOST}:{PORT}"
    if port_in_use():
        print("El diario ya está abierto; abriendo el navegador.")
        webbrowser.open(url)
    else:
        db.init()
        print(f"Diario de Trading en {url}\nDatos en: {db.DATA_DIR}\nCierra esta ventana para detenerlo.")
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
        app.run(host=HOST, port=PORT, debug=False)
