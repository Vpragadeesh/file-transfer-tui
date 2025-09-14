#!/usr/bin/env python3
"""
Minimal, stable CLI for PyShare.
- Starts server by default
- Commands: start, stop, dir, port, url, qr, help, quit
"""
import http.server
import socketserver
import multiprocessing
import os
import socket
from io import StringIO
import qrcode


def run_server(directory: str, port: int):
    os.chdir(directory)

    class QuietHandler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, format: str, *args) -> None:
            return

    with socketserver.TCPServer(("", port), QuietHandler) as httpd:
        httpd.serve_forever()


def get_local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def generate_qr_ascii(url: str) -> str:
    if not url:
        return "(stopped)"
    qr = qrcode.QRCode(border=1)
    qr.add_data(url)
    qr.make(fit=True)
    f = StringIO()
    qr.print_ascii(out=f)
    f.seek(0)
    return f.read()


class PyShareCLI:
    def __init__(self):
        self.shared_dir = os.getcwd()
        self.port = 8000
        self.proc = None
        self.url = ""
        self.start_server()

    def start_server(self):
        if self.proc and self.proc.is_alive():
            print("Server already running")
            return
        p = multiprocessing.Process(target=run_server, args=(self.shared_dir, self.port))
        p.daemon = True
        p.start()
        self.proc = p
        self.url = f"http://{get_local_ip()}:{self.port}"
        print(f"Started server at {self.url}, serving {self.shared_dir}")

    def stop_server(self):
        if self.proc and self.proc.is_alive():
            self.proc.terminate()
            self.proc.join(timeout=1)
            print("Server stopped")
        else:
            print("Server is not running")
        self.proc = None
        self.url = ""

    def repl(self):
        print("PyShare CLI — type 'help' for commands. Server started by default.")
        while True:
            try:
                cmd = input("> ").strip().split()
            except (EOFError, KeyboardInterrupt):
                print()
                self.stop_server()
                break
            if not cmd:
                continue
            c = cmd[0].lower()
            if c in ("q", "quit", "exit"):
                self.stop_server()
                break
            if c in ("start",):
                self.start_server()
            elif c in ("stop",):
                self.stop_server()
            elif c in ("dir",):
                if len(cmd) > 1:
                    new = cmd[1]
                else:
                    new = input(f"Enter directory (current: {self.shared_dir}): ")
                if os.path.isdir(new):
                    self.shared_dir = new
                    print(f"Serving: {self.shared_dir}")
                    if self.proc and self.proc.is_alive():
                        self.stop_server()
                        self.start_server()
                else:
                    print("Not a directory")
            elif c in ("port",):
                if len(cmd) > 1:
                    new = cmd[1]
                else:
                    new = input(f"Enter port (current: {self.port}): ")
                try:
                    p = int(new)
                    if 1024 <= p <= 65535:
                        self.port = p
                        print(f"Port set to {self.port}")
                        if self.proc and self.proc.is_alive():
                            self.stop_server()
                            self.start_server()
                    else:
                        print("Port must be 1024-65535")
                except ValueError:
                    print("Invalid port")
            elif c in ("url",):
                print(self.url or "(stopped)")
            elif c in ("qr",):
                print(generate_qr_ascii(self.url))
            elif c in ("help", "h", "?",):
                print("Commands: start stop dir <path> port <num> url qr help quit")
            else:
                print("Unknown command")


if __name__ == "__main__":
    PyShareCLI().repl()
