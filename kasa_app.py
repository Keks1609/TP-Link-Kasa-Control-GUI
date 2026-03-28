import tkinter as tk
import customtkinter as ctk
import asyncio
from kasa import Discover
import threading

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class KasaApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("TP-Link Kasa Control")
        self.geometry("300x450")
        self.device = None
        self.ip_address = None

        # UI Elemente
        self.label_title = ctk.CTkLabel(self, text="Kasa Device Control", font=("Arial", 20, "bold"))
        self.label_title.pack(pady=20)

        self.btn_discover = ctk.CTkButton(self, text="Netzwerk Scannen", command=self.start_discovery)
        self.btn_discover.pack(pady=5)

        self.device_list = ctk.CTkComboBox(self, values=["Keine Geräte gefunden"], command=self.select_device)
        self.device_list.pack(pady=10, padx=20, fill="x")

        # Info Bereich (Standardmäßig versteckt)
        self.info_frame = ctk.CTkFrame(self)
        
        self.name_label = ctk.CTkLabel(self.info_frame, text="Name: -", font=("Arial", 14))
        self.name_label.pack(pady=5)

        self.status_indicator = ctk.CTkLabel(self.info_frame, text="STATUS", text_color="white", corner_radius=8, fg_color="gray", width=120)
        self.status_indicator.pack(pady=10)

        self.btn_toggle = ctk.CTkButton(self.info_frame, text="Umschalten", command=self.toggle_power)
        self.btn_toggle.pack(pady=20)

        self.btn_exit = ctk.CTkButton(self, text="Beenden", fg_color="#444", command=self.quit)
        self.btn_exit.pack(side="bottom", pady=20)

        self.found_devices = {}

    def run_async(self, coro):
        """Hilfsfunktion, um asynchrone Funktionen in einem Thread auszuführen."""
        def wrapper():
            asyncio.run(coro)
        threading.Thread(target=wrapper, daemon=True).start()

    def start_discovery(self):
        self.btn_discover.configure(state="disabled", text="Suche...")
        self.run_async(self.do_discovery())

    async def do_discovery(self):
        found = await Discover.discover()
        self.found_devices = {f"{d.alias} ({ip})": ip for ip, d in found.items()}
        
        if self.found_devices:
            self.device_list.configure(values=list(self.found_devices.keys()))
        self.btn_discover.configure(state="normal", text="Netzwerk Scannen")

    def select_device(self, choice):
        self.ip_address = self.found_devices.get(choice) or self.ip_entry.get()
        if self.ip_address:
            self.run_async(self.update_device_info())

    async def update_device_info(self):
        try:
            # Nutze die neue empfohlene Methode discover_single
            self.device = await Discover.discover_single(self.ip_address)
            await self.device.update()
            
            # UI Update im Hauptthread
            self.after(0, self.show_info_frame)
            self.after(0, self.refresh_ui_elements)
        except Exception as e:
            print(f"Verbindungsfehler: {e}")

    def show_info_frame(self):
        self.info_frame.pack(pady=20, padx=20, fill="both")
        self.name_label.configure(text=f"Gerät: {self.device.alias}")

    def refresh_ui_elements(self):
        if not self.device: return
        
        is_on = self.device.is_on
        color = "#2fa572" if is_on else "#c0392b"
        text = "EINGESCHALTET" if is_on else "AUSGESCHALTET"
        btn_text = "Ausschalten" if is_on else "Einschalten"

        self.status_indicator.configure(text=text, fg_color=color)
        self.btn_toggle.configure(text=btn_text)
               
        # Alle 3 Sekunden aktualisieren
        self.after(3000, lambda: self.run_async(self.periodic_update()))

    async def periodic_update(self):
        if self.device:
            await self.device.update()
            self.after(0, self.refresh_ui_elements)

    def toggle_power(self):
        if self.device:
            self.run_async(self.do_toggle())

    async def do_toggle(self):
        if self.device.is_on:
            await self.device.turn_off()
        else:
            await self.device.turn_on()
        await self.device.update()
        self.after(0, self.refresh_ui_elements)

if __name__ == "__main__":
    app = KasaApp()
    app.mainloop()