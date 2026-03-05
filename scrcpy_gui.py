"""
Scrcpy GUI Controls — Sidebar panel for keymapper control.
Dark premium theme. Type-specific UI per mapping.
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

# ── Colors ──
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

TYPE_COLORS = {
    "KEY": ACCENT, "MOUSE": PURPLE, "AIM": "#f85149",
    "DPAD": "#58a6ff", "SCROLL": "#d29922", "MACRO": "#bc8cff",
}

# Keys that SDL uses — for display
KEY_DISPLAY = {
    "space": "SPACE", "lshift": "L-SHIFT", "rshift": "R-SHIFT",
    "lctrl": "L-CTRL", "rctrl": "R-CTRL", "lalt": "L-ALT", "ralt": "R-ALT",
    "tab": "TAB", "return": "ENTER", "escape": "ESC", "backspace": "BKSP",
    "left": "←", "right": "→", "up": "↑", "down": "↓",
}


class ScrcpySidebar(tk.Tk):
    def __init__(self):
        super().__init__()
        
        if "--no-scrcpy" not in sys.argv:
            try:
                subprocess.Popen(["scrcpy.exe", "-m", "1080", "--max-fps", "144", "--video-buffer", "0", "-K"], 
                                 creationflags=subprocess.CREATE_NO_WINDOW)
            except Exception as e:
                print("Could not launch scrcpy:", e)
            
        self.title("Scrcpy Controls")
        self.geometry("340x680")
        self.configure(bg=BG)
        self.attributes('-topmost', True)
        self.resizable(False, True)
        
        # Dark theme
        s = ttk.Style(self)
        s.theme_use('clam')
        s.configure("TNotebook", background=BG, borderwidth=0)
        s.configure("TNotebook.Tab", background=BG3, foreground=TEXT2, padding=[10, 5],
                   font=("Segoe UI", 9, "bold"))
        s.map("TNotebook.Tab", background=[("selected", BG2)], foreground=[("selected", ACCENT)])
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
        self.capturing_key_for = None  # Index of mapping being key-captured
        
        # ── Header ──
        hdr = tk.Frame(self, bg=BG)
        hdr.pack(fill=tk.X, padx=12, pady=(10, 5))
        tk.Label(hdr, text="CONTROLES", bg=BG, fg=TEXT, font=("Segoe UI", 14, "bold")).pack(side=tk.LEFT)

        # ── Quick Actions ──
        actions = tk.Frame(self, bg=BG)
        actions.pack(fill=tk.X, padx=12, pady=5)
        
        r1 = tk.Frame(actions, bg=BG)
        r1.pack(fill=tk.X, pady=2)
        self._make_btn(r1, "✏️ Editar  F12", self.toggle_edit, ACCENT).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0,3))
        self._make_btn(r1, "👁 Overlay  F11", self.toggle_overlay, BG3).pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(3,0))
        
        r2 = tk.Frame(actions, bg=BG)
        r2.pack(fill=tk.X, pady=2)
        self._make_btn(r2, "🎯 FPS  F10", self.toggle_fps, "#c9372c").pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0,3))
        
        opac_f = tk.Frame(r2, bg=BG)
        opac_f.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(3,0))
        self._make_btn(opac_f, "−", self.opac_down, BG3, w=3).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0,2))
        tk.Label(opac_f, text="Opac", bg=BG, fg=TEXT2, font=("Segoe UI", 7)).pack(side=tk.LEFT, padx=2)
        self._make_btn(opac_f, "+", self.opac_up, BG3, w=3).pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(2,0))

        tk.Frame(self, bg=BORDER, height=1).pack(fill=tk.X, padx=12, pady=8)
        
        # ── Mapping header + Add buttons ──
        mh = tk.Frame(self, bg=BG)
        mh.pack(fill=tk.X, padx=12)
        tk.Label(mh, text="MAPEAMENTOS", bg=BG, fg=TEXT2, font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT)

        # Add type menu
        add_f = tk.Frame(mh, bg=BG)
        add_f.pack(side=tk.RIGHT)
        self.add_type = tk.StringVar(value="KEY")
        add_cb = ttk.Combobox(add_f, textvariable=self.add_type, values=["KEY", "MOUSE", "AIM", "DPAD", "SCROLL", "MACRO"],
                             width=6, state="readonly", style="Dark.TCombobox", font=("Segoe UI", 8))
        add_cb.pack(side=tk.LEFT, padx=3)
        add_btn = tk.Label(add_f, text=" + ", bg=GREEN, fg=BG, font=("Segoe UI", 9, "bold"),
                          padx=6, pady=2, cursor="hand2")
        add_btn.pack(side=tk.LEFT)
        add_btn.bind("<Button-1>", lambda e: self.add_mapping())

        # ── Scrollable list ──
        list_frame = tk.Frame(self, bg=BG)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=(5, 0))
        
        self.canvas = tk.Canvas(list_frame, bg=BG, highlightthickness=0, bd=0)
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = tk.Frame(self.canvas, bg=BG)
        
        self.scrollable_frame.bind("<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw", width=300)
        self.canvas.configure(yscrollcommand=scrollbar.set)
        
        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.canvas.bind_all("<MouseWheel>", lambda e: self.canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

        # ── Bottom ──
        bot = tk.Frame(self, bg=BG)
        bot.pack(fill=tk.X, padx=12, pady=(5, 10))
        close_btn = tk.Label(bot, text="Fechar", bg=RED, fg=BG, font=("Segoe UI", 10, "bold"),
                           pady=6, cursor="hand2")
        close_btn.pack(fill=tk.X)
        close_btn.bind("<Button-1>", lambda e: self.quit_app())

        # Key capture label (hidden by default)
        self.capture_label = tk.Label(self, text="⌨️ PRESSIONE UMA TECLA...", bg=YELLOW, fg=BG,
                                     font=("Segoe UI", 11, "bold"), pady=8)
        
        self.mappings = []
        self.update_list()
        
        # Global key capture
        self.bind_all("<Key>", self._on_key_press)
        
        self.dock_thread = threading.Thread(target=self.dock_loop, daemon=True)
        self.dock_thread.start()
        self.protocol("WM_DELETE_WINDOW", self.quit_app)
    
    def _make_btn(self, parent, text, cmd, bg_c, w=None):
        btn = tk.Label(parent, text=text, bg=bg_c, fg=TEXT if bg_c == BG3 else "#0d1117",
                      font=("Segoe UI", 9, "bold"), padx=8, pady=5, cursor="hand2")
        if w: btn.config(width=w)
        btn.bind("<Button-1>", lambda e: cmd())
        return btn

    def send_cmd(self, cmd_str):
        try:
            with open("keymap.cmd", "w") as f:
                f.write(cmd_str + "\n")
                f.flush()
        except: pass

    def toggle_fps(self):   self.send_cmd("TOGGLE_FPS")
    def toggle_edit(self):
        self.send_cmd("TOGGLE_EDIT")
        self.after(500, self.update_list)
    def toggle_overlay(self): self.send_cmd("TOGGLE_OVERLAY")
    def opac_down(self):    self.send_cmd("OPAC_DOWN")
    def opac_up(self):      self.send_cmd("OPAC_UP")

    # ══════════════════════════════════════════
    # KEY CAPTURE
    # ══════════════════════════════════════════
    def start_key_capture(self, idx):
        """Start listening for the next keypress to assign to mapping[idx]."""
        self.capturing_key_for = idx
        self.capture_label.pack(fill=tk.X, padx=12, pady=5, before=self.canvas.master)
        self.focus_set()
    
    def _on_key_press(self, event):
        """Handle global key press for capture."""
        if self.capturing_key_for is None:
            return
        idx = self.capturing_key_for
        self.capturing_key_for = None
        self.capture_label.pack_forget()
        
        if 0 <= idx < len(self.mappings):
            # Convert tkinter keysym to SDL key name
            key = event.keysym.lower()
            # Map common tkinter names to scrcpy/SDL names
            tk_to_sdl = {
                "shift_l": "lshift", "shift_r": "rshift",
                "control_l": "lctrl", "control_r": "rctrl",
                "alt_l": "lalt", "alt_r": "ralt",
                "return": "return", "escape": "escape",
                "backspace": "backspace", "tab": "tab",
                "delete": "delete", "insert": "insert",
                "home": "home", "end": "end",
                "prior": "pageup", "next": "pagedown",
                "left": "left", "right": "right", "up": "up", "down": "down",
                "caps_lock": "capslock",
            }
            key = tk_to_sdl.get(key, key)
            self.mappings[idx]["key"] = key
            self.save_and_reload()
            self.render_list()

    # ══════════════════════════════════════════
    # FILE I/O — reads positions from file to preserve C-side edits
    # ══════════════════════════════════════════
    def _read_file(self):
        """Read keymap.cfg and return list of raw mapping dicts."""
        result = []
        if not os.path.exists(KEYMAP_FILE):
            return result
        with open(KEYMAP_FILE, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split()
                if len(parts) < 4:
                    continue
                try:
                    m = {
                        "type": parts[0],
                        "key": parts[1],
                        "x": float(parts[2]),
                        "y": float(parts[3]),
                        "radius": 0.08,
                        "macro_steps": ""
                    }
                    if m["type"] == "DPAD" and len(parts) >= 5:
                        m["radius"] = float(parts[4])
                    elif m["type"] == "MACRO" and len(parts) >= 5:
                        m["macro_steps"] = " ".join(parts[4:])
                    result.append(m)
                except:
                    pass
        return result

    def save_and_reload(self):
        """Save mappings to keymap.cfg."""
        lines = []
        for m in self.mappings:
            t = m["type"]
            k = m["key"]
            x = m["x"]
            y = m["y"]
            if t == "DPAD":
                lines.append(f"{t} {k} {x:.3f} {y:.3f} {m.get('radius', 0.08):.3f}\n")
            elif t == "MACRO":
                steps = m.get("macro_steps", "")
                lines.append(f"{t} {k} {x:.3f} {y:.3f} {steps}\n")
            else:
                lines.append(f"{t} {k} {x:.3f} {y:.3f}\n")
        with open(KEYMAP_FILE, "w") as f:
            f.write("# Scrcpy Keymapper Config\n")
            f.writelines(lines)

    def update_list(self):
        """Re-read from file (preserves C-side position changes)."""
        self.mappings = self._read_file()
        self.render_list()

    def add_mapping(self):
        t = self.add_type.get()
        m = {"type": t, "key": "unknown", "x": 0.5, "y": 0.5, "radius": 0.08, "macro_steps": ""}
        if t == "MOUSE":
            m["key"] = "left"
        elif t == "AIM":
            m["key"] = "aim"
        elif t == "DPAD":
            m["key"] = "wasd"
        elif t == "SCROLL":
            m["key"] = "scroll"
        elif t == "MACRO":
            m["key"] = "f1"
        self.mappings.append(m)
        self.save_and_reload()
        self.render_list()

    def remove_item(self, idx):
        if 0 <= idx < len(self.mappings):
            self.mappings.pop(idx)
            self.save_and_reload()
            self.render_list()

    # ══════════════════════════════════════════
    # RENDER — type-specific UI per card
    # ══════════════════════════════════════════
    def render_list(self):
        for w in self.scrollable_frame.winfo_children():
            w.destroy()
            
        for i, m in enumerate(self.mappings):
            t = m["type"]
            color = TYPE_COLORS.get(t, ACCENT)
            
            card = tk.Frame(self.scrollable_frame, bg=BG2)
            card.pack(fill=tk.X, pady=3)
            
            # Color bar
            tk.Frame(card, bg=color, width=3).pack(side=tk.LEFT, fill=tk.Y)
            
            inner = tk.Frame(card, bg=BG2)
            inner.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=8, pady=6)
            
            # ── Row 1: Type label + Delete ──
            top = tk.Frame(inner, bg=BG2)
            top.pack(fill=tk.X)
            
            tk.Label(top, text=t, bg=color, fg=BG, font=("Segoe UI", 8, "bold"),
                    padx=6, pady=1).pack(side=tk.LEFT)
            
            # Position
            pos = f"  ({m['x']:.2f}, {m['y']:.2f})"
            tk.Label(top, text=pos, bg=BG2, fg=TEXT2, font=("Segoe UI", 7)).pack(side=tk.LEFT, padx=4)
            
            del_btn = tk.Label(top, text=" ✕ ", bg=RED, fg=BG, font=("Segoe UI", 8, "bold"),
                              padx=3, pady=0, cursor="hand2")
            del_btn.pack(side=tk.RIGHT)
            del_btn.bind("<Button-1>", lambda e, idx=i: self.remove_item(idx))
            
            # ── Row 2: Type-specific controls ──
            ctrl = tk.Frame(inner, bg=BG2)
            ctrl.pack(fill=tk.X, pady=(4, 0))
            
            if t == "KEY":
                self._render_key_control(ctrl, i, m)
            elif t == "MOUSE":
                self._render_mouse_control(ctrl, i, m)
            elif t == "AIM":
                self._render_aim_control(ctrl, m)
            elif t == "DPAD":
                self._render_dpad_control(ctrl, m)
            elif t == "SCROLL":
                self._render_scroll_control(ctrl, i, m)
            elif t == "MACRO":
                self._render_macro_control(ctrl, i, m)
    
    def _render_key_control(self, parent, idx, m):
        """KEY: Show current key + capture button."""
        display = KEY_DISPLAY.get(m["key"], m["key"].upper())
        
        tk.Label(parent, text="Tecla:", bg=BG2, fg=TEXT2, font=("Segoe UI", 8)).pack(side=tk.LEFT)
        
        key_label = tk.Label(parent, text=f" {display} ", bg=BG3, fg=ACCENT,
                           font=("Segoe UI", 10, "bold"), padx=6, pady=1)
        key_label.pack(side=tk.LEFT, padx=4)
        
        cap_btn = tk.Label(parent, text="⌨️ Capturar", bg=ACCENT, fg=BG,
                          font=("Segoe UI", 8, "bold"), padx=6, pady=2, cursor="hand2")
        cap_btn.pack(side=tk.RIGHT)
        cap_btn.bind("<Button-1>", lambda e, i=idx: self.start_key_capture(i))
    
    def _render_mouse_control(self, parent, idx, m):
        """MOUSE: Left/Right/Middle selector."""
        tk.Label(parent, text="Botão:", bg=BG2, fg=TEXT2, font=("Segoe UI", 8)).pack(side=tk.LEFT)
        
        for btn_name, label in [("left", "Esq"), ("right", "Dir"), ("middle", "Meio")]:
            is_sel = m["key"] == btn_name
            bg_c = PURPLE if is_sel else BG3
            fg_c = BG if is_sel else TEXT2
            b = tk.Label(parent, text=f" {label} ", bg=bg_c, fg=fg_c,
                        font=("Segoe UI", 8, "bold"), padx=4, pady=2, cursor="hand2")
            b.pack(side=tk.LEFT, padx=2)
            b.bind("<Button-1>", lambda e, bn=btn_name, i=idx: self._set_mouse_btn(i, bn))
    
    def _set_mouse_btn(self, idx, btn_name):
        self.mappings[idx]["key"] = btn_name
        self.save_and_reload()
        self.render_list()
    
    def _render_aim_control(self, parent, m):
        """AIM: Just shows info — position is set in edit mode."""
        tk.Label(parent, text="🎯 Âncora da mira — posicione no modo edição",
                bg=BG2, fg=TEXT2, font=("Segoe UI", 8)).pack(side=tk.LEFT)
    
    def _render_dpad_control(self, parent, m):
        """DPAD: Shows WASD info + radius slider."""
        left = tk.Frame(parent, bg=BG2)
        left.pack(side=tk.LEFT)
        tk.Label(left, text="🕹️ Joystick WASD", bg=BG2, fg=TEXT2, font=("Segoe UI", 8)).pack(anchor="w")
        
        # Radius control
        rad_f = tk.Frame(parent, bg=BG2)
        rad_f.pack(side=tk.RIGHT)
        tk.Label(rad_f, text="R:", bg=BG2, fg=TEXT2, font=("Segoe UI", 7)).pack(side=tk.LEFT)
        
        rv = tk.StringVar(value=f"{m.get('radius', 0.08):.2f}")
        re = tk.Entry(rad_f, textvariable=rv, width=5, bg=BG3, fg=TEXT, insertbackground=TEXT,
                     font=("Segoe UI", 8), relief="flat", bd=3)
        re.pack(side=tk.LEFT, padx=2)
        
        def _update_radius(*a):
            try:
                m["radius"] = float(rv.get())
                self.save_and_reload()
            except: pass
        rv.trace_add("write", _update_radius)
    
    def _render_scroll_control(self, parent, idx, m):
        """SCROLL: Direction selector."""
        tk.Label(parent, text="🔄 Roda → Swipe", bg=BG2, fg=TEXT2, font=("Segoe UI", 8)).pack(side=tk.LEFT)
    
    def _render_macro_control(self, parent, idx, m):
        """MACRO: Trigger key + step builder."""
        # Trigger key
        tk.Label(parent, text="Tecla:", bg=BG2, fg=TEXT2, font=("Segoe UI", 8)).pack(side=tk.LEFT)
        
        display = KEY_DISPLAY.get(m["key"], m["key"].upper())
        key_label = tk.Label(parent, text=f" {display} ", bg=BG3, fg=PURPLE,
                           font=("Segoe UI", 9, "bold"), padx=4, pady=1)
        key_label.pack(side=tk.LEFT, padx=3)
        
        cap_btn = tk.Label(parent, text="⌨️", bg=ACCENT, fg=BG,
                          font=("Segoe UI", 8), padx=4, pady=1, cursor="hand2")
        cap_btn.pack(side=tk.LEFT, padx=2)
        cap_btn.bind("<Button-1>", lambda e, i=idx: self.start_key_capture(i))
        
        # Step info
        steps = m.get("macro_steps", "")
        n = len(steps.split(";")) if steps.strip() else 0
        
        step_btn = tk.Label(parent, text=f"📝 {n} passos", bg=BG3, fg=YELLOW, 
                           font=("Segoe UI", 8, "bold"), padx=6, pady=1, cursor="hand2")
        step_btn.pack(side=tk.RIGHT)
        step_btn.bind("<Button-1>", lambda e, i=idx: self._edit_macro(i))

    def _edit_macro(self, idx):
        """Open macro step editor window."""
        m = self.mappings[idx]
        
        win = tk.Toplevel(self)
        win.title("Editor de Macro")
        win.geometry("400x450")
        win.configure(bg=BG)
        win.attributes('-topmost', True)
        win.resizable(False, True)
        
        tk.Label(win, text="EDITOR DE MACRO", bg=BG, fg=TEXT, font=("Segoe UI", 12, "bold")).pack(pady=(10, 5))
        tk.Label(win, text="Cada passo: toque em (X, Y) com delay em ms", bg=BG, fg=TEXT2,
                font=("Segoe UI", 8)).pack()
        
        # Parse existing steps
        steps = []
        raw = m.get("macro_steps", "").strip()
        if raw:
            for s in raw.split(";"):
                parts = s.strip().split(",")
                if len(parts) >= 3:
                    try:
                        steps.append({"x": float(parts[0]), "y": float(parts[1]), "delay": int(parts[2])})
                    except: pass
        
        # Step list
        list_f = tk.Frame(win, bg=BG)
        list_f.pack(fill=tk.BOTH, expand=True, padx=15, pady=5)
        
        step_widgets = []
        
        def render_steps():
            for w in list_f.winfo_children(): w.destroy()
            step_widgets.clear()
            
            # Header
            hdr = tk.Frame(list_f, bg=BG)
            hdr.pack(fill=tk.X, pady=(0, 4))
            tk.Label(hdr, text="#", bg=BG, fg=TEXT2, font=("Segoe UI", 8, "bold"), width=3).pack(side=tk.LEFT)
            tk.Label(hdr, text="X", bg=BG, fg=TEXT2, font=("Segoe UI", 8, "bold"), width=8).pack(side=tk.LEFT)
            tk.Label(hdr, text="Y", bg=BG, fg=TEXT2, font=("Segoe UI", 8, "bold"), width=8).pack(side=tk.LEFT)
            tk.Label(hdr, text="Delay(ms)", bg=BG, fg=TEXT2, font=("Segoe UI", 8, "bold"), width=8).pack(side=tk.LEFT)
            
            for si, step in enumerate(steps):
                row = tk.Frame(list_f, bg=BG2)
                row.pack(fill=tk.X, pady=1)
                
                tk.Label(row, text=f"{si+1}", bg=BG2, fg=TEXT2, font=("Segoe UI", 8), width=3).pack(side=tk.LEFT)
                
                xv = tk.StringVar(value=f"{step['x']:.3f}")
                yv = tk.StringVar(value=f"{step['y']:.3f}")
                dv = tk.StringVar(value=str(step['delay']))
                
                tk.Entry(row, textvariable=xv, width=7, bg=BG3, fg=TEXT, font=("Segoe UI", 8),
                        relief="flat", bd=2, insertbackground=TEXT).pack(side=tk.LEFT, padx=2)
                tk.Entry(row, textvariable=yv, width=7, bg=BG3, fg=TEXT, font=("Segoe UI", 8),
                        relief="flat", bd=2, insertbackground=TEXT).pack(side=tk.LEFT, padx=2)
                tk.Entry(row, textvariable=dv, width=6, bg=BG3, fg=TEXT, font=("Segoe UI", 8),
                        relief="flat", bd=2, insertbackground=TEXT).pack(side=tk.LEFT, padx=2)
                
                del_b = tk.Label(row, text="✕", bg=RED, fg=BG, font=("Segoe UI", 7, "bold"),
                               padx=3, cursor="hand2")
                del_b.pack(side=tk.RIGHT, padx=3)
                del_b.bind("<Button-1>", lambda e, s=si: remove_step(s))
                
                step_widgets.append({"x": xv, "y": yv, "delay": dv})
        
        def add_step():
            steps.append({"x": 0.5, "y": 0.5, "delay": 100})
            render_steps()
        
        def remove_step(si):
            if 0 <= si < len(steps):
                steps.pop(si)
                render_steps()
        
        def save_macro():
            # Read from widgets
            parts = []
            for sw in step_widgets:
                try:
                    x = float(sw["x"].get())
                    y = float(sw["y"].get())
                    d = int(sw["delay"].get())
                    parts.append(f"{x:.3f},{y:.3f},{d}")
                except: pass
            m["macro_steps"] = ";".join(parts)
            self.save_and_reload()
            win.destroy()
            self.render_list()
        
        render_steps()
        
        # Bottom actions
        bot = tk.Frame(win, bg=BG)
        bot.pack(fill=tk.X, padx=15, pady=10)
        
        add_b = tk.Label(bot, text="+ Adicionar Passo", bg=GREEN, fg=BG,
                        font=("Segoe UI", 9, "bold"), padx=8, pady=5, cursor="hand2")
        add_b.pack(fill=tk.X, pady=(0, 5))
        add_b.bind("<Button-1>", lambda e: add_step())
        
        save_b = tk.Label(bot, text="💾 Salvar Macro", bg=ACCENT, fg=BG,
                         font=("Segoe UI", 10, "bold"), padx=8, pady=8, cursor="hand2")
        save_b.pack(fill=tk.X)
        save_b.bind("<Button-1>", lambda e: save_macro())

    # ══════════════════════════════════════════
    # DOCK LOOP
    # ══════════════════════════════════════════
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
