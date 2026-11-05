import tkinter as tk

class BaseTab(tk.Frame):
    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, bg="#f5f6f7", **kwargs)
        self.app = app
        self.setup_ui()

    def setup_ui(self):
        raise NotImplementedError("Subclasses must implement setup_ui")

    def log(self, message):
        self.app.log(message)

    def update_status(self, message):
        self.app.status_var.set(message)
