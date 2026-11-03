"""Lanzador: arranca el servidor local y abre el navegador."""
import json
import os
import socket
import sys
import threading
import time
import urllib.request
import webbrowser

from app import __version__, db
from app.server import app

HOST, PORT = "127.0.0.1", 8765
URL = f"http://{HOST}:{PORT}"

if sys.stdout is None or sys.stderr is None:  # versión instalada sin consola
    sys.stdout = sys.stderr = open(os.devnull, "w")


def port_in_use():
    with socket.socket() as s:
        return s.connect_ex((HOST, PORT)) == 0


def running_version():
    try:
        with urllib.request.urlopen(URL + "/api/version", timeout=2) as r:
            return json.load(r).get("version")
    except Exception:
        return None  # versión antigua sin /api/version, u otro programa


def stop_running():
    """Cierra una copia anterior del diario para que no sirva una interfaz desactualizada."""
    try:
        urllib.request.urlopen(urllib.request.Request(URL + "/api/shutdown", method="POST"), timeout=2)
    except Exception:
        return False
    for _ in range(20):
        time.sleep(0.25)
        if not port_in_use():
            return True
    return False


if __name__ == "__main__":
    if port_in_use():
        if running_version() == __version__ or not stop_running():
            print("El diario ya está abierto; abriendo el navegador.")
            webbrowser.open(URL)
            sys.exit(0)
    db.init()
    print(f"Diario de Trading {__version__} en {URL}\nDatos en: {db.DATA_DIR}\nCierra esta ventana para detenerlo.")
    threading.Timer(1.0, lambda: webbrowser.open(URL)).start()
    app.run(host=HOST, port=PORT, debug=False)
