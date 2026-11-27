import csv
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import matplotlib

matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from bench.benchmark import Benchmark, Stopped, per_pixel_ns

COLORS = ("#c0392b", "#e67e22", "#1f4e79", "#27ae60", "#8e44ad", "#16a085", "#7f8c8d")


def draw_charts(figure, data):
    figure.clear()
    by_count = figure.add_subplot(2, 2, 1)
    by_length = figure.add_subplot(2, 2, 2)
    circles = figure.add_subplot(2, 2, 3)
    bars = figure.add_subplot(2, 2, 4)
    for color, (name, entry) in zip(COLORS, data["lines"].items()):
        counts = [0] + [count for count, seconds in entry["marks"]]
        times = [0] + [seconds for count, seconds in entry["marks"]]
        by_count.plot(counts, times, marker="o", markersize=3, color=color, label=name)
    by_count.set_title("Отрезки: время от количества")
    by_count.set_xlabel("количество отрезков")
    by_count.set_ylabel("время, с")
    by_count.grid(alpha=0.3)
    by_count.legend(fontsize=7)
    for color, (name, points) in zip(COLORS, data["lengths"].items()):
        by_length.plot([length for length, value in points], [value for length, value in points],
                       marker="o", markersize=3, color=color, label=name)
    by_length.set_title("Отрезки: время одного от длины")
    by_length.set_xlabel("длина отрезка, пикселей")
    by_length.set_ylabel("время, мкс")
    by_length.grid(alpha=0.3)
    by_length.legend(fontsize=7)
    for color, (name, entry) in zip(COLORS[5:], data["circles"].items()):
        counts = [0] + [count for count, seconds in entry["marks"]]
        times = [0] + [seconds for count, seconds in entry["marks"]]
        circles.plot(counts, times, marker="o", markersize=3, color=color, label=name)
    circles.set_title("Окружности: время от количества")
    circles.set_xlabel("количество окружностей")
    circles.set_ylabel("время, с")
    circles.grid(alpha=0.3)
    circles.legend(fontsize=7)
    names = list(data["lines"]) + list(data["circles"])
    entries = list(data["lines"].values()) + list(data["circles"].values())
    values = [per_pixel_ns(entry) for entry in entries]
    bars.barh(range(len(names)), values, color=COLORS[:len(names)])
    bars.set_yticks(range(len(names)))
    bars.set_yticklabels(names, fontsize=7)
    bars.invert_yaxis()
    bars.set_title("Время на один пиксель")
    bars.set_xlabel("нс / пиксель")
    bars.grid(alpha=0.3, axis="x")
    figure.tight_layout()


class BenchmarkWindow(tk.Toplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("Бенчмарк: стресс-тест алгоритмов")
        self.geometry("1180x860")
        self.lines = tk.IntVar(value=100_000)
        self.circles = tk.IntVar(value=50_000)
        self.max_length = tk.IntVar(value=200)
        self.max_radius = tk.IntVar(value=100)
        self.messages = queue.Queue()
        self.benchmark = None
        self.data = None
        top = ttk.Frame(self, padding=8)
        top.pack(fill="x")
        for label, variable, low, high in (("Отрезков:", self.lines, 1000, 1_000_000),
                                           ("Окружностей:", self.circles, 1000, 500_000),
                                           ("Макс. длина:", self.max_length, 10, 450),
                                           ("Макс. радиус:", self.max_radius, 5, 300)):
            ttk.Label(top, text=label).pack(side="left")
            ttk.Spinbox(top, from_=low, to=high, increment=1000 if high > 1000 else 10,
                        textvariable=variable, width=9).pack(side="left", padx=(2, 12))
        self.start_button = ttk.Button(top, text="Запустить", command=self.start)
        self.start_button.pack(side="left")
        self.stop_button = ttk.Button(top, text="Остановить", command=self.stop, state="disabled")
        self.stop_button.pack(side="left", padx=4)
        actions = ttk.Frame(self, padding=(8, 0, 8, 6))
        actions.pack(fill="x")
        ttk.Button(actions, text="Сохранить графики…", command=self.save_png).pack(side="left")
        ttk.Button(actions, text="Сохранить CSV…", command=self.save_csv).pack(side="left", padx=4)
        self.progress = ttk.Progressbar(self, maximum=1.0)
        self.progress.pack(fill="x", padx=8)
        self.state = ttk.Label(self, text="Отрезки строятся «солнцем» из начала координат во все 8 октантов. "
                                          "Время — только заполнение виртуального растра, без интерфейса.")
        self.state.pack(fill="x", padx=8, pady=4)
        columns = ("algorithm", "count", "pixels", "time", "per_item", "per_pixel")
        self.table = ttk.Treeview(self, columns=columns, show="headings", height=8)
        for column, text, width in zip(columns, ("Алгоритм", "Примитивов", "Пикселей", "Время, с",
                                                 "мкс на примитив", "нс на пиксель"),
                                       (240, 100, 120, 100, 130, 120)):
            self.table.heading(column, text=text)
            self.table.column(column, width=width, anchor="center")
        self.table.pack(fill="x", padx=8)
        self.figure = Figure(figsize=(11, 6.2), dpi=90)
        self.chart = FigureCanvasTkAgg(self.figure, master=self)
        self.chart.get_tk_widget().pack(fill="both", expand=True, padx=8, pady=8)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def start(self):
        try:
            settings = (int(self.lines.get()), int(self.circles.get()),
                        int(self.max_length.get()), int(self.max_radius.get()))
        except (tk.TclError, ValueError):
            messagebox.showerror("Неверные данные", "Нужны целые числа", parent=self)
            return
        self.benchmark = Benchmark(*settings)
        self.start_button.config(state="disabled")
        self.stop_button.config(state="normal")
        self.progress["value"] = 0
        threading.Thread(target=self.work, daemon=True).start()
        self.after(100, self.poll)

    def work(self):
        stages = 4
        done = {"stage": 0, "title": None}

        def report(title, count, total):
            if title != done["title"]:
                done["title"] = title
                done["stage"] += 1
            self.messages.put(("progress", title, (done["stage"] - 1 + count / total) / stages))

        try:
            self.messages.put(("done", self.benchmark.run(report)))
        except Stopped:
            self.messages.put(("stopped",))

    def poll(self):
        try:
            while True:
                message = self.messages.get_nowait()
                if message[0] == "progress":
                    self.state.config(text=f"Идёт: {message[1]}")
                    self.progress["value"] = min(1.0, message[2])
                elif message[0] == "done":
                    self.show(message[1])
                    return
                else:
                    self.state.config(text="Остановлено")
                    self.finish()
                    return
        except queue.Empty:
            pass
        self.after(100, self.poll)

    def finish(self):
        self.start_button.config(state="normal")
        self.stop_button.config(state="disabled")

    def show(self, data):
        self.data = data
        self.finish()
        self.progress["value"] = 1.0
        self.state.config(text="Готово. Отрезков по октантам 1–8: " + ", ".join(map(str, data["octants"])))
        self.table.delete(*self.table.get_children())
        for group, count in (("lines", data["line_count"]), ("circles", data["circle_count"])):
            for name, entry in data[group].items():
                self.table.insert("", "end", values=(name, count, entry["pixels"], f"{entry['time']:.3f}",
                                                     f"{entry['time'] / count * 1e6:.2f}",
                                                     f"{per_pixel_ns(entry):.1f}"))
        draw_charts(self.figure, data)
        self.chart.draw()

    def stop(self):
        if self.benchmark is not None:
            self.benchmark.stop()

    def on_close(self):
        self.stop()
        self.destroy()

    def save_png(self):
        if self.data is None:
            return
        path = filedialog.asksaveasfilename(parent=self, defaultextension=".png", filetypes=[("PNG", "*.png")])
        if path:
            self.figure.savefig(path, dpi=150)

    def save_csv(self):
        if self.data is None:
            return
        path = filedialog.asksaveasfilename(parent=self, defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8-sig") as file:
            writer = csv.writer(file, delimiter=";")
            writer.writerow(["Алгоритм", "Количество", "Время, с"])
            for group in ("lines", "circles"):
                for name, entry in self.data[group].items():
                    for count, seconds in entry["marks"]:
                        writer.writerow([name, count, f"{seconds:.6f}".replace(".", ",")])
            writer.writerow([])
            writer.writerow(["Алгоритм", "Длина", "мкс на отрезок"])
            for name, points in self.data["lengths"].items():
                for length, value in points:
                    writer.writerow([name, length, f"{value:.3f}".replace(".", ",")])
