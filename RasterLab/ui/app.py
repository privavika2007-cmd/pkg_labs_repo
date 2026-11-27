import time
import tkinter as tk
from tkinter import messagebox, ttk

import numpy as np
from PIL import ImageTk

from raster.engine import LINE_ALGORITHMS, bresenham_circle, pitteway_ellipse
from raster.grid import VirtualGrid
from ui.benchmark_window import BenchmarkWindow
from ui.explain import explain_circle, explain_ellipse, explain_line
from ui.help_text import HELP
from ui.painter import GridPainter

GRID_HALF = 100
MIN_SCALE = 3
MAX_SCALE = 60
CIRCLE = "Брезенхем (окружность)"
ELLIPSE = "Питвей (эллипс / дуга)"
ALGORITHMS = list(LINE_ALGORITHMS) + [CIRCLE, ELLIPSE]
FIELDS = {
    "line": (("x1", 0), ("y1", 0), ("x2", 8), ("y2", 3)),
    "circle": (("xc", 0), ("yc", 0), ("R", 7)),
    "ellipse": (("xc", 0), ("yc", 0), ("a", 10), ("b", 6)),
}


def kind_of(name):
    if name == CIRCLE:
        return "circle"
    if name == ELLIPSE:
        return "ellipse"
    return "line"


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("RasterLab — базовые растровые алгоритмы")
        self.geometry("1360x820")
        self.minsize(1100, 680)
        self.grid_data = VirtualGrid(GRID_HALF, GRID_HALF)
        self.values = np.zeros((self.grid_data.height, self.grid_data.width))
        self.painter = GridPainter()
        self.scale_value = tk.DoubleVar(value=24)
        self.center_x = 4.0
        self.center_y = 1.5
        self.shape = None
        self.photo = None
        self.drag_start = None
        self.redraw_id = None
        self.algorithm = tk.StringVar(value=ALGORITHMS[2])
        self.clear_before = tk.BooleanVar(value=True)
        self.show_ideal = tk.BooleanVar(value=True)
        self.use_arc = tk.BooleanVar(value=False)
        self.arc_start = tk.IntVar(value=0)
        self.arc_end = tk.IntVar(value=135)
        self.field_vars = {}
        self._build()
        self.after(50, self.build_figure)

    def _build(self):
        left = ttk.Frame(self, padding=8)
        left.pack(side="left", fill="y")
        ttk.Label(left, text="Алгоритм", font=("TkDefaultFont", 12, "bold")).pack(anchor="w")
        box = ttk.Combobox(left, textvariable=self.algorithm, values=ALGORITHMS, state="readonly", width=28)
        box.pack(fill="x", pady=(2, 8))
        box.bind("<<ComboboxSelected>>", lambda event: self.on_algorithm())
        self.fields_frame = ttk.Frame(left)
        self.fields_frame.pack(fill="x")
        self.arc_frame = ttk.Frame(left)
        ttk.Checkbutton(self.arc_frame, text="Только дуга, углы (°):", variable=self.use_arc).grid(row=0, column=0, columnspan=4, sticky="w")
        ttk.Label(self.arc_frame, text="от").grid(row=1, column=0)
        ttk.Spinbox(self.arc_frame, from_=0, to=360, textvariable=self.arc_start, width=5).grid(row=1, column=1)
        ttk.Label(self.arc_frame, text="до").grid(row=1, column=2)
        ttk.Spinbox(self.arc_frame, from_=0, to=360, textvariable=self.arc_end, width=5).grid(row=1, column=3)
        buttons = ttk.Frame(left)
        buttons.pack(fill="x", pady=8)
        ttk.Button(buttons, text="Построить", command=self.build_figure).pack(side="left", expand=True, fill="x")
        ttk.Button(buttons, text="Очистить", command=self.clear).pack(side="left", expand=True, fill="x")
        ttk.Checkbutton(left, text="Очищать поле перед построением", variable=self.clear_before).pack(anchor="w")
        ttk.Checkbutton(left, text="Показывать идеальную фигуру", variable=self.show_ideal,
                        command=self.schedule_redraw).pack(anchor="w")
        ttk.Separator(left).pack(fill="x", pady=8)
        ttk.Label(left, text="Масштаб (точек на пиксель)").pack(anchor="w")
        scale_row = ttk.Frame(left)
        scale_row.pack(fill="x")
        ttk.Scale(scale_row, from_=MIN_SCALE, to=MAX_SCALE, variable=self.scale_value,
                  command=lambda value: self.schedule_redraw()).pack(side="left", fill="x", expand=True)
        self.scale_label = ttk.Label(scale_row, width=4)
        self.scale_label.pack(side="left")
        view_row = ttk.Frame(left)
        view_row.pack(fill="x", pady=4)
        ttk.Button(view_row, text="В центр", command=self.to_origin).pack(side="left", expand=True, fill="x")
        ttk.Button(view_row, text="Вписать фигуру", command=self.fit_shape).pack(side="left", expand=True, fill="x")
        ttk.Separator(left).pack(fill="x", pady=8)
        self.result_label = ttk.Label(left, text="", justify="left", wraplength=270)
        self.result_label.pack(anchor="w")
        ttk.Separator(left).pack(fill="x", pady=8)
        ttk.Button(left, text="Бенчмарк (стресс-тест)…", command=lambda: BenchmarkWindow(self)).pack(fill="x")
        ttk.Button(left, text="Справка: привязка к сетке", command=self.show_help).pack(fill="x", pady=4)

        right = ttk.Frame(self, padding=(0, 8, 8, 8))
        right.pack(side="left", fill="both", expand=True)
        panes = ttk.PanedWindow(right, orient="vertical")
        panes.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(panes, background="white", highlightthickness=1, highlightbackground="#bbbbbb")
        panes.add(self.canvas, weight=3)
        bottom = ttk.Frame(panes)
        panes.add(bottom, weight=2)
        self.explain_label = ttk.Label(bottom, text="", justify="left", font=("TkDefaultFont", 11))
        self.explain_label.pack(anchor="w", fill="x", pady=(6, 4))
        table_frame = ttk.Frame(bottom)
        table_frame.pack(fill="both", expand=True)
        self.table = ttk.Treeview(table_frame, show="headings", height=8)
        scroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.table.yview)
        self.table.configure(yscrollcommand=scroll.set)
        self.table.pack(side="left", fill="both", expand=True)
        scroll.pack(side="left", fill="y")
        self.status = ttk.Label(right, text="Наведите курсор на клетку", anchor="w")
        self.status.pack(fill="x")

        self.canvas.bind("<Configure>", lambda event: self.schedule_redraw())
        self.canvas.bind("<Motion>", self.on_motion)
        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<MouseWheel>", self.on_wheel)
        self.canvas.bind("<Button-4>", lambda event: self.zoom(1.15))
        self.canvas.bind("<Button-5>", lambda event: self.zoom(1 / 1.15))
        self.bind("<Return>", lambda event: self.build_figure())
        self.on_algorithm()

    def on_algorithm(self):
        for child in self.fields_frame.winfo_children():
            child.destroy()
        kind = kind_of(self.algorithm.get())
        self.field_vars = {}
        for index, (name, default) in enumerate(FIELDS[kind]):
            variable = tk.IntVar(value=default)
            self.field_vars[name] = variable
            ttk.Label(self.fields_frame, text=name).grid(row=index // 2, column=(index % 2) * 2, sticky="e", padx=(0, 4))
            low = 1 if name in ("a", "b") else (0 if name == "R" else -GRID_HALF)
            ttk.Spinbox(self.fields_frame, from_=low, to=GRID_HALF, textvariable=variable,
                        width=6).grid(row=index // 2, column=(index % 2) * 2 + 1, pady=2, padx=(0, 10))
        if kind == "ellipse":
            self.arc_frame.pack(after=self.fields_frame, fill="x", pady=(6, 0))
        else:
            self.arc_frame.pack_forget()

    def read_fields(self):
        values = {}
        for name, variable in self.field_vars.items():
            try:
                value = int(variable.get())
            except (tk.TclError, ValueError):
                raise ValueError(f"Поле {name}: нужно целое число")
            low = 1 if name in ("a", "b") else (0 if name == "R" else -GRID_HALF)
            if not low <= value <= GRID_HALF:
                raise ValueError(f"Поле {name}: допустимо от {low} до {GRID_HALF}")
            values[name] = value
        return values

    def make_job(self, name, values):
        kind = kind_of(name)
        if kind == "line":
            draw = LINE_ALGORITHMS[name]
            args = (values["x1"], values["y1"], values["x2"], values["y2"])
            return (lambda target, trace=None: draw(target, *args, trace),
                    ("line",) + args, explain_line(name, *args))
        if kind == "circle":
            args = (values["xc"], values["yc"], values["R"])
            return (lambda target, trace=None: bresenham_circle(target, *args, trace),
                    ("ellipse", args[0], args[1], args[2], args[2]), explain_circle(*args))
        args = (values["xc"], values["yc"], values["a"], values["b"])
        start, end = None, None
        if self.use_arc.get():
            start, end = int(self.arc_start.get()), int(self.arc_end.get())
        lines = explain_ellipse(*args)
        if start is not None:
            lines.append(f"Дуга: закрашиваются только пиксели с углом от {start}° до {end}°.")
        return (lambda target, trace=None: pitteway_ellipse(target, *args, trace, start, end),
                ("ellipse",) + args, lines)

    def build_figure(self):
        name = self.algorithm.get()
        try:
            values = self.read_fields()
            if kind_of(name) == "ellipse" and self.use_arc.get():
                int(self.arc_start.get())
                int(self.arc_end.get())
        except (ValueError, tk.TclError) as error:
            messagebox.showerror("Неверные данные", str(error), parent=self)
            return
        job, shape, lines = self.make_job(name, values)
        if self.clear_before.get():
            self.grid_data.clear()
        trace = []
        before = self.grid_data.painted
        job(self.grid_data, trace)
        calls = self.grid_data.painted - before
        microseconds = self.measure(job)
        self.values = np.array(self.grid_data.cells)
        self.shape = shape
        self.fill_table(trace)
        self.explain_label.config(text="\n".join(lines))
        self.result_label.config(text=f"{name}\nВызовов set_pixel: {calls}\n"
                                      f"Закрашено клеток на поле: {self.grid_data.filled()}\n"
                                      f"Время построения: {microseconds:.2f} мкс\n(среднее, time.perf_counter)")
        self.redraw()

    def measure(self, job):
        scratch = VirtualGrid(GRID_HALF, GRID_HALF)
        repeats = 0
        begin = time.perf_counter()
        elapsed = 0.0
        while elapsed < 0.05 or repeats < 5:
            job(scratch)
            repeats += 1
            elapsed = time.perf_counter() - begin
        return elapsed / repeats * 1e6

    def fill_table(self, trace):
        self.table.delete(*self.table.get_children())
        if not trace:
            self.table["columns"] = ()
            return
        columns = list(trace[0].keys())
        self.table["columns"] = columns
        for column in columns:
            self.table.heading(column, text=column)
            width = 260 if column in ("m1", "m2") else 110
            self.table.column(column, width=width, anchor="center", stretch=True)
        for row in trace[:3000]:
            self.table.insert("", "end", values=[str(row.get(column, "")) for column in columns])

    def clear(self):
        self.grid_data.clear()
        self.values = np.zeros((self.grid_data.height, self.grid_data.width))
        self.shape = None
        self.fill_table([])
        self.explain_label.config(text="")
        self.result_label.config(text="")
        self.redraw()

    def schedule_redraw(self):
        self.scale_label.config(text=str(int(self.scale_value.get())))
        if self.redraw_id is not None:
            self.after_cancel(self.redraw_id)
        self.redraw_id = self.after(15, self.redraw)

    def redraw(self):
        self.redraw_id = None
        width = max(self.canvas.winfo_width(), 50)
        height = max(self.canvas.winfo_height(), 50)
        shape = self.shape if self.show_ideal.get() else None
        image = self.painter.render(self.values, self.scale_value.get(), self.center_x, self.center_y,
                                    width, height, shape)
        self.photo = ImageTk.PhotoImage(image)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, image=self.photo, anchor="nw")
        self.scale_label.config(text=str(int(self.scale_value.get())))

    def to_world(self, event):
        scale = self.scale_value.get()
        x = self.center_x + (event.x - self.canvas.winfo_width() / 2) / scale
        y = self.center_y - (event.y - self.canvas.winfo_height() / 2) / scale
        return x, y

    def on_motion(self, event):
        x, y = self.to_world(event)
        cell_x = int(np.floor(x + 0.5))
        cell_y = int(np.floor(y + 0.5))
        brightness = self.grid_data.get(cell_x, cell_y)
        self.status.config(text=f"Курсор: ({x:.2f}; {y:.2f})  →  клетка ({cell_x}, {cell_y}) "
                                f"[область {cell_x - 0.5:+.1f}…{cell_x + 0.5:+.1f} по x]   яркость {brightness:.3f}")

    def on_press(self, event):
        self.drag_start = (event.x, event.y, self.center_x, self.center_y)

    def on_drag(self, event):
        if self.drag_start is None:
            return
        x0, y0, cx, cy = self.drag_start
        scale = self.scale_value.get()
        self.center_x = cx - (event.x - x0) / scale
        self.center_y = cy + (event.y - y0) / scale
        self.schedule_redraw()

    def on_wheel(self, event):
        if event.delta == 0:
            return
        self.zoom(1.15 if event.delta > 0 else 1 / 1.15)

    def zoom(self, factor):
        value = min(MAX_SCALE, max(MIN_SCALE, self.scale_value.get() * factor))
        self.scale_value.set(value)
        self.schedule_redraw()

    def to_origin(self):
        self.center_x = 0.0
        self.center_y = 0.0
        self.schedule_redraw()

    def fit_shape(self):
        if self.shape is None:
            return
        if self.shape[0] == "line":
            x1, y1, x2, y2 = self.shape[1:]
            left, right, bottom, top = min(x1, x2), max(x1, x2), min(y1, y2), max(y1, y2)
        else:
            xc, yc, a, b = self.shape[1:]
            left, right, bottom, top = xc - a, xc + a, yc - b, yc + b
        self.center_x = (left + right) / 2
        self.center_y = (bottom + top) / 2
        width = max(self.canvas.winfo_width(), 50)
        height = max(self.canvas.winfo_height(), 50)
        scale = min(width / (right - left + 4), height / (top - bottom + 4))
        self.scale_value.set(min(MAX_SCALE, max(MIN_SCALE, scale)))
        self.schedule_redraw()

    def show_help(self):
        window = tk.Toplevel(self)
        window.title("Справка")
        window.geometry("760x620")
        text = tk.Text(window, wrap="word", font=("TkDefaultFont", 12), padx=12, pady=10)
        text.insert("1.0", HELP)
        text.config(state="disabled")
        text.pack(fill="both", expand=True)
