import tkinter as tk
from tkinter import messagebox  # WICHTIG: Explizit importieren
import customtkinter as ctk
import asyncio
from kasa import Discover
import threading
import json
import os

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

def get_config_path():
    filename = ".kasa_config.json"
    if os.name == "nt":  # Windows
        # Speichert in C:\Users\DeinName\AppData\Roaming\KasaControl\
        base_path = os.getenv("APPDATA")
        app_folder = os.path.join(base_path, "KasaControl")
    else:  # Linux / macOS
        # Speichert im Home-Verzeichnis als versteckte Datei
        app_folder = os.path.expanduser("~")
    
    # Ordner erstellen, falls er nicht existiert (wichtig für Windows AppData)
    if not os.path.exists(app_folder):
        os.makedirs(app_folder)
        
    return os.path.join(app_folder, filename)

CONFIG_FILE = get_config_path()

class KasaApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("TP-Link Kasa Control")
        self.geometry("300x500")
        self.device = None
        self.ip_address = None
        self.found_devices = {}

        # UI Elemente (wie zuvor)
        self.label_title = ctk.CTkLabel(self, text="Kasa Device Control", font=("Arial", 20, "bold"))
        self.label_title.pack(pady=20)

        self.btn_discover = ctk.CTkButton(self, text="Netzwerk Scannen", command=self.start_discovery)
        self.btn_discover.pack(pady=5)

        self.device_list = ctk.CTkComboBox(self, values=["Bitte scannen..."], command=self.select_device)
        self.device_list.pack(pady=10, padx=20, fill="x")

        self.info_frame = ctk.CTkFrame(self)
        self.name_label = ctk.CTkLabel(self.info_frame, text="Name: -", font=("Arial", 14))
        self.name_label.pack(pady=5)

        self.status_indicator = ctk.CTkLabel(self.info_frame, text="STATUS", text_color="white", corner_radius=8, fg_color="gray", width=120)
        self.status_indicator.pack(pady=10)

        # NEU: Label für den Stromverbrauch
        self.watt_label = ctk.CTkLabel(self.info_frame, text="Verbrauch: 0.0 W", font=("Arial", 16))
        self.watt_label.pack(pady=5)

        self.btn_toggle = ctk.CTkButton(self.info_frame, text="Umschalten", command=self.confirm_toggle)
        self.btn_toggle.pack(pady=10)
        
        self.btn_rename = ctk.CTkButton(self.info_frame, text="Name ändern", fg_color="#555", command=self.rename_device)
        self.btn_rename.pack(pady=5)

        self.btn_exit = ctk.CTkButton(self, text="Beenden", fg_color="#444", command=self.quit)
        self.btn_exit.pack(side="bottom", pady=20)

        # NEU: Beim Start versuchen, das letzte Gerät zu laden
        self.load_last_device()

    def save_device_config(self, alias, ip):
        """Speichert IP und Name in einer JSON Datei."""
        with open(CONFIG_FILE, "w") as f:
            json.dump({"last_alias": alias, "last_ip": ip}, f)

    def load_last_device(self):
        """Lädt das letzte Gerät aus der Datei, falls vorhanden."""
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    data = json.load(f)
                    alias = data.get("last_alias")
                    ip = data.get("last_ip")
                    if alias and ip:
                        # In die Liste eintragen und auswählen
                        self.found_devices[alias] = ip
                        self.device_list.set(alias)
                        self.ip_address = ip
                        # Sofort verbinden
                        self.run_async(self.update_device_info())
            except:
                pass

    def run_async(self, coro):
        def wrapper():
            asyncio.run(coro)
        threading.Thread(target=wrapper, daemon=True).start()

    def start_discovery(self):
        self.btn_discover.configure(state="disabled", text="Suche...")
        self.run_async(self.do_discovery())

    async def do_discovery(self):
            try:
                found = await Discover.discover()
                self.found_devices = {f"{d.alias} ({ip})": ip for ip, d in found.items()}
                
                if self.found_devices:
                    # 1. Die Liste der Auswahlmöglichkeiten aktualisieren
                    vals = list(self.found_devices.keys())
                    self.after(0, lambda: self.device_list.configure(values=vals))
                    # 2. Den angezeigten Text im Feld von "Suche..." auf "Wähle ein Gerät" ändern
                    self.after(0, lambda: self.device_list.set("Gerät auswählen..."))
                else:
                    self.after(0, lambda: self.device_list.configure(values=["Keine Geräte gefunden"]))
                    self.after(0, lambda: self.device_list.set("Nichts gefunden"))
                    
            except Exception as e:
                print(f"Discovery Fehler: {e}")
                self.after(0, lambda: self.device_list.set("Fehler beim Scan"))

            finally:
                        if not self.found_devices:
                            self.after(0, lambda: self.btn_discover.configure(text="Nichts gefunden - Erneut scannen", state="normal"))
                        else:
                            self.after(0, lambda: self.btn_discover.configure(text="Netzwerk scannen", state="normal"))

    def select_device(self, choice):
        self.ip_address = self.found_devices.get(choice)
        if self.ip_address:
            # NEU: Beim Auswählen direkt speichern
            self.save_device_config(choice, self.ip_address)
            self.run_async(self.update_device_info())

    async def update_device_info(self):
        try:
            self.device = await Discover.discover_single(self.ip_address)
            await self.device.update()
            
            self.after(0, self.show_info_frame)
            self.after(0, self.refresh_ui_elements)
            
            # NEU: Wir starten die periodische Schleife nur EINMAL hier
            self.start_periodic_loop()
        except Exception as e:
            print(f"Verbindungsfehler: {e}")

    def start_periodic_loop(self):
        """Startet die dauerhafte Hintergrund-Aktualisierung."""
        self.run_async(self.periodic_update())

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
        self.name_label.configure(text=f"Gerät: {self.device.alias}")

        # NEU: Stromverbrauch abfragen
        if self.device.has_emeter:
            # emeter_realtime.power liefert den aktuellen Wert in Watt
            current_watt = self.device.emeter_realtime.power
            self.watt_label.configure(text=f"Verbrauch: {current_watt:.1f} W")
        else:
            self.watt_label.configure(text="Keine Strommessung möglich")
               
        # Alle 2 Sekunden aktualisieren
        self.after(2000, lambda: self.run_async(self.periodic_update()))

    def confirm_toggle(self):
        if self.device and self.device.is_on:
            # FEHLER BEHOBEN: Nutzt jetzt das korrekt importierte messagebox
            confirm = messagebox.askyesno("Bestätigung", f"Möchtest du '{self.device.alias}' wirklich ausschalten?")
            if not confirm:
                return
        self.toggle_power()

    def rename_device(self):
        dialog = ctk.CTkInputDialog(text="Gib einen neuen Namen ein:", title="Umbenennen")
        new_name = dialog.get_input()
        if new_name:
            self.run_async(self.do_rename(new_name))

    async def do_rename(self, new_name):
        if self.device:
            await self.device.set_alias(new_name)
            await self.device.update()
            self.after(0, self.refresh_ui_elements)

    async def periodic_update(self):
        if self.device:
            try:
                # WICHTIG: Hier holen wir die echten neuen Daten von der Hardware
                await self.device.update() 
                # UI im Hauptthread aktualisieren
                self.after(0, self.refresh_ui_elements_only)
            except Exception as e:
                print(f"Update Fehler: {e}")
            
            # Alle 3 Sekunden neu triggern
            await asyncio.sleep(3) 
            self.run_async(self.periodic_update())

    def refresh_ui_elements_only(self):
            """Aktualisiert nur die Texte, ohne eine neue Schleife zu triggern."""
            if not self.device: return
            
            is_on = self.device.is_on
            color = "#2fa572" if is_on else "#c0392b"
            
            self.status_indicator.configure(
                text="EINGESCHALTET" if is_on else "AUSGESCHALTET", 
                fg_color=color
            )
            self.btn_toggle.configure(text="Ausschalten" if is_on else "Einschalten")
            self.name_label.configure(text=f"Gerät: {self.device.alias}")

            if self.device.has_emeter:
                # Hier steht jetzt der frische Wert nach dem await device.update()
                pwr = self.device.emeter_realtime.power
                self.watt_label.configure(text=f"Verbrauch: {pwr:.1f} W")

    def toggle_power(self):
        if self.device:
            self.run_async(self.do_toggle())

    async def do_toggle(self):
        try:
            if self.device.is_on:
                await self.device.turn_off()
            else:
                await self.device.turn_on()
            await self.device.update()
            self.after(0, self.refresh_ui_elements)
        except Exception as e:
            print(f"Toggle Fehler: {e}")

if __name__ == "__main__":
    app = KasaApp()
    app.mainloop()
