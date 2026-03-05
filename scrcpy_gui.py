"""
Scrcpy GUI Controls — Sidebar panel for keymapper control.
Dark premium theme matching the launcher aesthetic.
"""
import tkinter as tk
from tkinter import ttk, messagebox
import ctypes
from ctypes import wintypes
import os
import sys
import time
import threading
import subprocess

# Windows APIs
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

KEYMAP_FILE = "keymap.cfg"

# ── Colors (matching launcher) ──
BG     = "#0d1117"
BG2    = "#161b22"
BG3    = "#21262d"
BORDER = "#30363d"
TEXT   = "#e6edf3"
TEXT2  = "#8b949e"
ACCENT = "#58a6ff"
GREEN  = "#3fb950"
RED    = "#f85149"
YELLOW = "#d29922"
PURPLE = "#bc8cff"

# Type colors
TYPE_COLORS = {
    "KEY": ACCENT,
    "MOUSE": PURPLE,
    "AIM": "#f85149",
    "DPAD": "#58a6ff",
    "SCROLL": "#d29922",
    "MACRO": "#bc8cff",
}


class ScrcpySidebar(tk.Tk):
    def __init__(self):
        super().__init__()
        
        # Start scrcpy automatically (unless launched from launcher)
        if "--no-scrcpy" not in sys.argv:
            try:
                subprocess.Popen(["scrcpy.exe", "-m", "1080", "--max-fps", "144", "--video-buffer", "0", "-K"], 
                                 creationflags=subprocess.CREATE_NO_WINDOW)
            except Exception as e:
                print("Could not launch scrcpy:", e)
            
        self.title("Scrcpy Controls")
        self.geometry("320x620")
        self.configure(bg=BG)
        self.attributes('-topmost', True)
        
        # Dark theme
        s = ttk.Style(self)
        s.theme_use('clam')
        s.configure("TNotebook", background=BG, borderwidth=0)
        s.configure("TNotebook.Tab", background=BG3, foreground=TEXT2, padding=[10, 5],
                   font=("Segoe UI", 9, "bold"))
        s.map("TNotebook.Tab", background=[("selected", BG2)], foreground=[("selected", ACCENT)])
        
        s.configure("Action.TButton", background=ACCENT, foreground=BG,
                   font=("Segoe UI", 9, "bold"), borderwidth=0, padding=6)
        s.map("Action.TButton", background=[("active", "#388bfd")])
        
        s.configure("Green.TButton", background=GREEN, foreground=BG,
                   font=("Segoe UI", 9, "bold"), borderwidth=0, padding=6)
        s.map("Green.TButton", background=[("active", "#2ea043")])
        
        s.configure("Red.TButton", background=RED, foreground=BG,
                   font=("Segoe UI", 9, "bold"), borderwidth=0, padding=4)
        s.map("Red.TButton", background=[("active", "#da3633")])
        
        s.configure("Ghost.TButton", background=BG3, foreground=TEXT2,
                   font=("Segoe UI", 9), borderwidth=0, padding=5)
        s.map("Ghost.TButton", background=[("active", BORDER)])
        
        s.configure("Dark.TCombobox", fieldbackground=BG3, background=BG3, foreground=TEXT,
                   arrowcolor=TEXT2, borderwidth=1, padding=3)
        s.map("Dark.TCombobox", fieldbackground=[("readonly", BG3)], foreground=[("readonly", TEXT)],
              selectbackground=[("readonly", BG3)], selectforeground=[("readonly", TEXT)])
        
        self.option_add('*TCombobox*Listbox.background', BG3)
        self.option_add('*TCombobox*Listbox.foreground', TEXT)
        self.option_add('*TCombobox*Listbox.selectBackground', ACCENT)
        self.option_add('*TCombobox*Listbox.selectForeground', BG)
        self.option_add('*TCombobox*Listbox.font', ("Segoe UI", 9))

        self.scrcpy_hwnd = None
        self.running = True
        
        # ── Header ──
        hdr = tk.Frame(self, bg=BG)
        hdr.pack(fill=tk.X, padx=12, pady=(10, 5))
        tk.Label(hdr, text="CONTROLES", bg=BG, fg=TEXT, font=("Segoe UI", 14, "bold")).pack(side=tk.LEFT)

        # ── Quick Actions ──
        actions = tk.Frame(self, bg=BG)
        actions.pack(fill=tk.X, padx=12, pady=5)
        
        # Row 1
        r1 = tk.Frame(actions, bg=BG)
        r1.pack(fill=tk.X, pady=2)
        self._action_btn(r1, "✏️ Editar  F12", self.toggle_edit, ACCENT).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0,3))
        self._action_btn(r1, "👁 Overlay  F11", self.toggle_overlay, BG3).pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(3,0))
        
        # Row 2
        r2 = tk.Frame(actions, bg=BG)
        r2.pack(fill=tk.X, pady=2)
        self._action_btn(r2, "🎯 FPS  F10", self.toggle_fps, "#c9372c").pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0,3))
        
        opac_f = tk.Frame(r2, bg=BG)
        opac_f.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(3,0))
        self._action_btn(opac_f, "−", self.opac_down, BG3, width=3).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0,2))
        tk.Label(opac_f, text="Opac", bg=BG, fg=TEXT2, font=("Segoe UI", 7)).pack(side=tk.LEFT, padx=2)
        self._action_btn(opac_f, "+", self.opac_up, BG3, width=3).pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(2,0))

        # ── Separator ──
        tk.Frame(self, bg=BORDER, height=1).pack(fill=tk.X, padx=12, pady=8)
        
        # ── Mapping header ──
        mh = tk.Frame(self, bg=BG)
        mh.pack(fill=tk.X, padx=12)
        tk.Label(mh, text="MAPEAMENTOS", bg=BG, fg=TEXT2, font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT)
        ttk.Button(mh, text="+ Novo", style="Green.TButton", command=self.add_key).pack(side=tk.RIGHT)

        # ── Scrollable list ──
        list_frame = tk.Frame(self, bg=BG)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=(5, 0))
        
        self.canvas = tk.Canvas(list_frame, bg=BG, highlightthickness=0, bd=0)
        self.scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = tk.Frame(self.canvas, bg=BG)
        
        self.scrollable_frame.bind("<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas_window = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw", width=280)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        
        def _wheel(event):
            self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        self.canvas.bind_all("<MouseWheel>", _wheel)

        # ── Bottom ──
        bot = tk.Frame(self, bg=BG)
        bot.pack(fill=tk.X, padx=12, pady=(5, 10))
        ttk.Button(bot, text="Fechar", style="Red.TButton", command=self.quit_app).pack(fill=tk.X)

        self.mappings = [] 
        self.update_list()
        
        self.dock_thread = threading.Thread(target=self.dock_loop, daemon=True)
        self.dock_thread.start()
        
        self.protocol("WM_DELETE_WINDOW", self.quit_app)
    
    def _action_btn(self, parent, text, command, bg_color, width=None):
        """Create a modern dark action button."""
        btn = tk.Label(parent, text=text, bg=bg_color, fg=TEXT if bg_color == BG3 else "#0d1117",
                      font=("Segoe UI", 9, "bold"), padx=8, pady=5, cursor="hand2")
        if width:
            btn.config(width=width)
        btn.bind("<Button-1>", lambda e: command())
        return btn

    def send_cmd(self, cmd_str):
        try:
            with open("keymap.cmd", "w") as f:
                f.write(cmd_str + "\n")
                f.flush()
        except:
            pass

    def toggle_fps(self):
        self.send_cmd("TOGGLE_FPS")

    def toggle_edit(self):
        self.send_cmd("TOGGLE_EDIT")
        self.after(500, self.update_list) 

    def toggle_overlay(self):
        self.send_cmd("TOGGLE_OVERLAY")

    def opac_down(self):
        self.send_cmd("OPAC_DOWN")
        
    def opac_up(self):
        self.send_cmd("OPAC_UP")

    def save_and_reload(self, *args):
        lines = ["# Scrcpy Keymapper Config\n", "# Types: KEY, MOUSE, AIM, DPAD, SCROLL, MACRO\n"]
        for m in self.mappings:
            type_val = m["type_var"].get()
            btn_val = m["btn_var"].get().replace(' ', '')
            if not btn_val:
                btn_val = "unknown"
            x_val = m["x"]
            y_val = m["y"]
            if type_val == "DPAD":
                radius = m.get("radius", 0.08)
                lines.append(f"{type_val} {btn_val} {x_val:.3f} {y_val:.3f} {radius:.3f}\n")
            elif type_val == "MACRO":
                steps = m.get("macro_steps", "")
                lines.append(f"{type_val} {btn_val} {x_val:.3f} {y_val:.3f} {steps}\n")
            else:
                lines.append(f"{type_val} {btn_val} {x_val:.3f} {y_val:.3f}\n")
            
        with open(KEYMAP_FILE, "w") as f:
            f.writelines(lines)

    def add_key(self):
        self.mappings.append({
            "type_var": tk.StringVar(value="KEY"),
            "btn_var": tk.StringVar(value="unknown"),
            "x": 0.500,
            "y": 0.500,
            "radius": 0.08,
            "macro_steps": ""
        })
        self.render_list()
        self.save_and_reload()

    def remove_item(self, idx):
        if 0 <= idx < len(self.mappings):
            self.mappings.pop(idx)
            self.render_list()
            self.save_and_reload()

    def update_list(self):
        self.mappings = []
        if os.path.exists(KEYMAP_FILE):
            with open(KEYMAP_FILE, "r") as f:
                lines = f.readlines()
            for line in lines:
                parts = line.strip().split()
                if len(parts) >= 4 and not line.startswith("#"):
                    m_type = parts[0]
                    m_btn = parts[1]
                    try:
                        m_x = float(parts[2])
                        m_y = float(parts[3])
                        m = {
                            "type_var": tk.StringVar(value=m_type),
                            "btn_var": tk.StringVar(value=m_btn),
                            "x": m_x,
                            "y": m_y,
                            "radius": 0.08,
                            "macro_steps": ""
                        }
                        if m_type == "DPAD" and len(parts) >= 5:
                            m["radius"] = float(parts[4])
                        elif m_type == "MACRO" and len(parts) >= 5:
                            m["macro_steps"] = " ".join(parts[4:])
                        self.mappings.append(m)
                    except:
                        pass
        self.render_list()
        
    def render_list(self):
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
            
        for i, m in enumerate(self.mappings):
            cur_type = m["type_var"].get()
            type_color = TYPE_COLORS.get(cur_type, ACCENT)
            
            # Card with colored left border
            card = tk.Frame(self.scrollable_frame, bg=BG2)
            card.pack(fill=tk.X, pady=3)
            
            # Color indicator bar
            tk.Frame(card, bg=type_color, width=3).pack(side=tk.LEFT, fill=tk.Y)
            
            inner = tk.Frame(card, bg=BG2)
            inner.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=8, pady=6)
            
            # Setup tracers for auto-save
            m["type_var"].trace_add("write", lambda *a: self.save_and_reload())
            m["btn_var"].trace_add("write", lambda *a: self.save_and_reload())
            
            # Top: Type + Key + Delete
            top = tk.Frame(inner, bg=BG2)
            top.pack(fill=tk.X)
            
            type_cb = ttk.Combobox(top, textvariable=m["type_var"], 
                                   values=["KEY", "MOUSE", "AIM", "DPAD", "SCROLL", "MACRO"], 
                                   width=6, state="readonly", style="Dark.TCombobox", font=("Segoe UI", 9))
            type_cb.pack(side=tk.LEFT)
            
            val_entry = tk.Entry(top, textvariable=m["btn_var"], width=8, bg=BG3, fg=TEXT,
                                insertbackground=TEXT, font=("Segoe UI", 9), relief="flat", bd=3)
            val_entry.pack(side=tk.LEFT, padx=6)
            
            del_btn = tk.Label(top, text="✕", bg=RED, fg=BG, font=("Segoe UI", 8, "bold"),
                              padx=5, pady=1, cursor="hand2")
            del_btn.pack(side=tk.RIGHT)
            del_btn.bind("<Button-1>", lambda e, idx=i: self.remove_item(idx))
            
            # Bottom: Position + type info
            info = tk.Frame(inner, bg=BG2)
            info.pack(fill=tk.X, pady=(3, 0))
            
            pos_text = f"X:{m['x']:.2f}  Y:{m['y']:.2f}"
            extra = ""
            if cur_type == "AIM":
                extra = "  Mira"
            elif cur_type == "DPAD":
                extra = f"  R:{m.get('radius', 0.08):.2f}"
            elif cur_type == "SCROLL":
                extra = "  Swipe"
            elif cur_type == "MACRO":
                steps = m.get('macro_steps', '')
                n = len(steps.split(';')) if steps else 0
                extra = f"  {n}steps"
            
            tk.Label(info, text=pos_text, bg=BG2, fg=TEXT2, font=("Segoe UI", 7)).pack(side=tk.LEFT)
            if extra:
                tk.Label(info, text=extra, bg=BG2, fg=type_color, font=("Segoe UI", 7, "bold")).pack(side=tk.LEFT)

    def dock_loop(self):
        while self.running:
            hwnd = user32.FindWindowW(None, "[Xiaomi] POCO 23113RKC6G (Android 16)")
            if not hwnd:
                def enum_cb(h, _):
                    length = user32.GetWindowTextLengthW(h)
                    buf = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(h, buf, length + 1)
                    if "POCO" in buf.value or "scrcpy" in buf.value.lower():
                        self.scrcpy_hwnd = h
                    return True
                
                CMPFUNC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int))
                user32.EnumWindows(CMPFUNC(enum_cb), 0)
            else:
                self.scrcpy_hwnd = hwnd
                        
            time.sleep(1.0)

    def quit_app(self):
        self.running = False
        if "--no-scrcpy" not in sys.argv:
            os.system("taskkill /F /IM scrcpy.exe >nul 2>&1")
        self.destroy()

if __name__ == "__main__":
    if "--no-scrcpy" not in sys.argv:
        os.system("taskkill /F /IM scrcpy.exe >nul 2>&1")
        time.sleep(0.5)
    app = ScrcpySidebar()
    app.mainloop()
