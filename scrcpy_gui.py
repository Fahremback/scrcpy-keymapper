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
            
        self.title("Scrcpy GUI Controls")
        self.geometry("340x650")
        self.configure(bg="#1E1E2E")
        self.attributes('-topmost', True)
        # Removed overrideredirect so standard Windows resize/close works.

        self.scrcpy_hwnd = None
        self.running = True
        
        # Style
        self.style = ttk.Style(self)
        self.style.theme_use('clam')
        self.style.configure("TButton", background="#89B4FA", foreground="#11111B", font=("Segoe UI", 10, "bold"), borderwidth=0)
        self.style.map("TButton", background=[("active", "#B4BEFE")])
        self.style.configure("Danger.TButton", background="#F38BA8", foreground="#11111B")
        self.style.map("Danger.TButton", background=[("active", "#F9E2AF")])

        self.btn_frame = tk.Frame(self, bg="#1E1E2E")
        self.btn_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Actions
        actions_frame = tk.Frame(self.btn_frame, bg="#1E1E2E")
        actions_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Button(actions_frame, text="✏️ Modo Edição (F12)", command=self.toggle_edit).pack(fill=tk.X, pady=2)
        ttk.Button(actions_frame, text="👁️ Mostrar/Ocultar (F11)", command=self.toggle_overlay).pack(fill=tk.X, pady=2)
        ttk.Button(actions_frame, text="🎯 Modo FPS [Mouse Lock] (F10)", command=self.toggle_fps).pack(fill=tk.X, pady=2)
        
        f = tk.Frame(actions_frame, bg="#1E1E2E")
        f.pack(fill=tk.X, pady=2)
        ttk.Button(f, text="Opacidade -", command=self.opac_down, width=12).pack(side=tk.LEFT, expand=True, padx=(0,2))
        ttk.Button(f, text="Opacidade +", command=self.opac_up, width=12).pack(side=tk.RIGHT, expand=True, padx=(2,0))

        # List Header
        list_header = tk.Frame(self.btn_frame, bg="#1E1E2E")
        list_header.pack(fill=tk.X, pady=(10, 5))
        tk.Label(list_header, text="MAPEAMENTOS:", bg="#1E1E2E", fg="#CDD6F4", font=("Segoe UI", 10, "bold")).pack(side=tk.LEFT)
        ttk.Button(list_header, text="➕ Novo", command=self.add_key, width=8).pack(side=tk.RIGHT, padx=5)

        # Inner Scrollable Frame for List
        self.canvas = tk.Canvas(self.btn_frame, bg="#181825", highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self.btn_frame, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = tk.Frame(self.canvas, bg="#181825")
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw", width=290)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        
        # Mouse Wheel binding
        def _on_mousewheel(event):
            self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        self.canvas.bind_all("<MouseWheel>", _on_mousewheel)

        bottom_frame = tk.Frame(self, bg="#1E1E2E")
        bottom_frame.pack(fill=tk.X, side=tk.BOTTOM, pady=10)
        ttk.Button(bottom_frame, text="❌ Fechar", style="Danger.TButton", command=self.quit_app).pack(fill=tk.X, padx=10)

        self.mappings = [] 
        self.update_list()
        
        self.dock_thread = threading.Thread(target=self.dock_loop, daemon=True)
        self.dock_thread.start()
        
        self.protocol("WM_DELETE_WINDOW", self.quit_app)

    def send_cmd(self, cmd_str):
        # IPC directly to C
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
        # Build lines from UI state automatically
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
            row = tk.Frame(self.scrollable_frame, bg="#313244", highlightbackground="#45475A", highlightthickness=1)
            row.pack(fill=tk.X, pady=4, padx=2)
            
            top_row = tk.Frame(row, bg="#313244")
            top_row.pack(fill=tk.X, padx=5, pady=5)
            
            # Setup tracers for auto-save
            m["type_var"].trace_add("write", lambda *a: self.save_and_reload())
            m["btn_var"].trace_add("write", lambda *a: self.save_and_reload())
            
            type_cb = ttk.Combobox(top_row, textvariable=m["type_var"], 
                                   values=["KEY", "MOUSE", "AIM", "DPAD", "SCROLL", "MACRO"], 
                                   width=7, state="readonly")
            type_cb.pack(side=tk.LEFT)
            
            val_entry = tk.Entry(top_row, textvariable=m["btn_var"], width=8, bg="#1E1E2E", fg="#CDD6F4", insertbackground="#CDD6F4")
            val_entry.pack(side=tk.LEFT, padx=5)
            
            btn = ttk.Button(top_row, text="X", style="Danger.TButton", width=3, command=lambda idx=i: self.remove_item(idx))
            btn.pack(side=tk.RIGHT)
            
            bot_row = tk.Frame(row, bg="#313244")
            bot_row.pack(fill=tk.X, padx=5, pady=(0, 5))
            
            cur_type = m["type_var"].get()
            info_text = f"Pos: X={m['x']:.2f}  Y={m['y']:.2f}"
            if cur_type == "AIM":
                info_text += "  [Mira FPS]"
            elif cur_type == "DPAD":
                info_text += f"  R={m.get('radius', 0.08):.2f} [Joystick]"
            elif cur_type == "SCROLL":
                info_text += "  [Scroll→Swipe]"
            elif cur_type == "MACRO":
                steps = m.get('macro_steps', '')
                n = len(steps.split(';')) if steps else 0
                info_text += f"  [{n} steps]"
            
            tk.Label(bot_row, text=info_text, bg="#313244", fg="#A6ADC8", font=("Segoe UI", 8)).pack(side=tk.LEFT)

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
                        
            time.sleep(1.0) # Reduced check frequency since we don't snap position aggressively anymore

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
