import os
import queue
import sys
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import numpy as np
from PIL import Image, ImageTk

from algorithms.colorspace import to_gray
from algorithms.histogram import histogram
from core.context import Context
from core.methods import NeedSecondImage, build_methods
from core.parallel import WORKERS, Cancelled, Job
from memory.buffer import PixelBuffer
from ui.histogram_view import HistogramView

POLL_MS = 30
AUTO_DELAY_MS = 220


def base_dir():
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_buffer(path):
    with Image.open(path) as image:
        if image.mode in ("L", "1", "I;16", "I", "F", "LA"):
            image = image.convert("L")
        else:
            image = image.convert("RGB")
        return PixelBuffer(np.asarray(image))


def describe(buffer):
    gray = to_gray(buffer).plane(0)
    hist = histogram(gray)
    return (f"{buffer.width}×{buffer.height}, каналов: {buffer.channels}   "
            f"min {int(gray.min())}  max {int(gray.max())}  размах {int(gray.max()) - int(gray.min())}   "
            f"среднее {gray.mean():.1f}  σ {gray.std():.1f}   уровней {int((hist > 0).sum())}")


class ImagePane(ttk.Frame):
    def __init__(self, master, title, on_open):
        super().__init__(master)
        ttk.Label(self, text=title, font=("TkDefaultFont", 11, "bold")).pack(anchor="w")
        self.canvas = tk.Canvas(self, background="#2b2b2b", highlightthickness=0, width=300, height=260)
        self.canvas.pack(fill="both", expand=True)
        self.histogram = HistogramView(self, height=130)
        self.histogram.pack(fill="x", pady=(4, 0))
        self.stats = ttk.Label(self, text="", wraplength=420, justify="left")
        self.stats.pack(fill="x", anchor="w")
        self.buffer = None
        self.photo = None
        self.after_id = None
        self.canvas.bind("<Configure>", lambda event: self.schedule_redraw())
        self.canvas.bind("<Double-Button-1>", lambda event: on_open(self))

    def set_buffer(self, buffer, log_scale):
        self.buffer = buffer
        self.histogram.set_buffer(buffer, log_scale)
        self.stats.config(text="" if buffer is None else describe(buffer))
        self.redraw()

    def schedule_redraw(self):
        if self.after_id is not None:
            self.after_cancel(self.after_id)
        self.after_id = self.after(60, self.redraw)

    def redraw(self):
        self.after_id = None
        self.canvas.delete("all")
        if self.buffer is None:
            self.canvas.create_text(
                self.canvas.winfo_width() / 2, self.canvas.winfo_height() / 2,
                text="Нет изображения", fill="#aaaaaa")
            return
        width = max(self.canvas.winfo_width(), 10)
        height = max(self.canvas.winfo_height(), 10)
        scale = min(width / self.buffer.width, height / self.buffer.height)
        size = (max(1, int(self.buffer.width * scale)), max(1, int(self.buffer.height * scale)))
        image = Image.fromarray(self.buffer.to_array()).resize(size, Image.BILINEAR)
        self.photo = ImageTk.PhotoImage(image)
        self.canvas.create_image(width // 2, height // 2, image=self.photo)


class ParamPanel:
    def __init__(self, master, on_change):
        self.frame = ttk.Frame(master)
        self.on_change = on_change
        self.rows = {}
        self.vars = {}
        self.params = []
        self.labels = {}

    def build(self, params):
        for child in self.frame.winfo_children():
            child.destroy()
        self.rows.clear()
        self.vars.clear()
        self.labels.clear()
        self.params = params
        self.frame.columnconfigure(0, weight=1)
        for index, param in enumerate(params):
            row = ttk.Frame(self.frame)
            row.grid(row=index, column=0, sticky="ew", pady=2)
            row.columnconfigure(0, weight=1)
            self.rows[param.key] = row
            if param.kind == "scale":
                var = tk.DoubleVar(value=param.default)
                caption = ttk.Label(row, text=param.label)
                caption.grid(row=0, column=0, sticky="w")
                value_label = ttk.Label(row, text="", width=7, anchor="e")
                value_label.grid(row=0, column=1, sticky="e")
                scale = ttk.Scale(row, from_=param.low, to=param.high, variable=var,
                                  command=lambda raw, p=param: self.moved(p))
                scale.grid(row=1, column=0, columnspan=2, sticky="ew")
                self.labels[param.key] = value_label
                self.vars[param.key] = var
                self.snap(param)
            elif param.kind == "choice":
                var = tk.StringVar(value=param.default)
                ttk.Label(row, text=param.label).grid(row=0, column=0, sticky="w")
                box = ttk.Combobox(row, textvariable=var, values=param.choices, state="readonly")
                box.grid(row=1, column=0, sticky="ew")
                box.bind("<<ComboboxSelected>>", lambda event: self.changed())
                self.vars[param.key] = var
            elif param.kind == "check":
                var = tk.BooleanVar(value=param.default)
                ttk.Checkbutton(row, text=param.label, variable=var, command=self.changed).grid(row=0, column=0, sticky="w")
                self.vars[param.key] = var
            else:
                var = tk.StringVar(value=param.default)
                ttk.Label(row, text=param.label).grid(row=0, column=0, sticky="w")
                entry = ttk.Entry(row, textvariable=var)
                entry.grid(row=1, column=0, sticky="ew")
                entry.bind("<Return>", lambda event: self.changed())
                entry.bind("<FocusOut>", lambda event: self.changed())
                self.vars[param.key] = var
        self.refresh_visibility()

    def snap(self, param):
        var = self.vars[param.key]
        value = round(float(var.get()) / param.step) * param.step
        value = min(max(value, param.low), param.high)
        var.set(value)
        decimals = 0 if float(param.step).is_integer() else (2 if param.step < 0.1 else 1)
        self.labels[param.key].config(text=f"{value:.{decimals}f}")

    def moved(self, param):
        self.snap(param)
        self.on_change()

    def changed(self):
        self.refresh_visibility()
        self.on_change()

    def refresh_visibility(self):
        for param in self.params:
            row = self.rows[param.key]
            visible = all(self.vars[key].get() in allowed for key, allowed in param.only.items())
            if visible:
                row.grid()
            else:
                row.grid_remove()

    def values(self):
        result = {}
        for param in self.params:
            var = self.vars[param.key]
            if param.kind == "scale":
                value = round(float(var.get()) / param.step) * param.step
                result[param.key] = int(value) if float(param.step).is_integer() else value
            else:
                result[param.key] = var.get()
        return result


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("ImageLab: морфология и контрастирование")
        self.geometry("1320x860")
        self.minsize(1000, 680)
        self.source = None
        self.result = None
        self.second = None
        self.source_name = ""
        self.methods = build_methods()
        self.method = self.methods[0]
        self.jobs = None
        self.job = None
        self.token = 0
        self.results = queue.Queue()
        self.auto_id = None
        self.started = 0.0
        self.images_dir = os.path.join(base_dir(), "images")
        self.build_menu()
        self.build_layout()
        self.select_method(self.methods[0])
        self.after(POLL_MS, self.poll)

    def build_menu(self):
        bar = tk.Menu(self)
        file_menu = tk.Menu(bar, tearoff=False)
        file_menu.add_command(label="Открыть изображение…", command=self.open_source)
        file_menu.add_command(label="Открыть второе изображение…", command=self.open_second)
        file_menu.add_command(label="Сохранить результат…", command=self.save_result)
        file_menu.add_separator()
        file_menu.add_command(label="Выход", command=self.destroy)
        bar.add_cascade(label="Файл", menu=file_menu)
        samples = tk.Menu(bar, tearoff=False)
        if os.path.isdir(self.images_dir):
            for name in sorted(os.listdir(self.images_dir)):
                if name.lower().endswith((".png", ".jpg", ".bmp", ".tif", ".tiff")):
                    samples.add_command(label=name, command=lambda n=name: self.load_source(os.path.join(self.images_dir, n)))
        bar.add_cascade(label="Тестовая база", menu=samples)
        self.config(menu=bar)

    def build_layout(self):
        toolbar = ttk.Frame(self, padding=(8, 6))
        toolbar.pack(fill="x")
        ttk.Button(toolbar, text="Открыть…", command=self.open_source).pack(side="left")
        ttk.Button(toolbar, text="Второе изображение…", command=self.open_second).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Сохранить результат…", command=self.save_result).pack(side="left")
        ttk.Button(toolbar, text="Результат → исходное", command=self.promote).pack(side="left", padx=4)
        self.log_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(toolbar, text="Логарифмическая шкала гистограмм", variable=self.log_var,
                        command=self.show_all).pack(side="right")
        self.threads_var = tk.StringVar(value=str(WORKERS))
        ttk.Label(toolbar, text="Потоков:").pack(side="right", padx=(0, 4))
        ttk.Spinbox(toolbar, from_=1, to=64, width=4, textvariable=self.threads_var,
                    command=self.schedule_auto).pack(side="right", padx=(0, 14))

        body = ttk.PanedWindow(self, orient="horizontal")
        body.pack(fill="both", expand=True, padx=8)

        left = ttk.Frame(body, padding=(0, 0, 8, 0), width=340)
        body.add(left, weight=0)
        ttk.Label(left, text="Метод", font=("TkDefaultFont", 11, "bold")).pack(anchor="w")
        self.method_var = tk.StringVar()
        box = ttk.Combobox(left, textvariable=self.method_var, state="readonly",
                           values=[m.title for m in self.methods])
        box.pack(fill="x", pady=(0, 6))
        box.bind("<<ComboboxSelected>>", lambda event: self.select_method(
            next(m for m in self.methods if m.title == self.method_var.get())))
        self.panel = ParamPanel(left, self.schedule_auto)
        self.panel.frame.pack(fill="x")
        buttons = ttk.Frame(left)
        buttons.pack(fill="x", pady=8)
        ttk.Button(buttons, text="Применить", command=self.start).pack(side="left")
        ttk.Button(buttons, text="Отмена", command=self.cancel).pack(side="left", padx=4)
        self.auto_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(buttons, text="Автоприменение", variable=self.auto_var).pack(side="left", padx=6)
        ttk.Label(left, text="Пояснения", font=("TkDefaultFont", 11, "bold")).pack(anchor="w")
        holder = ttk.Frame(left)
        holder.pack(fill="both", expand=True)
        self.explain = tk.Text(holder, wrap="word", width=40, height=10, background="#f6f6f6", foreground="#202020", relief="flat")
        scroll = ttk.Scrollbar(holder, command=self.explain.yview)
        self.explain.config(yscrollcommand=scroll.set, state="disabled")
        scroll.pack(side="right", fill="y")
        self.explain.pack(side="left", fill="both", expand=True)

        right = ttk.Frame(body)
        body.add(right, weight=1)
        right.columnconfigure(0, weight=1)
        right.columnconfigure(1, weight=1)
        right.rowconfigure(0, weight=1)
        self.before = ImagePane(right, "До", self.view_full)
        self.after_pane = ImagePane(right, "После", self.view_full)
        self.before.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
        self.after_pane.grid(row=0, column=1, sticky="nsew", padx=(4, 0))

        bottom = ttk.Frame(self, padding=(8, 6))
        bottom.pack(fill="x")
        self.progress = ttk.Progressbar(bottom, mode="determinate", maximum=1.0, length=260)
        self.progress.pack(side="left")
        self.status = ttk.Label(bottom, text="Откройте изображение или выберите его в меню «Тестовая база»")
        self.status.pack(side="left", padx=10)

    def select_method(self, method):
        self.method = method
        self.method_var.set(method.title)
        self.panel.build(method.params)
        self.explain.config(state="normal")
        self.explain.delete("1.0", "end")
        self.explain.insert("1.0", method.explanation)
        self.explain.config(state="disabled")
        self.schedule_auto()

    def workers(self):
        try:
            return max(1, min(64, int(self.threads_var.get())))
        except ValueError:
            return WORKERS

    def show_all(self):
        log = self.log_var.get()
        self.before.set_buffer(self.source, log)
        self.after_pane.set_buffer(self.result, log)

    def load_source(self, path):
        try:
            buffer = load_buffer(path)
        except (OSError, ValueError) as error:
            messagebox.showerror("Ошибка", f"Не удалось открыть файл:\n{error}")
            return
        self.source = buffer
        self.source_name = os.path.basename(path)
        self.result = None
        self.title(f"ImageLab: {self.source_name}")
        self.show_all()
        self.status.config(text=f"{self.source_name}: {buffer.width}×{buffer.height}")
        self.schedule_auto(force=True)

    def open_source(self):
        initial = self.images_dir if os.path.isdir(self.images_dir) else os.getcwd()
        path = filedialog.askopenfilename(
            title="Исходное изображение", initialdir=initial,
            filetypes=[("Изображения", "*.png *.jpg *.jpeg *.bmp *.tif *.tiff *.gif"), ("Все файлы", "*.*")])
        if path:
            self.load_source(path)

    def open_second(self):
        initial = self.images_dir if os.path.isdir(self.images_dir) else os.getcwd()
        path = filedialog.askopenfilename(
            title="Второе изображение", initialdir=initial,
            filetypes=[("Изображения", "*.png *.jpg *.jpeg *.bmp *.tif *.tiff *.gif"), ("Все файлы", "*.*")])
        if not path:
            return
        try:
            self.second = load_buffer(path)
        except (OSError, ValueError) as error:
            messagebox.showerror("Ошибка", f"Не удалось открыть файл:\n{error}")
            return
        self.status.config(text=f"Второе изображение: {os.path.basename(path)}")
        self.schedule_auto()

    def save_result(self):
        if self.result is None:
            messagebox.showinfo("Нет результата", "Сначала примените метод.")
            return
        path = filedialog.asksaveasfilename(title="Сохранить результат", defaultextension=".png",
                                            filetypes=[("PNG", "*.png"), ("BMP", "*.bmp"), ("JPEG", "*.jpg")])
        if path:
            Image.fromarray(self.result.to_array()).save(path)
            self.status.config(text=f"Сохранено: {path}")

    def promote(self):
        if self.result is None:
            return
        self.source = self.result
        self.result = None
        self.show_all()
        self.schedule_auto(force=True)

    def view_full(self, pane):
        if pane.buffer is None:
            return
        window = tk.Toplevel(self)
        window.title("Полный размер")
        window.geometry("900x700")
        canvas = tk.Canvas(window, background="#2b2b2b")
        horizontal = ttk.Scrollbar(window, orient="horizontal", command=canvas.xview)
        vertical = ttk.Scrollbar(window, orient="vertical", command=canvas.yview)
        canvas.configure(xscrollcommand=horizontal.set, yscrollcommand=vertical.set)
        horizontal.pack(side="bottom", fill="x")
        vertical.pack(side="right", fill="y")
        canvas.pack(fill="both", expand=True)
        photo = ImageTk.PhotoImage(Image.fromarray(pane.buffer.to_array()))
        canvas.create_image(0, 0, anchor="nw", image=photo)
        canvas.configure(scrollregion=(0, 0, pane.buffer.width, pane.buffer.height))
        window.photo = photo

    def schedule_auto(self, force=False):
        if self.auto_id is not None:
            self.after_cancel(self.auto_id)
            self.auto_id = None
        if self.source is None:
            return
        if force or self.auto_var.get():
            self.auto_id = self.after(AUTO_DELAY_MS, self.start)

    def cancel(self):
        if self.job is not None:
            self.job.cancel()
        self.token += 1
        self.progress["value"] = 0
        self.status.config(text="Обработка отменена")

    def start(self):
        self.auto_id = None
        if self.source is None:
            return
        if self.job is not None:
            self.job.cancel()
        self.token += 1
        token = self.token
        job = Job()
        self.job = job
        method = self.method
        values = self.panel.values()
        source = self.source
        context = Context(job, self.workers(), self.second)
        self.started = time.perf_counter()
        self.status.config(text="Обработка…")

        def work():
            try:
                result, note = method.run(source, values, context)
                self.results.put((token, "ok", result, note, time.perf_counter() - self.started))
            except Cancelled:
                pass
            except NeedSecondImage as error:
                self.results.put((token, "error", None, str(error), 0.0))
            except ValueError as error:
                self.results.put((token, "error", None, str(error), 0.0))
            except Exception as error:
                self.results.put((token, "error", None, f"{type(error).__name__}: {error}", 0.0))

        threading.Thread(target=work, daemon=True).start()

    def poll(self):
        if self.job is not None:
            self.progress["value"] = self.job.fraction
        try:
            while True:
                token, kind, result, note, elapsed = self.results.get_nowait()
                if token != self.token:
                    continue
                self.progress["value"] = 1.0
                if kind == "ok":
                    self.result = result
                    self.after_pane.set_buffer(result, self.log_var.get())
                    detail = f" ({note})" if note else ""
                    self.status.config(
                        text=f"{self.method.title}: {elapsed * 1000:.0f} мс, потоков {self.workers()}{detail}")
                else:
                    self.status.config(text=f"Ошибка: {note}")
        except queue.Empty:
            pass
        self.after(POLL_MS, self.poll)
