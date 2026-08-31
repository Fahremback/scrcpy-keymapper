"""
Scrcpy Launcher — UI Premium com detecção ADB, pareamento e configuração.
Detecção focada em conexões Wi-Fi / Wireless Debugging.
"""
import tkinter as tk
from tkinter import ttk, messagebox
import subprocess
import os
import sys
import time
import threading
import json
import shutil
import re

def find_adb():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(base_dir, "adb.exe"),
        r"C:\Users\fahre\Desktop\Ferramentas\adb\platform-tools\adb.exe",
        r"C:\Users\fahre\Desktop\Ferramentas\scrcpy-win64-v3.3.4\adb.exe",
        r"C:\Users\fahre\Documents\antigravity\wise-faraday\tools\platform-tools\adb.exe",
        os.path.expanduser(r"~\AppData\Local\Android\Sdk\platform-tools\adb.exe"),
        shutil.which("adb.exe") or "",
        shutil.which("adb") or "",
    ]
    for c in candidates:
        if c and os.path.exists(c):
            return os.path.abspath(c)
    return "adb.exe"

def find_scrcpy():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(base_dir, "scrcpy.exe"),
        os.path.join(base_dir, "scrcpy-master", "build-win64", "app", "scrcpy.exe"),
        os.path.join(base_dir, "build", "app", "scrcpy.exe"),
        r"C:\Users\fahre\Desktop\Ferramentas\scrcpy-win64-v3.3.4\scrcpy.exe",
        shutil.which("scrcpy.exe") or "",
        shutil.which("scrcpy") or "",
    ]
    for c in candidates:
        if c and os.path.exists(c):
            return os.path.abspath(c)
    return "scrcpy.exe"

ADB_PATH = find_adb()
SCRCPY_PATH = find_scrcpy()
GUI_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scrcpy_gui.py")
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "launcher_config.json")

# ── Colors ──
BG        = "#0d1117"
BG2       = "#161b22"
BG3       = "#21262d"
BORDER    = "#30363d"
TEXT      = "#e6edf3"
TEXT2     = "#8b949e"
ACCENT    = "#58a6ff"
GREEN     = "#3fb950"
RED       = "#f85149"
YELLOW    = "#d29922"
PURPLE    = "#bc8cff"

DEFAULT_CONFIG = {
    "max_size": "1080", "max_fps": "144", "video_bit_rate": "8M",
    "video_codec": "h265", "audio": True, "video_buffer": "0",
    "keep_awake": True, "show_touches": False, "fullscreen": False,
    "borderless": False, "always_on_top": False, "turn_screen_off": False,
    "power_off_close": False,
}

def load_config():
    try:
        with open(CONFIG_FILE, "r") as f:
            cfg = DEFAULT_CONFIG.copy()
            cfg.update(json.load(f))
            return cfg
    except:
        return DEFAULT_CONFIG.copy()

def save_config(cfg):
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(cfg, f, indent=2)
    except:
        pass

def run_adb(*args, timeout=10):
    adb_path = find_adb()
    adb_dir = os.path.dirname(adb_path) if os.path.isabs(adb_path) else os.path.dirname(os.path.abspath(__file__))
    env = os.environ.copy()
    if adb_dir:
        env["PATH"] = adb_dir + os.pathsep + env.get("PATH", "")
    try:
        r = subprocess.run(
            [adb_path] + list(args),
            cwd=adb_dir if os.path.exists(adb_dir) else None,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except Exception as e:
        return -1, "", str(e)

def is_wifi_serial(serial):
    """Verifica se o serial do dispositivo corresponde a uma conexão Wi-Fi / Rede."""
    return ":" in serial or "._tcp" in serial or "._adb" in serial

def get_devices():
    """Retorna lista de dispositivos Wi-Fi conectados e eventuais dispositivos USB detectados."""
    code, out, _ = run_adb("devices", "-l")
    wifi_devs = []
    usb_devs = []
    
    if code == 0:
        for line in out.splitlines():
            line = line.strip()
            if not line or line.startswith("List of devices"):
                continue
            parts = line.split()
            if len(parts) >= 2:
                serial = parts[0]
                status = parts[1]
                
                model = ""
                for p in parts[2:]:
                    if p.startswith("model:"):
                        model = p.split(":", 1)[1].replace("_", " ")
                
                if status == "device":
                    if is_wifi_serial(serial):
                        wifi_devs.append((serial, status, model))
                    else:
                        usb_devs.append((serial, status, model))
                        
    return wifi_devs, usb_devs

def get_device_name(serial, fallback_model=""):
    # Tenta obter nome comercial (ex: POCO F6 Pro)
    code, out, _ = run_adb("-s", serial, "shell", "getprop", "ro.product.marketname")
    if code == 0 and out.strip():
        name = out.strip()
        code2, out2, _ = run_adb("-s", serial, "shell", "getprop", "ro.product.model")
        if code2 == 0 and out2.strip() and out2.strip() not in name:
            return f"{name} ({out2.strip()})"
        return name

    code, out, _ = run_adb("-s", serial, "shell", "getprop", "ro.product.model")
    if code == 0 and out.strip():
        return out.strip()

    if fallback_model:
        return fallback_model

    return f"Android ({serial[:18]})"

def get_device_ip(serial):
    """Obtém o endereço IP local do dispositivo Wi-Fi."""
    code, out, _ = run_adb("-s", serial, "shell", "ip -f inet addr show wlan0")
    if code == 0 and out:
        m = re.search(r"inet\s+(\d+\.\d+\.\d+\.\d+)", out)
        if m:
            return m.group(1)
    code, out, _ = run_adb("-s", serial, "shell", "getprop", "dhcp.wlan0.ipaddress")
    if code == 0 and out.strip():
        return out.strip()
    return ""


def apply_dark_theme(root):
    """Apply a fully dark theme to all ttk widgets."""
    s = ttk.Style(root)
    s.theme_use('clam')
    
    # Notebook
    s.configure("TNotebook", background=BG, borderwidth=0)
    s.configure("TNotebook.Tab", background=BG3, foreground=TEXT2, padding=[14, 6],
               font=("Segoe UI", 10, "bold"))
    s.map("TNotebook.Tab", background=[("selected", BG2)], foreground=[("selected", ACCENT)])
    
    # Comboboxes - fully dark
    s.configure("Dark.TCombobox", 
                fieldbackground=BG3, background=BG3, foreground=TEXT,
                arrowcolor=TEXT2, borderwidth=1, padding=4)
    s.map("Dark.TCombobox",
          fieldbackground=[("readonly", BG3), ("focus", BG3)],
          foreground=[("readonly", TEXT)],
          selectbackground=[("readonly", BG3)],
          selectforeground=[("readonly", TEXT)])
    
    # Buttons
    s.configure("Green.TButton", background=GREEN, foreground="#0d1117",
               font=("Segoe UI", 13, "bold"), borderwidth=0, padding=14)
    s.map("Green.TButton", background=[("active", "#2ea043"), ("disabled", BG3)],
          foreground=[("disabled", TEXT2)])
    
    s.configure("Blue.TButton", background=ACCENT, foreground="#0d1117",
               font=("Segoe UI", 10, "bold"), borderwidth=0, padding=7)
    s.map("Blue.TButton", background=[("active", "#388bfd")])
    
    s.configure("Red.TButton", background=RED, foreground="#0d1117",
               font=("Segoe UI", 9, "bold"), borderwidth=0, padding=5)
    s.map("Red.TButton", background=[("active", "#da3633")])
    
    s.configure("Ghost.TButton", background=BG3, foreground=TEXT2,
               font=("Segoe UI", 9), borderwidth=0, padding=5)
    s.map("Ghost.TButton", background=[("active", BORDER)])
    
    # Scrollbar
    s.configure("Dark.Vertical.TScrollbar", background=BG2, troughcolor=BG, 
               arrowcolor=TEXT2, borderwidth=0)
    s.map("Dark.Vertical.TScrollbar", background=[("active", BG3)])
    
    # Checkbutton
    s.configure("Dark.TCheckbutton", background=BG2, foreground=TEXT, 
               font=("Segoe UI", 9), indicatorbackground=BG3, 
               indicatorforeground=GREEN)
    s.map("Dark.TCheckbutton", background=[("active", BG2)])
    
    # Fix combobox dropdown colors (Tk option database)
    root.option_add('*TCombobox*Listbox.background', BG3)
    root.option_add('*TCombobox*Listbox.foreground', TEXT)
    root.option_add('*TCombobox*Listbox.selectBackground', ACCENT)
    root.option_add('*TCombobox*Listbox.selectForeground', BG)
    root.option_add('*TCombobox*Listbox.font', ("Segoe UI", 10))


class LauncherApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Scrcpy Keymapper Launcher")
        self.geometry("460x730")
        self.configure(bg=BG)
        self.resizable(False, False)
        self.cfg = load_config()
        apply_dark_theme(self)
        
        # Center
        self.update_idletasks()
        x = (self.winfo_screenwidth() // 2) - 230
        y = (self.winfo_screenheight() // 2) - 365
        self.geometry(f"+{x}+{y}")
        
        # ── Header ──
        hdr = tk.Frame(self, bg=BG)
        hdr.pack(fill=tk.X, padx=20, pady=(18, 5))
        tk.Label(hdr, text="SCRCPY LAUNCHER", bg=BG, fg=TEXT,
                font=("Segoe UI", 18, "bold")).pack(side=tk.LEFT)
        tk.Label(hdr, text="Wi-Fi 4.1", bg=BG, fg=ACCENT,
                font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT, padx=8, pady=5)
        
        # ── Status card ──
        self.status_card = tk.Frame(self, bg=BG2, highlightbackground=BORDER, highlightthickness=1)
        self.status_card.pack(fill=tk.X, padx=20, pady=8)
        
        row = tk.Frame(self.status_card, bg=BG2)
        row.pack(fill=tk.X, padx=12, pady=10)
        self.dot = tk.Label(row, text="●", bg=BG2, fg=YELLOW, font=("Segoe UI", 14))
        self.dot.pack(side=tk.LEFT)
        info = tk.Frame(row, bg=BG2)
        info.pack(side=tk.LEFT, padx=8)
        self.status_text = tk.Label(info, text="Procurando conexões Wi-Fi...", bg=BG2, fg=TEXT,
                                   font=("Segoe UI", 11, "bold"), anchor="w")
        self.status_text.pack(anchor="w")
        self.device_text = tk.Label(info, text="", bg=BG2, fg=TEXT2, font=("Segoe UI", 8), anchor="w")
        self.device_text.pack(anchor="w")
        
        # ── Notebook ──
        nb = ttk.Notebook(self)
        nb.pack(fill=tk.BOTH, expand=True, padx=20, pady=6)
        
        # Tab: Conexão
        self.conn_tab = tk.Frame(nb, bg=BG)
        nb.add(self.conn_tab, text="   Conexão Wi-Fi   ")
        self.conn_inner = tk.Frame(self.conn_tab, bg=BG)
        self.conn_inner.pack(fill=tk.BOTH, expand=True)
        
        # Tab: Config (with scroll)
        cfg_tab_outer = tk.Frame(nb, bg=BG)
        nb.add(cfg_tab_outer, text="   Configurações   ")
        self._build_config_tab(cfg_tab_outer)
        
        # ── Launch ──
        bot = tk.Frame(self, bg=BG)
        bot.pack(fill=tk.X, padx=20, pady=(6, 12))
        self.launch_btn = ttk.Button(bot, text="  INICIAR  ", style="Green.TButton",
                                     command=self.launch_all, state="disabled")
        self.launch_btn.pack(fill=tk.X, pady=(0, 6))
        ttk.Button(bot, text="Fechar", style="Ghost.TButton", command=self.destroy).pack(fill=tk.X)
        
        self.found_device = None
        self.after(300, self.scan_devices)
    
    # ──────── Config Tab (scrollable) ────────
    def _build_config_tab(self, parent):
        # Scrollable canvas
        canvas = tk.Canvas(parent, bg=BG, highlightthickness=0, bd=0)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview, style="Dark.Vertical.TScrollbar")
        inner = tk.Frame(canvas, bg=BG)
        
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw", width=400)
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Mouse wheel
        def _wheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _wheel)
        
        # Build options
        self._cfg_section(inner, "VÍDEO")
        self._cfg_combo(inner, "Resolução Máxima", "max_size", ["720", "1080", "1440", "1920", "2560"])
        self._cfg_combo(inner, "FPS Máximo", "max_fps", ["30", "60", "90", "120", "144", "240"])
        self._cfg_combo(inner, "Bitrate de Vídeo", "video_bit_rate", ["2M", "4M", "8M", "16M", "32M", "64M"])
        self._cfg_combo(inner, "Codec de Vídeo", "video_codec", ["h265", "h264", "av1"])
        
        self._cfg_section(inner, "LATÊNCIA")
        self._cfg_combo(inner, "Buffer de Vídeo (ms)", "video_buffer", ["0", "10", "25", "50", "100", "200"])
        
        self._cfg_section(inner, "ÁUDIO")
        self._cfg_toggle(inner, "Transmitir Áudio", "audio")
        
        self._cfg_section(inner, "JANELA")
        self._cfg_toggle(inner, "Tela Cheia", "fullscreen")
        self._cfg_toggle(inner, "Sem Bordas", "borderless")
        self._cfg_toggle(inner, "Sempre no Topo", "always_on_top")
        
        self._cfg_section(inner, "DISPOSITIVO")
        self._cfg_toggle(inner, "Desligar Tela do Celular", "turn_screen_off")
        self._cfg_toggle(inner, "Mostrar Toques na Tela", "show_touches")
        
        # Spacer at bottom
        tk.Frame(inner, bg=BG, height=20).pack()
    
    def _cfg_section(self, parent, title):
        f = tk.Frame(parent, bg=BG)
        f.pack(fill=tk.X, padx=8, pady=(12, 2))
        tk.Frame(f, bg=ACCENT, width=3, height=16).pack(side=tk.LEFT, padx=(0, 8))
        tk.Label(f, text=title, bg=BG, fg=ACCENT, font=("Segoe UI", 10, "bold")).pack(side=tk.LEFT)
    
    def _cfg_combo(self, parent, label, key, values):
        row = tk.Frame(parent, bg=BG2, highlightbackground=BORDER, highlightthickness=1)
        row.pack(fill=tk.X, padx=8, pady=2)
        
        tk.Label(row, text=label, bg=BG2, fg=TEXT, font=("Segoe UI", 10), 
                anchor="w").pack(side=tk.LEFT, padx=10, pady=8)
        
        var = tk.StringVar(value=str(self.cfg.get(key, values[0])))
        cb = ttk.Combobox(row, textvariable=var, values=values, width=10, 
                         state="readonly", style="Dark.TCombobox", font=("Segoe UI", 10))
        cb.pack(side=tk.RIGHT, padx=10, pady=6)
        var.trace_add("write", lambda *a: self._save(key, var.get()))
    
    def _cfg_toggle(self, parent, label, key):
        row = tk.Frame(parent, bg=BG2, highlightbackground=BORDER, highlightthickness=1)
        row.pack(fill=tk.X, padx=8, pady=2)
        
        tk.Label(row, text=label, bg=BG2, fg=TEXT, font=("Segoe UI", 10),
                anchor="w").pack(side=tk.LEFT, padx=10, pady=8)
        
        var = tk.BooleanVar(value=self.cfg.get(key, False))
        
        # Custom toggle button
        toggle_frame = tk.Frame(row, bg=BG2)
        toggle_frame.pack(side=tk.RIGHT, padx=10, pady=6)
        
        btn_text = "  ON " if var.get() else " OFF "
        btn_bg = GREEN if var.get() else BG3
        btn_fg = BG if var.get() else TEXT2
        
        toggle_btn = tk.Label(toggle_frame, text=btn_text, bg=btn_bg, fg=btn_fg,
                             font=("Segoe UI", 9, "bold"), padx=8, pady=2, cursor="hand2",
                             relief="flat", bd=0)
        toggle_btn.pack()
        
        def flip(e=None):
            new_val = not var.get()
            var.set(new_val)
            toggle_btn.config(
                text="  ON " if new_val else " OFF ",
                bg=GREEN if new_val else BG3,
                fg=BG if new_val else TEXT2
            )
            self._save(key, new_val)
        toggle_btn.bind("<Button-1>", flip)
    
    def _save(self, key, val):
        self.cfg[key] = val
        save_config(self.cfg)
    
    # ──────── Connection ────────
    def scan_devices(self):
        self.dot.config(fg=YELLOW)
        self.status_text.config(text="Procurando conexões Wi-Fi...")
        self.device_text.config(text="")
        self.launch_btn.config(state="disabled")
        for w in self.conn_inner.winfo_children(): w.destroy()
        
        def _do():
            wifi_devs, usb_devs = get_devices()
            
            # Format named wifi devices
            named_wifi = []
            for serial, status, model in wifi_devs:
                n = get_device_name(serial, fallback_model=model)
                named_wifi.append((serial, n))
            
            named_usb = []
            for serial, status, model in usb_devs:
                n = get_device_name(serial, fallback_model=model)
                named_usb.append((serial, n))
                
            self.after(0, lambda: self._show_devices(named_wifi, named_usb))
        threading.Thread(target=_do, daemon=True).start()
    
    def _show_devices(self, wifi_devices, usb_devices):
        """Show the device list UI (filtering Wi-Fi only for launch)."""
        for w in self.conn_inner.winfo_children(): w.destroy()
        f = self.conn_inner
        
        if wifi_devices:
            self.dot.config(fg=GREEN)
            count = len(wifi_devices)
            self.status_text.config(text=f"{count} celular{'es' if count > 1 else ''} Wi-Fi conectado{'s' if count > 1 else ''}")
            self.device_text.config(text=wifi_devices[0][1])
            self.found_device = wifi_devices[0][0]  # Use first Wi-Fi device
            self.launch_btn.config(state="normal")
            
            # Device list
            for serial, name in wifi_devices:
                card = tk.Frame(f, bg=BG2, highlightbackground=GREEN, highlightthickness=1)
                card.pack(fill=tk.X, padx=10, pady=4)
                
                row = tk.Frame(card, bg=BG2)
                row.pack(fill=tk.X, padx=10, pady=8)
                
                # Green dot + info
                tk.Label(row, text="📶", bg=BG2, fg=GREEN, font=("Segoe UI", 12)).pack(side=tk.LEFT)
                info_f = tk.Frame(row, bg=BG2)
                info_f.pack(side=tk.LEFT, padx=8, fill=tk.X, expand=True)
                tk.Label(info_f, text=name, bg=BG2, fg=TEXT, font=("Segoe UI", 10, "bold"), anchor="w").pack(anchor="w")
                short = serial[:38] + "..." if len(serial) > 38 else serial
                tk.Label(info_f, text=short, bg=BG2, fg=ACCENT, font=("Segoe UI", 8), anchor="w").pack(anchor="w")
                
                # Disconnect button
                del_btn = tk.Label(row, text=" ✕ ", bg=RED, fg=BG, font=("Segoe UI", 9, "bold"),
                                  cursor="hand2", padx=4, pady=1)
                del_btn.pack(side=tk.RIGHT)
                del_btn.bind("<Button-1>", lambda e, s=serial: self.disconnect_device(s))
            
            # Actions inside connected area
            actions = tk.Frame(f, bg=BG)
            actions.pack(fill=tk.X, padx=10, pady=(8, 4))
            
            ttk.Button(actions, text="↻  Re-escanear", style="Ghost.TButton",
                      command=self.scan_devices).pack(side=tk.LEFT, padx=(0, 5))
            ttk.Button(actions, text="+  Parear Outro", style="Blue.TButton",
                      command=self._show_add_device).pack(side=tk.RIGHT)
                      
        else:
            self.dot.config(fg=YELLOW if usb_devices else RED)
            self.status_text.config(text="Nenhum celular Wi-Fi conectado")
            self.device_text.config(text="")
            self.found_device = None
            self.launch_btn.config(state="disabled")
            
            # If USB device is detected, offer 1-click Wi-Fi switch
            if usb_devices:
                usb_card = tk.Frame(f, bg=BG2, highlightbackground=YELLOW, highlightthickness=1)
                usb_card.pack(fill=tk.X, padx=10, pady=8)
                
                tk.Label(usb_card, text="📱 Celular detectado via USB:", bg=BG2, fg=YELLOW,
                         font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=10, pady=(8, 2))
                
                for s, n in usb_devices:
                    r = tk.Frame(usb_card, bg=BG2)
                    r.pack(fill=tk.X, padx=10, pady=(0, 6))
                    tk.Label(r, text=f"{n} ({s})", bg=BG2, fg=TEXT, font=("Segoe UI", 9)).pack(side=tk.LEFT)
                    btn = ttk.Button(r, text="Ativar Wi-Fi 📶", style="Blue.TButton",
                                    command=lambda u_ser=s: self.enable_wifi_from_usb(u_ser))
                    btn.pack(side=tk.RIGHT)
            
            # Empty state info
            empty = tk.Frame(f, bg=BG2, highlightbackground=BORDER, highlightthickness=1)
            empty.pack(fill=tk.X, padx=10, pady=6)
            tk.Label(empty, text="📶", bg=BG2, font=("Segoe UI", 26)).pack(pady=(12, 4))
            tk.Label(empty, text="Conexão Wi-Fi Necessária", bg=BG2, fg=TEXT, font=("Segoe UI", 11, "bold")).pack()
            tk.Label(empty, text="Ative a Depuração sem Fio no celular\nou conecte via IP abaixo", bg=BG2, fg=TEXT2,
                    font=("Segoe UI", 8)).pack(pady=(2, 10))
            
            actions = tk.Frame(f, bg=BG)
            actions.pack(fill=tk.X, padx=10, pady=6)
            ttk.Button(actions, text="↻  Re-escanear", style="Ghost.TButton",
                      command=self.scan_devices).pack(side=tk.LEFT)
            ttk.Button(actions, text="+  Parear / Conectar IP", style="Blue.TButton",
                      command=self._show_add_device).pack(side=tk.RIGHT)
    
    def enable_wifi_from_usb(self, usb_serial):
        """Ativa o modo TCP/IP no celular via USB e conecta via Wi-Fi."""
        self.status_text.config(text="Ativando Wi-Fi no dispositivo...")
        self.dot.config(fg=YELLOW)
        
        def _do():
            ip = get_device_ip(usb_serial)
            run_adb("-s", usb_serial, "tcpip", "5555")
            time.sleep(1)
            if ip:
                run_adb("connect", f"{ip}:5555")
                time.sleep(1)
            self.after(0, self.scan_devices)
        threading.Thread(target=_do, daemon=True).start()
    
    def _show_add_device(self):
        """Show the add/pair device UI."""
        for w in self.conn_inner.winfo_children(): w.destroy()
        f = self.conn_inner
        
        # Back button
        ttk.Button(f, text="← Voltar", style="Ghost.TButton",
                  command=self.scan_devices).pack(anchor="w", padx=10, pady=(8, 5))
        
        # Connect by IP
        card1 = tk.Frame(f, bg=BG2, highlightbackground=BORDER, highlightthickness=1)
        card1.pack(fill=tk.X, padx=10, pady=5)
        
        tk.Label(card1, text="Conectar via IP (Wi-Fi)", bg=BG2, fg=TEXT,
                font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=12, pady=(8, 2))
        tk.Label(card1, text="Para celulares na mesma rede Wi-Fi", bg=BG2, fg=TEXT2,
                font=("Segoe UI", 8)).pack(anchor="w", padx=12)
        
        r1 = tk.Frame(card1, bg=BG2)
        r1.pack(fill=tk.X, padx=12, pady=(5, 8))
        self.ip_entry = tk.Entry(r1, bg=BG3, fg=TEXT, insertbackground=TEXT,
                                font=("Segoe UI", 10), width=22, relief="flat", bd=5)
        self.ip_entry.insert(0, "192.168.1.X:5555")
        self.ip_entry.pack(side=tk.LEFT)
        ttk.Button(r1, text="Conectar", style="Blue.TButton", command=self.connect_ip).pack(side=tk.RIGHT)
        
        # Pair new
        card2 = tk.Frame(f, bg=BG2, highlightbackground=BORDER, highlightthickness=1)
        card2.pack(fill=tk.X, padx=10, pady=5)
        
        tk.Label(card2, text="Parear Depuração sem Fio", bg=BG2, fg=TEXT,
                font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=12, pady=(8, 2))
        tk.Label(card2, text="Celular → Configurações → Opções do Desenvolvedor\n→ Depuração sem Fio → Parear com Código",
                bg=BG2, fg=TEXT2, font=("Segoe UI", 7), justify=tk.LEFT).pack(anchor="w", padx=12)
        
        pg = tk.Frame(card2, bg=BG2)
        pg.pack(fill=tk.X, padx=12, pady=5)
        
        tk.Label(pg, text="IP:Porta", bg=BG2, fg=TEXT2, font=("Segoe UI", 9), width=8, anchor="w").grid(row=0, column=0)
        self.pair_ip = tk.Entry(pg, bg=BG3, fg=TEXT, insertbackground=TEXT,
                               font=("Segoe UI", 9), width=20, relief="flat", bd=4)
        self.pair_ip.grid(row=0, column=1, pady=2, padx=3)
        
        tk.Label(pg, text="Código", bg=BG2, fg=TEXT2, font=("Segoe UI", 9), width=8, anchor="w").grid(row=1, column=0)
        self.pair_code = tk.Entry(pg, bg=BG3, fg=TEXT, insertbackground=TEXT,
                                 font=("Segoe UI", 9), width=20, relief="flat", bd=4)
        self.pair_code.grid(row=1, column=1, pady=2, padx=3)
        
        ttk.Button(card2, text="Parear Dispositivo", style="Blue.TButton",
                  command=self.pair_device).pack(fill=tk.X, padx=12, pady=(3, 8))
    
    def disconnect_device(self, serial):
        """Disconnect a Wi-Fi device via ADB."""
        self.status_text.config(text="Desconectando...")
        self.dot.config(fg=YELLOW)
        def _do():
            run_adb("disconnect", serial)
            time.sleep(0.5)
            self.after(0, self.scan_devices)
        threading.Thread(target=_do, daemon=True).start()
    
    def connect_ip(self):
        ip = self.ip_entry.get().strip()
        if not ip or "X" in ip: return
        self.status_text.config(text=f"Conectando a {ip}...")
        self.dot.config(fg=YELLOW)
        def _do():
            c, out, err = run_adb("connect", ip)
            ok = c == 0 and "connected" in out.lower()
            self.after(0, lambda: self.scan_devices() if ok else self.status_text.config(text=f"Falha: {(out or err)[:40]}"))
        threading.Thread(target=_do, daemon=True).start()
    
    def pair_device(self):
        ip = self.pair_ip.get().strip()
        code = self.pair_code.get().strip()
        if not ip or not code: return
        self.status_text.config(text="Pareando...")
        self.dot.config(fg=YELLOW)
        def _do():
            c, out, err = run_adb("pair", ip, code)
            ok = "success" in (out + err).lower() or "paired" in (out + err).lower()
            if ok:
                base = ip.split(":")[0]
                time.sleep(1)
                run_adb("connect", f"{base}:5555")
                time.sleep(1)
            self.after(0, lambda: self.scan_devices() if ok else self.status_text.config(text="Falha ao parear"))
        threading.Thread(target=_do, daemon=True).start()
    
    # ──────── Launch ────────
    def launch_all(self):
        self.status_text.config(text="Iniciando...")
        self.dot.config(fg=YELLOW)
        self.launch_btn.config(state="disabled")
        self.update()
        
        scrcpy_exe = find_scrcpy()
        cmd = [scrcpy_exe]
        
        # Alvo específico do dispositivo Wi-Fi conectado
        if self.found_device:
            cmd += ["-s", self.found_device]
            
        c = self.cfg
        if c.get("max_size"): cmd += ["-m", str(c["max_size"])]
        if c.get("max_fps"): cmd += ["--max-fps", str(c["max_fps"])]
        if c.get("video_bit_rate"): cmd += ["-b", str(c["video_bit_rate"])]
        
        codec = c.get("video_codec", "h265")
        if codec != "h264":
            cmd += ["--video-codec", codec]
            
        # Removed profile/level options as they can cause black screens on some devices
            
        vb = c.get("video_buffer", "0")
        if vb != "0": cmd += ["--video-buffer", str(vb)]
        
        # Audio buffer 10ms default
        if not c.get("audio", True): 
            cmd += ["--no-audio"]
        else:
            cmd += ["--audio-buffer", "10"]
            
        if c.get("fullscreen"): cmd += ["--fullscreen"]
        if c.get("borderless"): cmd += ["--window-borderless"]
        if c.get("always_on_top"): cmd += ["--always-on-top"]
        if c.get("show_touches"): cmd += ["--show-touches"]
        if c.get("turn_screen_off"):
            cmd += ["--turn-screen-off", "--stay-awake"]
        cmd += ["-K"]
        
        print("Executando:", " ".join(cmd))
        
        try:
            scrcpy_dir = os.path.dirname(scrcpy_exe) if os.path.isabs(scrcpy_exe) else os.path.dirname(os.path.abspath(__file__))
            env = os.environ.copy()
            adb_dir = os.path.dirname(find_adb())
            if adb_dir:
                env["PATH"] = adb_dir + os.pathsep + env.get("PATH", "")
                
            subprocess.Popen(
                cmd,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
                cwd=scrcpy_dir,
                env=env
            )
        except Exception as e:
            messagebox.showerror("Erro", f"Scrcpy falhou:\n{e}")
            self.launch_btn.config(state="normal")
            return
        
        time.sleep(2)
        try:
            subprocess.Popen([sys.executable, GUI_PATH, "--no-scrcpy"],
                           cwd=os.path.dirname(GUI_PATH))
        except:
            pass
        
        self.destroy()


if __name__ == "__main__":
    app = LauncherApp()
    app.mainloop()
