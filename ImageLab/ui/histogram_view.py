import tkinter as tk

import numpy as np

from algorithms.colorspace import to_gray
from algorithms.histogram import histogram

CHANNEL_COLORS = ["#d9382b", "#2f9e44", "#2b6fd9"]
BACKGROUND = "#fafafa"


class HistogramView(tk.Canvas):
    def __init__(self, master, **kwargs):
        super().__init__(master, background=BACKGROUND, highlightthickness=1, highlightbackground="#bbbbbb", **kwargs)
        self.buffer = None
        self.log_scale = False
        self.bind("<Configure>", lambda event: self.redraw())

    def set_buffer(self, buffer, log_scale=False):
        self.buffer = buffer
        self.log_scale = log_scale
        self.redraw()

    def scaled(self, hist):
        values = hist.astype(np.float64)
        if self.log_scale:
            values = np.log1p(values)
        return values

    def redraw(self):
        self.delete("all")
        width = max(self.winfo_width(), 50)
        height = max(self.winfo_height(), 40)
        left, right, top, bottom = 10, width - 18, 8, height - 18
        self.create_line(left, bottom, right, bottom, fill="#888888")
        for level in (0, 64, 128, 192, 255):
            x = left + (right - left) * level / 255.0
            self.create_line(x, bottom, x, bottom + 4, fill="#888888")
            self.create_text(x, bottom + 11, text=str(level), fill="#555555", font=("TkDefaultFont", 8))
        if self.buffer is None:
            return
        gray = histogram(to_gray(self.buffer).plane(0))
        series = [(gray, "#b9b9b9", True)]
        if self.buffer.is_color:
            series += [(histogram(self.buffer.plane(c)), CHANNEL_COLORS[c], False) for c in range(3)]
        top_value = max(float(self.scaled(h).max()) for h, _, _ in series) or 1.0
        for hist, color, filled in series:
            values = self.scaled(hist) / top_value
            points = []
            for level in range(256):
                x = left + (right - left) * level / 255.0
                y = bottom - (bottom - top) * values[level]
                points.append((x, y))
            if filled:
                polygon = [(left, bottom)] + points + [(right, bottom)]
                self.create_polygon([c for p in polygon for c in p], fill=color, outline="")
            else:
                self.create_line([c for p in points for c in p], fill=color, width=1)
