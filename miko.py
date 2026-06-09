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
    'panel_bg': '#1a1e3a', 'panel_fg': '#a0b0dd',
    'blur_behind': True, 'wander_timeout': 10,
}

SETTINGS_KEYS = [
    ('animation_fps', 'Anim FPS', 1, 30, 1),
    ('scale', 'Scale', 1, 4, 0.5),
    ('sleep_timeout', 'Sleep (s)', 5, 60, 5),
    ('speed', 'Speed', 1, 10, 1),
    ('deadzone', 'Deadzone', 10, 300, 10),
    ('click_through', 'Click Thru', 0, 1, 1),
    ('wander_timeout', 'Wander (s)', 0, 60, 5),
]

BG_PRESETS = ['#1a1e3a', '#2a1a3a', '#1a3a2a', '#3a2a1a', '#1a2a3a', '#2a2a2a']


def resource_path(filename):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, 'assets', 'miko ase', filename)
    return os.path.join(BASE, 'assets', 'miko ase', filename)


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

        self.running_frames = self.load_gif("runningcat.gif")
        self.running_right_frames = self.load_gif("cat right.gif")
        self.typing_frames = self.load_gif("typingcat.gif")
        self.idle_frames = self.load_gif("idle.gif")
        self.sleeping_frames = self.load_gif("sleepingcat.gif")
        self.krita_frames = self.load_gif("kritacat.gif")

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

        self.window.bind('<Escape>', lambda e: self.close_settings() if self.showing_settings else None)

        self.update_miko()
        self.window.mainloop()

    def load_gif(self, filename):
        path = resource_path(filename)
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
            print(f"cant load {filename}:", e)
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
        self.settings_row_frames = {}

        win = tk.Toplevel(self.window)
        win.overrideredirect(True)
        win.attributes('-topmost', True)
        win.attributes('-alpha', 0.80)
        pbg = self.cfg.get('panel_bg', '#1a1e3a')
        pfg = self.cfg.get('panel_fg', '#a0b0dd')
        win.config(bg=pbg)
        self.settings_win = win

        pw, ph = 420, 370
        tx, ty = self.window.winfo_x(), self.window.winfo_y()
        win.geometry(f"{pw}x{ph}+{max(0, tx - pw - 10)}+{max(0, ty - 20)}")
        win.update_idletasks()

        top = tk.Frame(win, bg=pbg, bd=0)
        top.pack(fill='x', padx=14, pady=(12, 0))
        tk.Label(top, text="MIKO", fg='#8899dd', bg=pbg,
                 font=('Segoe UI', 14, 'bold')).pack(side='left')
        close_lbl = tk.Label(top, text="[X]", fg='#dd6688', bg=pbg,
                             font=('Segoe UI', 14, 'bold'), cursor='hand2')
        close_lbl.pack(side='right')
        close_lbl.bind('<Button-1>', lambda e: self.close_settings())

        sep = tk.Frame(win, bg='#3a4070', height=1, bd=0)
        sep.pack(fill='x', padx=14, pady=(6, 0))

        body = tk.Frame(win, bg=pbg, bd=0)
        body.pack(fill='both', expand=True, padx=14, pady=(8, 10))

        for key, label, lo, hi, step in SETTINGS_KEYS:
            val = self.cfg.get(key, DEFAULTS[key])
            row_f = tk.Frame(body, bg=pbg, bd=0)
            row_f.pack(fill='x', pady=4)
            self.settings_row_frames[key] = row_f

            if isinstance(val, bool):
                txt = f"{label}: {'ON' if val else 'OFF'}"
            else:
                txt = f"{label}: {val}"
            val_lbl = tk.Label(row_f, text=txt, fg=pfg, bg=pbg,
                               font=('Segoe UI', 11), anchor='w', width=28)
            val_lbl.pack(side='left')
            self.settings_labels[key] = val_lbl

            lbl_m = tk.Label(row_f, text="[-]", fg='#ee9944', bg=pbg,
                             font=('Segoe UI', 11, 'bold'), cursor='hand2')
            lbl_m.pack(side='right')
            lbl_m.bind('<Button-1>', lambda e, k=key: self.click_setting(k, -1))

            lbl_p = tk.Label(row_f, text="[+]", fg='#44ee88', bg=pbg,
                             font=('Segoe UI', 11, 'bold'), cursor='hand2')
            lbl_p.pack(side='right', padx=(0, 6))
            lbl_p.bind('<Button-1>', lambda e, k=key: self.click_setting(k, 1))

        sep2 = tk.Frame(win, bg='#3a4070', height=1, bd=0)
        sep2.pack(fill='x', padx=14, pady=(4, 0))
        bottom = tk.Frame(win, bg=pbg, bd=0)
        bottom.pack(fill='x', padx=14, pady=(6, 10))
        fg2 = '#8899bb'
        bg_lbl = tk.Label(bottom, text="[Panel BG]", fg=fg2, bg=pbg,
                          font=('Segoe UI', 9), cursor='hand2')
        bg_lbl.pack(side='left')
        bg_lbl.bind('<Button-1>', lambda e: self._cycle_bg())
        blur_lbl = tk.Label(bottom, text="[Blur]", fg=fg2, bg=pbg,
                            font=('Segoe UI', 9), cursor='hand2')
        blur_lbl.pack(side='left', padx=(10, 0))
        blur_lbl.bind('<Button-1>', lambda e: self._toggle_blur())

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
        if key == 'click_through':
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

    def reload_gifs(self):
        old_state = self.state
        self.running_frames = self.load_gif("runningcat.gif")
        self.running_right_frames = self.load_gif("cat right.gif")
        self.typing_frames = self.load_gif("typingcat.gif")
        self.idle_frames = self.load_gif("idle.gif")
        self.sleeping_frames = self.load_gif("sleepingcat.gif")
        self.krita_frames = self.load_gif("kritacat.gif")
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
        try:
            w.config(bg=color)
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

    def _toggle_blur(self):
        on = not self.cfg.get('blur_behind', True)
        self.cfg['blur_behind'] = on
        save_settings(self.cfg)
        if self.showing_settings and self.settings_win:
            self.settings_win.attributes('-alpha', 0.65 if on else 0.80)

    def on_key_press(self, key):
        self.is_typing = True
        self.mouse_still_time = 0
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
        if self.typing_timer:
            self.window.after_cancel(self.typing_timer)
        self.typing_timer = self.window.after(self.timer_buffer, self.stop_typing)
        if self.wandering:
            self.wandering = False
            self.wander_target = None

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

    def update_miko(self):
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
            if self.wandering:
                self.wandering = False
                self.wander_target = None
                self.state = "running"

        if (self.wander_timeout > 0 and still and not self.wandering
                and not self.is_sleeping
                and self.mouse_still_time >= self.wander_timeout):
            sw = self.window.winfo_screenwidth()
            sh = self.window.winfo_screenheight()
            cw = max(1, self.label.winfo_width() or 64)
            ch = max(1, self.label.winfo_height() or 64)
            self.wander_target = (
                random.randint(10, max(11, sw - cw - 10)),
                random.randint(10, max(11, sh - ch - 10))
            )
            self.wandering = True
            self.is_idle = False
            self.is_sleeping = False
            self.mouse_still_time = 0

        if self.wandering and self.wander_target:
            tx, ty = self.wander_target
            dx = tx - self.x
            dy = ty - self.y
            d = math.hypot(dx, dy)
            self.facing_right = dx > 0
            if d < 5:
                self.wandering = False
                self.wander_target = None
                self.x = tx
                self.y = ty
                self.window.geometry(f"+{int(self.x)}+{int(self.y)}")
                self.is_sleeping = True
                self.is_idle = False
                self.state = "sleeping"
                self.sleeping_frame_index = 0
                if self.sleeping_frames:
                    self.label.config(image=self.sleeping_frames[0])
            else:
                self.state = "running"
                t = self.speed / d
                self.x += dx * t
                self.y += dy * t
                self.window.geometry(f"+{int(self.x)}+{int(self.y)}")
            self.window.after(self.update_delay, self.update_miko)
            return

        dx = mx - self.x
        dy = my - self.y
        self.facing_right = dx > 0
        dist = math.hypot(dx, dy)

        if dist > self.deadzone:
            self.state = "running"
            self.is_idle = False
            self.is_sleeping = False
            t = self.speed / dist
            self.x += dx * t
            self.y += dy * t
            self.window.geometry(f"+{int(self.x)}+{int(self.y)}")
        else:
            if not still:
                self.is_idle = False
                self.is_sleeping = False
                self.state = "running"
            elif self.mouse_still_time >= self.sleep_timeout:
                if not self.is_sleeping:
                    self.is_sleeping = True
                    self.is_idle = False
                    self.state = "sleeping"
                    self.sleeping_frame_index = 0
                    if self.sleeping_frames:
                        self.label.config(image=self.sleeping_frames[0])
            elif self.mouse_still_time > 0 and not self.is_sleeping:
                if not self.is_idle:
                    self.is_idle = True
                    self.state = "idle"
                    self.idle_frame_index = 0
                    if self.idle_frames:
                        self.label.config(image=self.idle_frames[0])

        self.window.after(self.update_delay, self.update_miko)


if __name__ == "__main__":
    Miko()
