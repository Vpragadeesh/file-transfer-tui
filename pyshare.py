import http.server
import socketserver
import multiprocessing
import os
import netifaces
import qrcode
from io import StringIO
from pathlib import Path

from textual.app import App, ComposeResult
from textual.containers import Grid, Container
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Header, Static, Label, Input

# --- Server Process ---

def run_server(directory: str, port: int):
    """Target function to run the HTTP server in a separate process."""
    class QuietHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=directory, **kwargs)

        def log_message(self, format: str, *args) -> None:
            """Suppress server log messages."""
            pass

    with socketserver.TCPServer(("", port), QuietHTTPRequestHandler) as httpd:
        httpd.serve_forever()

# --- Utility Functions ---

def get_local_ip() -> str:
    """Finds the most likely local IP address."""
    try:
        for iface in netifaces.interfaces():
            ifaddrs = netifaces.ifaddresses(iface)
            if netifaces.AF_INET in ifaddrs:
                for link in ifaddrs[netifaces.AF_INET]:
                    ip = link.get('addr')
                    if ip and not ip.startswith('127.'):
                        return ip
    except Exception:
        return "?.?.?.?"
    return "?.?.?.?"

def generate_qr_code(url: str) -> str:
    """Generates an ASCII QR code from a URL."""
    if not url:
        return "Server is stopped. Start it to see the QR code."
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=1,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)
    
    # Create an in-memory text stream
    fake_file = StringIO()
    qr.print_ascii(out=fake_file)
    fake_file.seek(0)
    return fake_file.read()

# --- Modal Dialogs ---

class DirectoryDialog(ModalScreen[str]):
    """A modal dialog to ask for a directory path."""

    def compose(self) -> ComposeResult:
        with Grid(id="dialog"):
            yield Label("Enter new directory path:", id="dialog-label")
            yield Input(os.getcwd(), id="dialog-input")
            yield Button("OK", variant="primary", id="ok-button")
            yield Button("Cancel", id="cancel-button")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "ok-button":
            input_widget = self.query_one(Input)
            path = input_widget.value
            if os.path.isdir(path):
                self.dismiss(path)
            else:
                input_widget.placeholder = f"'{path}' is not a valid directory!"
                input_widget.value = ""
        else:
            self.dismiss()

class PortDialog(ModalScreen[int]):
    """A modal dialog to ask for a port number."""

    def compose(self) -> ComposeResult:
        with Grid(id="dialog"):
            yield Label("Enter new port (1024-65535):", id="dialog-label")
            yield Input("8000", id="dialog-input")
            yield Button("OK", variant="primary", id="ok-button")
            yield Button("Cancel", id="cancel-button")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "ok-button":
            input_widget = self.query_one(Input)
            port_str = input_widget.value
            try:
                port = int(port_str)
                if 1024 <= port <= 65535:
                    self.dismiss(port)
                else:
                    raise ValueError
            except ValueError:
                input_widget.placeholder = "Invalid port number!"
                input_widget.value = ""
        else:
            self.dismiss()

# --- Main Application ---

class PyShareApp(App):
    """A Textual TUI for sharing files locally."""

    CSS_PATH = "pyshare.css"
    BINDINGS = [
        ("s", "start_server", "Start"),
        ("t", "stop_server", "Stop"),
        ("d", "change_dir", "Directory"),
        ("p", "change_port", "Port"),
        ("q", "quit", "Quit"),
    ]

    # -- Reactive properties that update the UI automatically
    # Use proper type annotations and initial values with reactive(...)
    server_process: multiprocessing.Process | None = reactive(None)
    shared_dir: str = reactive(os.getcwd())
    port: int = reactive(8000)
    url: str = reactive("")

    def compose(self) -> ComposeResult:
        yield Header(name="PyShare - Local File Sharer")
        with Container(id="main-container"):
            yield Static("Status: [b]Stopped[/b]", id="status-line")
            yield Static("URL: (stopped)", id="url-line")
            yield Static("Serving: ...", id="dir-line") # Placeholder
            yield Static(id="qr-code-box")
        yield Footer()

    def on_mount(self) -> None:
        """Called when the app is first mounted. Set initial values here."""
        # Update the UI with initial values now that the DOM is ready.
        self.query_one("#dir-line").update(f"Serving: {self.shared_dir}")
        self.query_one("#qr-code-box").update(generate_qr_code(self.url))

    # -- Watch methods for reactive properties
    def watch_server_process(self, new_process: multiprocessing.Process | None) -> None:
        """Update UI based on server status."""
        status_line = self.query_one("#status-line")
        url_line = self.query_one("#url-line")
        qr_box = self.query_one("#qr-code-box")

        if new_process and new_process.is_alive():
            self.url = f"http://{get_local_ip()}:{self.port}"
            status_line.update("Status: [b green]Running[/b green]")
            url_line.update(f"URL: [@click=app.open_url('{self.url}')]{self.url}[/]")
            qr_box.update(generate_qr_code(self.url))
        else:
            self.url = ""
            status_line.update("Status: [b red]Stopped[/b red]")
            url_line.update("URL: (stopped)")
            qr_box.update(generate_qr_code(self.url))

    def watch_shared_dir(self, new_dir: str) -> None:
        """Update directory line and restart server if running."""
        self.query_one("#dir-line").update(f"Serving: {new_dir}")
        if self.server_process and self.server_process.is_alive():
            self.action_stop_server()
            self.action_start_server()

    def watch_port(self, new_port: int) -> None:
        """Update port and restart server if running."""
        if self.server_process and self.server_process.is_alive():
            self.action_stop_server()
            self.action_start_server()

    # -- Action methods for key bindings
    def action_start_server(self) -> None:
        """Start the HTTP server in a background process."""
        if self.server_process and self.server_process.is_alive():
            return

        proc = multiprocessing.Process(
            target=run_server, args=(self.shared_dir, self.port)
        )
        proc.daemon = True  # ensure it won't block app exit
        proc.start()
        self.server_process = proc

    def action_stop_server(self) -> None:
        """Stop the HTTP server process."""
        if self.server_process and self.server_process.is_alive():
            self.server_process.terminate()
            self.server_process.join()
            self.server_process = None

    def action_change_dir(self) -> None:
        """Open the directory change dialog."""
        def on_dialog_dismiss(path: str):
            self.shared_dir = path
        
        self.push_screen(DirectoryDialog(), on_dialog_dismiss)

    def action_change_port(self) -> None:
        """Open the port change dialog."""
        def on_dialog_dismiss(port: int):
            self.port = port

        self.push_screen(PortDialog(), on_dialog_dismiss)

    def action_quit(self) -> None:
        """Quit the application."""
        self.action_stop_server()
        self.exit()
        
    async def action_open_url(self, url: str) -> None:
        """Placeholder for potentially opening URL. Textual handles http links."""
        pass


if __name__ == "__main__":
    # Ensure multiprocessing works correctly when bundled
    multiprocessing.freeze_support()
    app = PyShareApp()
    app.run()
