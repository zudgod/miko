import tkinter as tk
import math
import ctypes
import os
import sys
from pynput import keyboard
import psutil
from fractions import Fraction


def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, 'assets', relative_path)
    return os.path.join(os.path.abspath('.'), 'assets', relative_path)

class Miko:
    def __init__(self):
        self.window = tk.Tk()
        self.window.overrideredirect(True)
        self.window.attributes('-topmost', True)
        self.window.config(bg='#ff00ff')
        self.window.attributes('-transparentcolor', '#ff00ff')

        try:
            hwnd = ctypes.windll.user32.GetParent(self.window.winfo_id())
            ws = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
            ctypes.windll.user32.SetWindowLongW(hwnd, -20, ws | 0x20)
        except Exception as e:
            print("click-through fail:", e)

        self.animation_fps = 5
        self.update_fps = 60
        self.update_delay = int(1000 / self.update_fps)
        self.anim_interval = int(1000 / self.animation_fps)
        self.anim_accumulator = 0

        self.is_typing = False
        self.typing_timer = None
        self.timer_buffer = 1000

        self.listener = keyboard.Listener(on_press=self.on_key_press)
        self.listener.start()

        self.deadzone = 100

        self.mouse_still_time = 0
        self.last_mouse_x = 0
        self.last_mouse_y = 0
        self.is_idle = False
        self.is_sleeping = False

        self.krita_open = False
        self.check_software_counter = 0

        self.state = "running"

        self.running_frames = []
        self.typing_frames = []
        self.idle_frames = []
        self.sleeping_frames = []
        self.krita_frames = []

        self.frame_index = 0
        self.typing_frame_index = 0
        self.idle_frame_index = 0
        self.sleeping_frame_index = 0
        self.krita_frame_index = 0

        self.scale = 2.0

        self.running_frames = self.load_gif("runningcat.gif", self.scale)
        self.running_right_frames = self.load_gif("cat right.gif", self.scale)
        self.typing_frames = self.load_gif("typingcat.gif", self.scale)
        self.idle_frames = self.load_gif("idle.gif", self.scale)
        self.sleeping_frames = self.load_gif("sleepingcat.gif", self.scale)
        self.krita_frames = self.load_gif("kritacat.gif", self.scale * 4)

        img = self.running_frames[0] if self.running_frames else None

        if img:
            self.label = tk.Label(self.window, image=img, bg='#ff00ff', bd=0)
        else:
            self.label = tk.Label(self.window, text="??", font=("Arial", 24), bg='#ff00ff', fg='white')
        self.label.pack()

        self.x = 0
        self.y = 0
        self.speed = 4
        self.facing_right = False

        self.update_miko()
        self.window.mainloop()

    def load_gif(self, filename, scale=1):
        path = resource_path(filename)
        frames = []
        try:
            i = 0
            while True:
                try:
                    frame = tk.PhotoImage(file=path, format=f"gif -index {i}")
                    if scale != 1:
                        f = Fraction(str(scale)).limit_denominator(100)
                        frame = frame.zoom(f.numerator, f.numerator).subsample(f.denominator, f.denominator)
                    frames.append(frame)
                    i += 1
                except tk.TclError:
                    break
        except Exception as e:
            print(f"cant load {filename}:", e)
        return frames

    def check_running_software(self):
        running = False
        for p in psutil.process_iter(['name']):
            try:
                if p.info['name'] and 'krita' in p.info['name'].lower():
                    running = True
                    break
            except:
                pass

        if running != self.krita_open:
            self.krita_open = running
            if running:
                sw = self.window.winfo_screenwidth()
                sh = self.window.winfo_screenheight()
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

    def on_key_press(self, key):
        self.is_typing = True
        self.mouse_still_time = 0

        if not self.krita_open:
            self.state = "typing"
            self.typing_frame_index = 0
            if self.typing_frames:
                self.label.config(image=self.typing_frames[0])

        if self.typing_timer:
            self.window.after_cancel(self.typing_timer)
        self.typing_timer = self.window.after(self.timer_buffer, self.stop_typing)

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

    def update_miko(self):
        self.check_software_counter += 1
        if self.check_software_counter >= 100:
            self.check_software_counter = 0
            self.check_running_software()

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
            sw = self.window.winfo_screenwidth()
            sh = self.window.winfo_screenheight()
            kw = self.krita_frames[0].width() if self.krita_frames else 192
            kh = self.krita_frames[0].height() if self.krita_frames else 192
            self.x = sw - kw - 20
            self.y = sh - kh - 20
            self.window.geometry(f"+{int(self.x)}+{int(self.y)}")
            self.last_mouse_x = mx
            self.last_mouse_y = my
            self.window.after(self.update_delay, self.update_miko)
            return

        dx = mx - self.x
        dy = my - self.y
        self.facing_right = dx > 0
        dist = math.hypot(dx, dy)

        still = (mx == self.last_mouse_x and my == self.last_mouse_y)
        self.last_mouse_x = mx
        self.last_mouse_y = my

        if still:
            self.mouse_still_time += self.update_delay
        else:
            self.mouse_still_time = 0

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
            elif self.mouse_still_time >= 10000:
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
