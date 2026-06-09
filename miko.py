import tkinter as tk
import math
import ctypes
import os
import sys
import json
import random
import psutil
from fractions import Fraction
from pynput import keyboard

BASE = os.path.dirname(os.path.abspath(__file__))
SETTINGS_FILE = os.path.join(BASE, 'settings.json')

DEFAULTS = {
    'animation_fps': 5, 'scale': 2.0, 'sleep_timeout': 10,
    'click_through': True, 'speed': 4, 'deadzone': 100,
    'panel_bg': '#0b101e', 'panel_fg': '#c0cce0',
    'wander_timeout': 10, 'character': 'miko',
}

SETTINGS_KEYS = [
    ('animation_fps', 'Anim FPS', 1, 30, 1),
    ('scale', 'Scale', 1, 4, 0.5),
    ('sleep_timeout', 'Sleep (s)', 5, 60, 5),
    ('speed', 'Speed', 1, 10, 1),
    ('deadzone', 'Deadzone', 10, 300, 10),
    ('click_through', 'Click Thru', 0, 1, 1),
    ('wander_timeout', 'Wander (s)', 0, 60, 5),
    ('character', 'Character', 0, 1, 1),
]

SETTINGS_PAGES = [
    ['character', 'animation_fps', 'scale', 'sleep_timeout'],
    ['speed', 'deadzone', 'wander_timeout'],
    ['click_through'],
]

BG_PRESETS = ['#0b101e', '#0d1a1a', '#1a0d0d', '#0d0d1a', '#1a1a0d', '#101010']

CHAR_FOLDERS = {'miko': 'miko ase', 'chungus': 'fox-chungus'}
CHAR_LIST = ['miko', 'chungus']

GIF_MAP = {
    'miko': {
        'left': 'runningcat.gif', 'right': 'cat right.gif',
        'idle': 'idle.gif', 'sleeping': 'sleepingcat.gif',
        'typing': 'typingcat.gif', 'krita': 'kritacat.gif',
        'doing': 'catdoing.gif',
    },
    'chungus': {
        'left': 'foxleft.gif', 'right': 'foxright.gif',
        'idle': 'foxneutral.gif', 'sleeping': 'foxsleeping.gif',
        'typing': 'foxneutral.gif', 'krita': 'foxneutral.gif',
        'doing': None,
    },
}


def resource_path(subfolder, filename):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, 'assets', subfolder, filename)
    return os.path.join(BASE, 'assets', subfolder, filename)


def load_settings():
    try:
        with open(SETTINGS_FILE) as f:
            data = json.load(f)
        for k in DEFAULTS:
            if k not in data:
                data[k] = DEFAULTS[k]
        return data
    except Exception:
        return dict(DEFAULTS)


def save_settings(cfg):
    try:
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(cfg, f, indent=2)
    except Exception:
        pass


class Miko:
    def __init__(self):
        self.cfg = load_settings()

        self.window = tk.Tk()
        self.window.title("miko")
        self.window.overrideredirect(True)
        self.window.attributes('-topmost', True)
        self.trans_color = '#ff00ff'
        self.window.config(bg=self.trans_color)
        self.window.attributes('-transparentcolor', self.trans_color)
        self.set_click_through(self.cfg['click_through'])

        self.animation_fps = self.cfg['animation_fps']
        self.update_fps = 60
        self.update_delay = int(1000 / self.update_fps)
        self.anim_interval = int(1000 / self.animation_fps)
        self.anim_accumulator = 0

        self.is_typing = False
        self.typing_timer = None
        self.timer_buffer = 1000
        self.ctrl_pressed = False
        self.deadzone = self.cfg['deadzone']
        self.sleep_timeout = self.cfg['sleep_timeout'] * 1000
        self.mouse_still_time = 0
        self.last_mouse_x = 0
        self.last_mouse_y = 0
        self.is_idle = False
        self.is_sleeping = False
        self.krita_open = False
        self.check_software_counter = 0
        self.state = "running"
        self.frame_index = 0
        self.typing_frame_index = 0
        self.idle_frame_index = 0
        self.sleeping_frame_index = 0
        self.krita_frame_index = 0
        self.scale = self.cfg['scale']
        self.speed = self.cfg['speed']
        self.wander_timeout = self.cfg.get('wander_timeout', 10) * 1000
        self.wandering = False
        self.wander_target = None
        self.character = self.cfg.get('character', 'miko')

        self.patrol_target = None
        self.fox_mode = "patrol"
        self.rest_counter = 0
        self.rest_duration_ticks = 5 * 60

        self.doing_frames = []
        self.is_doing = False
        self.doing_frame_index = 0
        self.doing_play_count = 0
        self.sleep_after_doing = False

        self._load_character_gifs()

        img = self.running_frames[0] if self.running_frames else None
        if img:
            self.label = tk.Label(self.window, image=img, bg=self.trans_color, bd=0)
        else:
            self.label = tk.Label(self.window, text="??", font=("Arial", 24), bg=self.trans_color, fg='white')
        self.label.pack()

        self.x = 0
        self.y = 0
        self.facing_right = False

        self.showing_settings = False
        self.settings_win = None
        self.settings_labels = {}
        self.bg_index = 0

        self.listener = keyboard.Listener(on_press=self.on_key_press, on_release=self.on_key_release)
        self.listener.start()

        self.window.bind('<Escape>', lambda e: self._close_settings_ui())

        self.update_miko()
        self.window.mainloop()

    def _close_settings_ui(self):
        if self.showing_settings:
            self.close_settings()

    def _load_character_gifs(self):
        folder = CHAR_FOLDERS.get(self.character, 'miko ase')
        gifs = GIF_MAP.get(self.character, GIF_MAP['miko'])

        self.running_frames = self._load_gif(folder, gifs['left'])
        self.running_right_frames = self._load_gif(folder, gifs['right'])
        self.idle_frames = self._load_gif(folder, gifs['idle'])
        self.sleeping_frames = self._load_gif(folder, gifs['sleeping'])
        self.typing_frames = self._load_gif(folder, gifs['typing'])
        self.krita_frames = self._load_gif(folder, gifs['krita'])
        if gifs['doing']:
            self.doing_frames = self._load_gif(folder, gifs['doing'])
        else:
            self.doing_frames = []

    def _load_gif(self, subfolder, filename):
        path = resource_path(subfolder, filename)
        frames = []
        try:
            i = 0
            while True:
                try:
                    frame = tk.PhotoImage(file=path, format=f"gif -index {i}")
                    if self.scale != 1:
                        f = Fraction(str(self.scale)).limit_denominator(100)
                        frame = frame.zoom(f.numerator, f.numerator).subsample(f.denominator, f.denominator)
                    frames.append(frame)
                    i += 1
                except tk.TclError:
                    break
        except Exception as e:
            print(f"cant load {subfolder}/{filename}:", e)
        return frames

    def set_click_through(self, on):
        try:
            hwnd = ctypes.windll.user32.GetParent(self.window.winfo_id())
            ws = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
            if on:
                ctypes.windll.user32.SetWindowLongW(hwnd, -20, ws | 0x20)
            else:
                ctypes.windll.user32.SetWindowLongW(hwnd, -20, ws & ~0x20)
        except Exception:
            pass

    def open_settings(self):
        if self.settings_win:
            return
        self.showing_settings = True
        self.settings_labels = {}
        self.settings_page = 0

        win = tk.Toplevel(self.window)
        win.overrideredirect(True)
        win.attributes('-topmost', True)
        pbg = self.cfg.get('panel_bg', '#1a1e3a')
        pfg = self.cfg.get('panel_fg', '#a0b0dd')
        win.config(bg=pbg)
        self.settings_win = win
        self._pbg = pbg
        self._pfg = pfg

        pw, ph = 420, 300
        tx, ty = self.window.winfo_x(), self.window.winfo_y()
        win.geometry(f"{pw}x{ph}+{max(0, tx - pw - 10)}+{max(0, ty - 20)}")

        self._bg_canvas = tk.Canvas(win, highlightthickness=0, bd=0)
        self._bg_canvas.place(x=0, y=0, relwidth=1, relheight=1)
        self._draw_balatro_bg(pw, ph, pbg)

        top = tk.Frame(win, bg=pbg, bd=0)
        top.pack(fill='x', padx=16, pady=(14, 0))
        tk.Label(top, text="MIKO", fg='#d4a84b', bg=pbg,
                 font=('Segoe UI', 14, 'bold')).pack(side='left')
        close_lbl = tk.Label(top, text="[X]", fg='#dd6688', bg=pbg,
                             font=('Segoe UI', 14, 'bold'), cursor='hand2')
        close_lbl.pack(side='right')
        close_lbl.bind('<Button-1>', lambda e: self.close_settings())

        sep = tk.Frame(win, bg='#2a3050', height=1, bd=0)
        sep.pack(fill='x', padx=16, pady=(6, 0))

        self.settings_body = tk.Frame(win, bg=pbg, bd=0)
        self.settings_body.pack(fill='both', expand=True, padx=16, pady=(8, 0))

        self._render_page()

        sep2 = tk.Frame(win, bg='#2a3050', height=1, bd=0)
        sep2.pack(fill='x', padx=16, pady=(4, 0))
        bottom = tk.Frame(win, bg=pbg, bd=0)
        bottom.pack(fill='x', padx=16, pady=(6, 10))
        fg2 = '#8a9bc0'
        nav_frame = tk.Frame(bottom, bg=pbg, bd=0)
        nav_frame.pack(side='left')
        nav_l = tk.Label(nav_frame, text="[<]", fg='#d4a84b', bg=pbg,
                         font=('Segoe UI', 10, 'bold'), cursor='hand2')
        nav_l.pack(side='left')
        nav_l.bind('<Button-1>', lambda e: self._nav_page(-1))
        self.page_ind = tk.Label(nav_frame, text="", fg=fg2, bg=pbg,
                                 font=('Segoe UI', 10))
        self.page_ind.pack(side='left', padx=6)
        nav_r = tk.Label(nav_frame, text="[>]", fg='#d4a84b', bg=pbg,
                         font=('Segoe UI', 10, 'bold'), cursor='hand2')
        nav_r.pack(side='left')
        nav_r.bind('<Button-1>', lambda e: self._nav_page(1))
        self._update_page_ind()

        extra = tk.Frame(bottom, bg=pbg, bd=0)
        extra.pack(side='right')
        bgl = tk.Label(extra, text="[Panel BG]", fg=fg2, bg=pbg,
                       font=('Segoe UI', 9), cursor='hand2')
        bgl.pack(side='left')
        bgl.bind('<Button-1>', lambda e: self._cycle_bg())
        stl = tk.Label(extra, text="[Stop]", fg='#dd4455', bg=pbg,
                       font=('Segoe UI', 9, 'bold'), cursor='hand2')
        stl.pack(side='left', padx=(10, 0))
        stl.bind('<Button-1>', lambda e: self._stop_miko())

    def _draw_balatro_bg(self, w, h, color):
        c = self._bg_canvas
        c.delete("all")
        c.create_rectangle(0, 0, w, h, fill=color, outline='')
        c.create_rectangle(3, 3, w-4, h-4, fill='', outline='#1e2940', width=1)
        c.create_rectangle(8, 8, w-9, h-9, fill='', outline='#182030', width=1)
        c.create_rectangle(3, 3, w-4, 5, fill='#d4a84b', outline='')

    def _update_page_ind(self):
        t = len(SETTINGS_PAGES)
        self.page_ind.config(text=f"{self.settings_page+1}/{t}")

    def _render_page(self):
        if hasattr(self, 'settings_content') and self.settings_content:
            self.settings_content.destroy()
        self.settings_labels = {}
        self.settings_content = tk.Frame(self.settings_body, bg=self._pbg, bd=0)
        self.settings_content.pack(fill='both', expand=True)
        for key in SETTINGS_PAGES[self.settings_page]:
            item = next((x for x in SETTINGS_KEYS if x[0] == key), None)
            if not item:
                continue
            _, label, lo, hi, step = item
            val = self.cfg.get(key, DEFAULTS[key])
            row_f = tk.Frame(self.settings_content, bg=self._pbg, bd=0)
            row_f.pack(fill='x', pady=4)
            if isinstance(val, bool):
                txt = f"{label}: {'ON' if val else 'OFF'}"
            elif key == 'character':
                txt = f"{label}: {val.capitalize()}"
            else:
                txt = f"{label}: {val}"
            vl = tk.Label(row_f, text=txt, fg=self._pfg, bg=self._pbg,
                          font=('Segoe UI', 11), anchor='w', width=28)
            vl.pack(side='left')
            self.settings_labels[key] = vl
            lm = tk.Label(row_f, text="[-]", fg='#ee9944', bg=self._pbg,
                          font=('Segoe UI', 11, 'bold'), cursor='hand2')
            lm.pack(side='right')
            lm.bind('<Button-1>', lambda e, k=key: self.click_setting(k, -1))
            lp = tk.Label(row_f, text="[+]", fg='#44ee88', bg=self._pbg,
                          font=('Segoe UI', 11, 'bold'), cursor='hand2')
            lp.pack(side='right', padx=(0, 6))
            lp.bind('<Button-1>', lambda e, k=key: self.click_setting(k, 1))

    def _nav_page(self, direction):
        self.settings_page = (self.settings_page + direction) % len(SETTINGS_PAGES)
        self._render_page()
        self._update_page_ind()

    def _stop_miko(self):
        self.close_settings()
        self.window.after(100, self.window.destroy)

    def rebuild_settings(self):
        was_open = self.settings_win is not None
        if was_open:
            self.settings_win.destroy()
            self.settings_win = None
        if was_open:
            self.open_settings()

    def refresh_setting_labels(self):
        pbg = self.cfg.get('panel_bg', '#1a1e3a')
        pfg = self.cfg.get('panel_fg', '#a0b0dd')
        for key, label, lo, hi, step in SETTINGS_KEYS:
            val = self.cfg.get(key, DEFAULTS[key])
            if isinstance(val, bool):
                txt = f"{label}: {'ON' if val else 'OFF'}"
            elif key == 'character':
                txt = f"{label}: {val.capitalize()}"
            else:
                txt = f"{label}: {val}"
            if key in self.settings_labels:
                self.settings_labels[key].config(text=txt, fg=pfg, bg=pbg)

    def click_setting(self, key, direction):
        lo, hi, step_val = 0, 1, 1
        for k, _, l, h, s in SETTINGS_KEYS:
            if k == key:
                lo, hi, step_val = l, h, s
                break
        val = self.cfg.get(key, DEFAULTS[key])

        if key == 'character':
            idx = CHAR_LIST.index(val) if val in CHAR_LIST else 0
            self.cfg[key] = CHAR_LIST[(idx + 1) % len(CHAR_LIST)]
            self.character = self.cfg[key]
            self.window.after(50, self._reload_char)
        elif key == 'click_through':
            self.cfg[key] = not val
            self.set_click_through(self.cfg[key])
        else:
            self.cfg[key] = max(lo, min(hi, val + direction * step_val))
            if key == 'scale':
                self.scale = self.cfg['scale']
                self.window.after(50, self.reload_gifs)
            elif key == 'animation_fps':
                self.animation_fps = self.cfg['animation_fps']
                self.anim_interval = int(1000 / self.animation_fps)
            elif key == 'sleep_timeout':
                self.sleep_timeout = self.cfg['sleep_timeout'] * 1000
            elif key == 'speed':
                self.speed = self.cfg['speed']
            elif key == 'deadzone':
                self.deadzone = self.cfg['deadzone']
            elif key == 'wander_timeout':
                self.wander_timeout = self.cfg['wander_timeout'] * 1000
        self.refresh_setting_labels()
        save_settings(self.cfg)

    def _reload_char(self):
        self._load_character_gifs()
        self.reload_gifs()
        self.wandering = False
        self.wander_target = None
        self.patrol_target = None
        self.fox_mode = "patrol"
        self.rest_counter = 0
        self.is_doing = False
        self.is_sleeping = False
        self.is_idle = False

    def reload_gifs(self):
        old_state = self.state
        self._load_character_gifs()
        if old_state == "running" and self.running_frames:
            self.label.config(image=self.running_frames[0])
        elif old_state == "typing" and self.typing_frames:
            self.label.config(image=self.typing_frames[0])
        elif old_state == "idle" and self.idle_frames:
            self.label.config(image=self.idle_frames[0])
        elif old_state == "sleeping" and self.sleeping_frames:
            self.label.config(image=self.sleeping_frames[0])
        elif old_state == "krita" and self.krita_frames:
            self.label.config(image=self.krita_frames[0])

    def _restore_gif_state(self):
        if self.state == "running" and self.running_frames:
            self.label.config(image=self.running_frames[0])
        elif self.state == "sleeping" and self.sleeping_frames:
            self.label.config(image=self.sleeping_frames[0])
        elif self.state == "idle" and self.idle_frames:
            self.label.config(image=self.idle_frames[0])

    def close_settings(self):
        self.showing_settings = False
        if self.settings_win:
            self.settings_win.destroy()
            self.settings_win = None
        self.settings_labels = {}
        save_settings(self.cfg)

    def _toggle_settings(self):
        if self.showing_settings:
            self.close_settings()
        else:
            self.open_settings()

    def _cycle_bg(self):
        current = self.cfg.get('panel_bg', BG_PRESETS[0])
        try:
            idx = BG_PRESETS.index(current)
        except ValueError:
            idx = -1
        new = BG_PRESETS[(idx + 1) % len(BG_PRESETS)]
        self.cfg['panel_bg'] = new
        save_settings(self.cfg)
        if self.showing_settings and self.settings_win:
            self._recolor_settings(new)

    def _recolor_settings(self, color):
        w = self.settings_win
        if not w:
            return
        self._pbg = color
        pw, ph = 420, 300
        self._draw_balatro_bg(pw, ph, color)
        try:
            for child in w.winfo_children():
                try:
                    child.config(bg=color)
                    for grand in child.winfo_children():
                        try:
                            grand.config(bg=color)
                        except:
                            pass
                except:
                    pass
        except:
            pass

    def on_key_press(self, key):
        self.is_typing = True
        self.mouse_still_time = 0
        if self.typing_timer:
            self.window.after_cancel(self.typing_timer)
        self.typing_timer = self.window.after(self.timer_buffer, self.stop_typing)
        if key in (keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
            self.ctrl_pressed = True
        if key == keyboard.Key.f2:
            self.window.after(0, self._toggle_settings)
            return
        if self.ctrl_pressed:
            if key == keyboard.KeyCode.from_char('`'):
                self.window.after(0, self._toggle_settings)
                return
            if hasattr(key, 'vk') and key.vk == 192:
                self.window.after(0, self._toggle_settings)
                return
        if self.showing_settings and key == keyboard.Key.esc:
            self.window.after(0, self.close_settings)
            return
        self.wandering = False
        self.wander_target = None
        self.fox_mode = "patrol"

    def on_key_release(self, key):
        if key in (keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
            self.ctrl_pressed = False

    def stop_typing(self):
        self.is_typing = False
        self.typing_timer = None
        self.typing_frame_index = 0
        if not self.krita_open:
            self._restore()

    def _restore(self):
        if self.is_sleeping and self.sleeping_frames:
            self.state = "sleeping"
            self.label.config(image=self.sleeping_frames[0])
        elif self.is_idle and self.idle_frames:
            self.state = "idle"
            self.label.config(image=self.idle_frames[0])
        elif self.running_frames:
            self.state = "running"
            self.label.config(image=self.running_frames[0])

    def _advance_anim(self):
        if self.state == "typing" and self.typing_frames:
            self.typing_frame_index = (self.typing_frame_index + 1) % len(self.typing_frames)
            self.label.config(image=self.typing_frames[self.typing_frame_index])
        elif self.state == "doing" and self.doing_frames:
            self.doing_frame_index += 1
            if self.doing_frame_index >= len(self.doing_frames):
                self.doing_play_count += 1
                if self.doing_play_count >= 3:
                    self.is_doing = False
                    self.doing_play_count = 0
                    self.doing_frame_index = 0
                    self.sleep_after_doing = False
                    self.is_sleeping = True
                    self.is_idle = False
                    self.state = "sleeping"
                    self.sleeping_frame_index = 0
                    if self.sleeping_frames:
                        self.label.config(image=self.sleeping_frames[0])
                    return
                self.doing_frame_index = 0
            self.label.config(image=self.doing_frames[self.doing_frame_index])
        elif self.state == "idle" and self.idle_frames:
            self.idle_frame_index = (self.idle_frame_index + 1) % len(self.idle_frames)
            self.label.config(image=self.idle_frames[self.idle_frame_index])
        elif self.state == "sleeping" and self.sleeping_frames:
            self.sleeping_frame_index = (self.sleeping_frame_index + 1) % len(self.sleeping_frames)
            self.label.config(image=self.sleeping_frames[self.sleeping_frame_index])
        elif self.state == "krita" and self.krita_frames:
            self.krita_frame_index = (self.krita_frame_index + 1) % len(self.krita_frames)
            self.label.config(image=self.krita_frames[self.krita_frame_index])
        elif self.state == "running":
            if self.facing_right and self.running_right_frames:
                self.frame_index = (self.frame_index + 1) % len(self.running_right_frames)
                self.label.config(image=self.running_right_frames[self.frame_index])
            elif self.running_frames:
                self.frame_index = (self.frame_index + 1) % len(self.running_frames)
                self.label.config(image=self.running_frames[self.frame_index])

    def check_running_software(self):
        running = False
        for p in psutil.process_iter(['name']):
            try:
                if p.info['name'] and 'krita' in p.info['name'].lower():
                    running = True
                    break
            except Exception:
                pass
        if running != self.krita_open:
            self.krita_open = running
            if running:
                sw, sh = self.window.winfo_screenwidth(), self.window.winfo_screenheight()
                kw = self.krita_frames[0].width() if self.krita_frames else 192
                kh = self.krita_frames[0].height() if self.krita_frames else 192
                self.x = sw - kw - 20
                self.y = sh - kh - 20
                self.window.geometry(f"+{int(self.x)}+{int(self.y)}")
                self.state = "krita"
                self.krita_frame_index = 0
                if self.krita_frames:
                    self.label.config(image=self.krita_frames[0])
            else:
                self.state = "running"
                self.is_idle = False
                self.is_sleeping = False
                self.mouse_still_time = 0
                self.frame_index = 0
                if self.running_frames:
                    self.label.config(image=self.running_frames[0])

    def _update_miko_character(self, mx, my, still, dist):
        if self.krita_open:
            return

        if self.is_typing or self.state == "typing":
            return

        if self.is_doing:
            return

        if dist > self.deadzone:
            self.state = "running"
            self.is_idle = False
            self.is_sleeping = False
            t = self.speed / dist
            self.x += (mx - self.x) * t
            self.y += (my - self.y) * t
            self.window.geometry(f"+{int(self.x)}+{int(self.y)}")
        else:
            if not still:
                self.is_idle = False
                self.is_sleeping = False
                self.state = "running"
            elif self.mouse_still_time >= self.sleep_timeout:
                if not self.is_sleeping and not self.is_doing:
                    if random.random() < 0.5 and self.doing_frames:
                        self.is_doing = True
                        self.is_idle = False
                        self.state = "doing"
                        self.doing_frame_index = 0
                        self.doing_play_count = 0
                        self.sleep_after_doing = True
                    else:
                        self.is_sleeping = True
                        self.is_idle = False
                        self.state = "sleeping"
                        self.sleeping_frame_index = 0
                        if self.sleeping_frames:
                            self.label.config(image=self.sleeping_frames[0])
            elif self.mouse_still_time > 0 and not self.is_sleeping:
                if not self.is_idle and not self.is_doing:
                    self.is_idle = True
                    self.state = "idle"
                    self.idle_frame_index = 0
                    if self.idle_frames:
                        self.label.config(image=self.idle_frames[0])

    def _update_chungus_character(self, mx, my, still, dist):
        if self.fox_mode == "patrol":
            if not self.patrol_target:
                sw = self.window.winfo_screenwidth()
                sh = self.window.winfo_screenheight()
                pad = 50
                self.patrol_target = (random.uniform(pad, sw - pad), random.uniform(pad, sh - pad))
            tx, ty = self.patrol_target
            dx = tx - self.x
            dy = ty - self.y
            d = math.hypot(dx, dy)
            self.facing_right = dx > 0
            if d < 5:
                self.patrol_target = None
                self.fox_mode = "resting"
                self.rest_counter = 0
                self.is_idle = True
                self.state = "idle"
                self.idle_frame_index = 0
                if self.idle_frames:
                    self.label.config(image=self.idle_frames[0])
            else:
                self.state = "running"
                self.is_idle = False
                t = self.speed / d
                self.x += dx * t
                self.y += dy * t
                self.window.geometry(f"+{int(self.x)}+{int(self.y)}")

        elif self.fox_mode == "resting":
            self.rest_counter += 1
            if self.rest_counter >= self.rest_duration_ticks:
                self.fox_mode = "patrol"
                self.patrol_target = None
                self.is_idle = False
                self.state = "running"
                self.rest_counter = 0

    def update_miko(self):
        try:
            self.check_software_counter += 1
            if self.check_software_counter >= 100:
                self.check_software_counter = 0
                self.check_running_software()

            if not self.krita_open and self.state != "typing" and self.is_typing:
                self.state = "typing"
                self.typing_frame_index = 0
                if self.typing_frames:
                    self.label.config(image=self.typing_frames[0])

            self.anim_accumulator += self.update_delay
            if self.anim_accumulator >= self.anim_interval:
                self.anim_accumulator -= self.anim_interval
                self._advance_anim()

            if self.is_typing:
                self.window.after(self.update_delay, self.update_miko)
                return

            mx = self.window.winfo_pointerx()
            my = self.window.winfo_pointery()

            if self.krita_open:
                sw, sh = self.window.winfo_screenwidth(), self.window.winfo_screenheight()
                kw = self.krita_frames[0].width() if self.krita_frames else 192
                kh = self.krita_frames[0].height() if self.krita_frames else 192
                self.x = sw - kw - 20
                self.y = sh - kh - 20
                self.window.geometry(f"+{int(self.x)}+{int(self.y)}")
                self.last_mouse_x = mx
                self.last_mouse_y = my
                self.window.after(self.update_delay, self.update_miko)
                return

            still = (mx == self.last_mouse_x and my == self.last_mouse_y)
            self.last_mouse_x = mx
            self.last_mouse_y = my

            if still:
                self.mouse_still_time += self.update_delay
            else:
                self.mouse_still_time = 0

            self.facing_right = (mx - self.x) > 0
            dist_mouse = math.hypot(mx - self.x, my - self.y)

            if self.character == "chungus":
                self._update_chungus_character(mx, my, still, dist_mouse)
            else:
                self._update_miko_character(mx, my, still, dist_mouse)

        except Exception as e:
            print(f"update err: {e}")
        self.window.after(self.update_delay, self.update_miko)


if __name__ == "__main__":
    Miko()
