#!/usr/bin/env python3
"""
A lightweight Rich-based TUI for local file sharing.
- Start/stop simple HTTP server
- Change served directory
- Change port
- Show URL and ASCII QR

Run: python pyshare_rich.py
"""
import http.server
import socketserver
import multiprocessing
import os
import socket
import sys
from io import StringIO
from typing import Optional

import qrcode
from rich import box
from rich.align import Align
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt
from rich.live import Live
from rich.text import Text
from rich.layout import Layout

console = Console()


def run_server(directory: str, port: int):
    """Run a simple HTTP file server serving `directory` on `port`."""
    os.chdir(directory)

    class QuietHandler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, format: str, *args) -> None:
            return

    with socketserver.TCPServer(("", port), QuietHandler) as httpd:
        httpd.serve_forever()


def get_local_ip() -> str:
    """Return a reasonable local IP address or localhost fallback."""
    try:
        # connect to an external address (does not send data) to discover outbound IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def generate_qr_ascii(url: str) -> str:
    if not url:
        return "Server is stopped. Start it to see the QR code."
    qr = qrcode.QRCode(border=1)
    qr.add_data(url)
    qr.make(fit=True)
    fake = StringIO()
    qr.print_ascii(out=fake)
    fake.seek(0)
    return fake.read()


class PyShareRich:
    def __init__(self):
        self.shared_dir = os.getcwd()
        self.port = 8000
        self.server_proc: Optional[multiprocessing.Process] = None
        self.url = ""
        # Start the server by default
        try:
            self.start_server()
        except Exception:
            # don't crash on startup; leave server stopped
            self.server_proc = None

    def start_server(self):
        if self.server_proc and self.server_proc.is_alive():
            return
        proc = multiprocessing.Process(target=run_server, args=(self.shared_dir, self.port))
        proc.daemon = True
        proc.start()
        self.server_proc = proc
        self.url = f"http://{get_local_ip()}:{self.port}"

    def stop_server(self):
        if self.server_proc and self.server_proc.is_alive():
            self.server_proc.terminate()
            self.server_proc.join(timeout=1)
        self.server_proc = None
        self.url = ""

    def toggle_server(self):
        if self.server_proc and self.server_proc.is_alive():
            self.stop_server()
        else:
            self.start_server()

    def change_dir(self):
        new = console.input(f"Enter directory (current: {self.shared_dir}): ") or self.shared_dir
        if os.path.isdir(new):
            self.shared_dir = new
            if self.server_proc and self.server_proc.is_alive():
                self.stop_server()
                self.start_server()
        else:
            console.print(f"[red]'{new}' is not a directory[/red]")

    def change_port(self):
        new = console.input(f"Enter port (current: {self.port}): ") or str(self.port)
        try:
            p = int(new)
            if 1024 <= p <= 65535:
                self.port = p
                if self.server_proc and self.server_proc.is_alive():
                    self.stop_server()
                    self.start_server()
            else:
                console.print("[red]Port must be 1024-65535[/red]")
        except ValueError:
            console.print("[red]Invalid port[/red]")

    def render(self) -> Panel:
        table = Table.grid(expand=True)
        status = "Running" if self.server_proc and self.server_proc.is_alive() else "Stopped"
        status_text = Text(status, style="green" if status=="Running" else "red")
        table.add_row(Text("Status:"), status_text)
        table.add_row(Text("URL:"), Text(self.url or "(stopped)", style="cyan"))
        table.add_row(Text("Serving:"), Text(self.shared_dir))

        qr = generate_qr_ascii(self.url)
        qr_panel = Panel.fit(qr, title="QR", border_style="blue")

        layout = Layout()
        layout.split_column(
            Layout(Panel(table, title="PyShare"), ratio=2),
            Layout(qr_panel, ratio=3),
            Layout(Panel(Text("Commands: [s] Start/Stop  [d] Directory  [p] Port  [q] Quit"), box=box.SIMPLE), ratio=1),
        )
        return Panel(layout, box=box.ROUNDED)

    def _get_single_key(self) -> str:
        """Read a single keypress without waiting for Enter (POSIX)."""
        if os.name == "posix":
            import tty, termios

            fd = sys.stdin.fileno()
            old = termios.tcgetattr(fd)
            try:
                tty.setraw(fd)
                ch = sys.stdin.read(1)
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old)
            return ch
        elif os.name == "nt":
            # Windows single-key
            import msvcrt

            ch = msvcrt.getch()
            try:
                return ch.decode()
            except Exception:
                return ""
        # Fallback: ask for a line
        return Prompt.ask("Command (s/d/p/q)").strip()

    def run(self):
        # Use screen=False to avoid switching to the terminal's alternate screen,
        # which can cause flicker and glitches on some terminals.
        with Live(self.render(), refresh_per_second=4, screen=False) as live:
            while True:
                try:
                    # Ensure UI is rendered before blocking for input
                    live.update(self.render())
                    # Use single-key input so users don't need to press Enter
                    key = self._get_single_key().strip().lower()
                    if not key:
                        live.update(self.render())
                        continue
                    if key == "s":
                        self.toggle_server()
                    elif key == "d":
                        # Directory change requires full-line input; pause live
                        live.stop()
                        self.change_dir()
                        live.start()
                    elif key == "p":
                        live.stop()
                        self.change_port()
                        live.start()
                    elif key == "q":
                        self.stop_server()
                        break
                    else:
                        console.print("Unknown command")
                    live.update(self.render())
                except (KeyboardInterrupt, EOFError):
                    self.stop_server()
                    break


def main():
    app = PyShareRich()
    app.run()


if __name__ == "__main__":
    main()
