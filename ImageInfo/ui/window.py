import csv
import os
import queue
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from engine import Scanner
from parsers.common import BROKEN, NOT_IMAGE, OK, READ_ERROR, WRONG_EXTENSION

from .help_text import FIELDS, HELP, SOURCES, STATUS

try:
    from PIL import Image, ImageTk
except ImportError:
    Image = None

COLUMNS = [
    ("name", "Имя файла", 240),
    ("kind", "Формат", 70),
    ("size", "Размер, px", 110),
    ("dpi", "Разрешение", 120),
    ("depth", "Глубина цвета", 250),
    ("compression", "Сжатие", 210),
    ("file_size", "Объём", 80),
    ("status", "Статус", 170),
]

TAGS = {BROKEN: "bad", WRONG_EXTENSION: "warn", NOT_IMAGE: "gray", READ_ERROR: "gray"}
FILTERS = ["Все файлы", "Только без ошибок", "Только с проблемами"]
PREVIEW = (380, 280)


def human_size(size):
    for unit in ("Б", "КБ", "МБ", "ГБ"):
        if size < 1024 or unit == "ГБ":
            return f"{size:.0f} {unit}" if unit == "Б" else f"{size:.1f} {unit}"
        size /= 1024


def first_number(text):
    digits = ""
    for char in text:
        if char.isdigit():
            digits += char
        elif digits:
            break
    return int(digits) if digits else -1


class App:
    def __init__(self, root):
        self.root = root
        self.scanner = Scanner()
        self.items = []
        self.shown = []
        self.waiting = []
        self.total = 0
        self.started = 0
        self.finished = True
        self.counts = {}
        self.sort_column = None
        self.sort_reverse = False
        self.preview_queue = queue.Queue()
        self.preview_number = 0
        self.photo = None

        root.title("Сведения о графических файлах")
        root.geometry("1440x820")
        root.minsize(1100, 620)
        self.build()
        root.bind("<Control-o>", lambda event: self.open_folder())
        root.after(40, self.poll)

    def build(self):
        style = ttk.Style()
        if "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure("Treeview", rowheight=24)
        style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"))
        style.configure("Accent.TButton", font=("Segoe UI", 10, "bold"))

        bar = ttk.Frame(self.root, padding=(10, 8))
        bar.pack(fill="x")
        self.folder_button = ttk.Button(bar, text="Открыть папку…", style="Accent.TButton", command=self.open_folder)
        self.folder_button.pack(side="left")
        self.files_button = ttk.Button(bar, text="Открыть файлы…", command=self.open_files)
        self.files_button.pack(side="left", padx=(6, 0))
        self.stop_button = ttk.Button(bar, text="Остановить", command=self.scanner_stop, state="disabled")
        self.stop_button.pack(side="left", padx=(6, 0))
        self.all_files = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="Проверять все файлы, а не только с расширениями картинок",
                        variable=self.all_files).pack(side="left", padx=(14, 0))
        ttk.Button(bar, text="Справка", command=self.show_help).pack(side="right")
        ttk.Button(bar, text="Сохранить в CSV…", command=self.export_csv).pack(side="right", padx=(0, 6))

        bar2 = ttk.Frame(self.root, padding=(10, 0, 10, 6))
        bar2.pack(fill="x")
        ttk.Label(bar2, text="Поиск по имени:").pack(side="left")
        self.search = tk.StringVar()
        self.search.trace_add("write", lambda *args: self.refill())
        ttk.Entry(bar2, textvariable=self.search, width=32).pack(side="left", padx=(6, 14))
        ttk.Label(bar2, text="Показать:").pack(side="left")
        self.filter = tk.StringVar(value=FILTERS[0])
        box = ttk.Combobox(bar2, textvariable=self.filter, values=FILTERS, state="readonly", width=22)
        box.pack(side="left", padx=(6, 0))
        box.bind("<<ComboboxSelected>>", lambda event: self.refill())
        self.summary = ttk.Label(bar2, text="")
        self.summary.pack(side="right")

        panes = ttk.PanedWindow(self.root, orient="horizontal")
        panes.pack(fill="both", expand=True, padx=10)

        table_frame = ttk.Frame(panes)
        self.tree = ttk.Treeview(table_frame, columns=[c[0] for c in COLUMNS], show="headings", selectmode="browse")
        for key, title, width in COLUMNS:
            self.tree.heading(key, text=title, command=lambda key=key: self.sort_by(key))
            self.tree.column(key, width=width, minwidth=50, anchor="w")
        self.tree.tag_configure("bad", background="#fbdcdc")
        self.tree.tag_configure("warn", background="#fff2c6")
        self.tree.tag_configure("gray", background="#e9e9e9", foreground="#555555")
        scroll_y = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        scroll_x = ttk.Scrollbar(table_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        scroll_y.grid(row=0, column=1, sticky="ns")
        scroll_x.grid(row=1, column=0, sticky="ew")
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)
        self.tree.bind("<<TreeviewSelect>>", self.on_select)
        panes.add(table_frame, weight=3)

        side = ttk.Frame(panes, padding=(10, 0, 0, 0))
        self.preview_box = tk.Frame(side, width=PREVIEW[0], height=PREVIEW[1], bg="#f3f4f6")
        self.preview_box.pack_propagate(False)
        self.preview_box.pack(fill="x")
        self.preview = tk.Label(self.preview_box, text="Выберите файл в таблице", bg="#f3f4f6", fg="#666666")
        self.preview.pack(fill="both", expand=True)
        self.details = tk.Text(side, wrap="word", width=48, relief="flat", padx=8, pady=8,
                               font=("Segoe UI", 10), bg="#fbfbfb")
        details_scroll = ttk.Scrollbar(side, orient="vertical", command=self.details.yview)
        self.details.configure(yscrollcommand=details_scroll.set, state="disabled")
        details_scroll.pack(side="right", fill="y", pady=(8, 0))
        self.details.pack(fill="both", expand=True, pady=(8, 0))
        self.details.tag_configure("title", font=("Segoe UI", 12, "bold"))
        self.details.tag_configure("label", font=("Segoe UI", 10, "bold"))
        self.details.tag_configure("hint", foreground="#6b7280", font=("Segoe UI", 9))
        self.details.tag_configure("mono", font=("Consolas", 9))
        self.details.tag_configure("bad", foreground="#b91c1c", font=("Segoe UI", 10, "bold"))
        panes.add(side, weight=1)

        bottom = ttk.Frame(self.root, padding=(10, 6))
        bottom.pack(fill="x")
        self.progress = ttk.Progressbar(bottom, mode="determinate")
        self.progress.pack(fill="x")
        self.state = ttk.Label(bottom, text="Откройте папку или файлы (Ctrl+O)")
        self.state.pack(anchor="w", pady=(4, 0))


    def open_folder(self):
        if self.scanner.busy:
            return
        folder = filedialog.askdirectory(title="Выберите папку с изображениями")
        if folder:
            self.start([folder])

    def open_files(self):
        if self.scanner.busy:
            return
        files = filedialog.askopenfilenames(title="Выберите файлы", filetypes=[
            ("Изображения", "*.jpg *.jpeg *.jpe *.jfif *.png *.gif *.bmp *.dib *.tif *.tiff *.pcx"),
            ("Все файлы", "*.*")])
        if files:
            self.start(list(files))

    def start(self, paths):
        self.items = []
        self.shown = []
        self.waiting = []
        self.counts = {}
        self.total = 0
        self.tree.delete(*self.tree.get_children())
        self.show_details(None)
        self.started = time.perf_counter()
        self.finished = False
        self.progress.configure(mode="indeterminate", value=0)
        self.progress.start(12)
        self.state.configure(text="Поиск файлов…")
        self.set_busy(True)
        self.scanner.start(paths, self.all_files.get())

    def scanner_stop(self):
        self.scanner.cancel()
        self.state.configure(text="Останавливаю…")

    def set_busy(self, busy):
        self.folder_button.configure(state="disabled" if busy else "normal")
        self.files_button.configure(state="disabled" if busy else "normal")
        self.stop_button.configure(state="normal" if busy else "disabled")

    def poll(self):
        handled = 0
        while handled < 200:
            try:
                message = self.scanner.messages.get_nowait()
            except queue.Empty:
                break
            handled += 1
            if message[0] == "found":
                self.state.configure(text=f"Поиск файлов… найдено {message[1]:,}".replace(",", " "))
            elif message[0] == "total":
                self.total = message[1]
                self.progress.stop()
                self.progress.configure(mode="determinate", maximum=max(1, self.total), value=0)
            elif message[0] == "rows":
                for info in message[1]:
                    number = len(self.items)
                    self.items.append(info)
                    self.counts[info.status] = self.counts.get(info.status, 0) + 1
                    if self.matches(info):
                        self.waiting.append(number)
            elif message[0] == "done":
                self.finish(message[1], message[2])

        if self.waiting:
            part = self.waiting[:400]
            del self.waiting[:400]
            for number in part:
                self.insert_row(number)

        if not self.finished:
            self.progress.configure(value=len(self.items))
            self.update_state()
        while not self.preview_queue.empty():
            self.show_preview(*self.preview_queue.get_nowait())
        self.root.after(15, self.poll)

    def finish(self, elapsed, cancelled):
        self.finished = True
        self.progress.stop()
        self.progress.configure(mode="determinate", maximum=max(1, self.total), value=len(self.items))
        self.set_busy(False)
        self.update_state(elapsed, cancelled)
        if self.sort_column:
            self.refill()

    def update_state(self, elapsed=None, cancelled=False):
        spent = elapsed if elapsed is not None else time.perf_counter() - self.started
        speed = len(self.items) / spent if spent > 0 else 0
        text = f"Обработано {len(self.items):,} из {self.total:,} · {spent:.2f} с · {speed:,.0f} файлов/с".replace(",", " ")
        if elapsed is not None:
            text = ("Остановлено. " if cancelled else "Готово. ") + text
        self.state.configure(text=text)
        parts = [f"Всего: {len(self.items)}", f"OK: {self.counts.get(OK, 0)}"]
        for status in (BROKEN, WRONG_EXTENSION, NOT_IMAGE, READ_ERROR):
            if self.counts.get(status):
                parts.append(f"{status}: {self.counts[status]}")
        self.summary.configure(text="   ".join(parts))

    def matches(self, info):
        text = self.search.get().strip().lower()
        if text and text not in info.name.lower():
            return False
        mode = self.filter.get()
        if mode == FILTERS[1]:
            return info.status == OK
        if mode == FILTERS[2]:
            return info.status != OK
        return True

    def insert_row(self, number):
        info = self.items[number]
        values = (info.name, info.kind or "—", info.size_text, info.dpi, info.depth,
                  info.compression, human_size(info.file_size), info.status)
        self.tree.insert("", "end", iid=str(number), values=values, tags=(TAGS.get(info.status, ""),))
        self.shown.append(number)

    def refill(self):
        self.tree.delete(*self.tree.get_children())
        self.shown = []
        numbers = [number for number, info in enumerate(self.items) if self.matches(info)]
        if self.sort_column:
            numbers.sort(key=lambda number: self.sort_value(self.items[number]), reverse=self.sort_reverse)
        self.waiting = numbers

    def sort_value(self, info):
        key = self.sort_column
        if key == "size":
            return info.width * info.height
        if key == "file_size":
            return info.file_size
        if key == "dpi":
            return first_number(info.dpi)
        if key == "depth":
            return first_number(info.depth)
        if key == "kind":
            return info.kind
        if key == "status":
            return info.status
        return getattr(info, key).lower() if isinstance(getattr(info, key), str) else getattr(info, key)

    def sort_by(self, key):
        if self.sort_column == key:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_column = key
            self.sort_reverse = False
        for column, title, _ in COLUMNS:
            arrow = (" ▼" if self.sort_reverse else " ▲") if column == key else ""
            self.tree.heading(column, text=title + arrow)
        self.refill()

    def on_select(self, event):
        selected = self.tree.selection()
        if not selected:
            return
        info = self.items[int(selected[0])]
        self.show_details(info)
        self.load_preview(info)

    def show_details(self, info):
        text = self.details
        text.configure(state="normal")
        text.delete("1.0", "end")
        if info is None:
            text.configure(state="disabled")
            self.preview.configure(image="", text="Выберите файл в таблице")
            return
        text.insert("end", info.name + "\n", "title")
        text.insert("end", info.path + "\n\n", "hint")
        if info.status != OK:
            text.insert("end", f"{info.status}: {info.problem}\n", "bad")
            text.insert("end", STATUS.get(info.status, "") + "\n\n", "hint")
        sources = SOURCES.get(info.kind, {})
        rows = [("Формат (по сигнатуре)", info.kind or "не определён"), ("Объём файла", human_size(info.file_size)),
                ("Размер, px", info.size_text), ("Разрешение", info.dpi), ("Глубина цвета", info.depth),
                ("Сжатие", info.compression)]
        for label, value in rows:
            text.insert("end", label + ": ", "label")
            text.insert("end", value + "\n")
            if label in sources:
                text.insert("end", "откуда: " + sources[label] + "\n", "hint")
            if label in FIELDS:
                text.insert("end", FIELDS[label] + "\n", "hint")
            text.insert("end", "\n")
        if info.extra:
            text.insert("end", "Дополнительно\n", "title")
            for label, value in info.extra.items():
                text.insert("end", label + ": ", "label")
                if "\n" in value:
                    text.insert("end", "\n" + value + "\n", "mono")
                    if label.startswith("Таблица квантования"):
                        text.insert("end", SOURCES["JPEG"]["Таблицы квантования"] + "\n", "hint")
                else:
                    text.insert("end", value + "\n")
                    hint = sources.get(label)
                    if hint:
                        text.insert("end", "откуда: " + hint + "\n", "hint")
        text.configure(state="disabled")

    def load_preview(self, info):
        self.preview_number += 1
        number = self.preview_number
        if Image is None:
            self.preview.configure(image="", text="Предпросмотр недоступен: не установлен Pillow")
            return
        if info.status in (NOT_IMAGE, READ_ERROR):
            self.preview.configure(image="", text="Это не изображение")
            return
        self.preview.configure(image="", text="Загрузка…")
        threading.Thread(target=self.render, args=(info.path, number), daemon=True).start()

    def render(self, path, number):
        try:
            with Image.open(path) as image:
                image.draft("RGB", PREVIEW)
                image.thumbnail(PREVIEW)
                if image.mode not in ("RGB", "RGBA"):
                    image = image.convert("RGBA")
                self.preview_queue.put((number, image.copy(), None))
        except Exception:
            self.preview_queue.put((number, None, "Картинку не удалось показать: файл повреждён"))

    def show_preview(self, number, image, error):
        if number != self.preview_number:
            return
        if image is None:
            self.preview.configure(image="", text=error)
            return
        self.photo = ImageTk.PhotoImage(image)
        self.preview.configure(image=self.photo, text="")

    def export_csv(self):
        if not self.items:
            messagebox.showinfo("Нечего сохранять", "Сначала откройте папку или файлы.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")],
                                            initialfile="сведения_о_файлах.csv")
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8-sig") as file:
            writer = csv.writer(file, delimiter=";")
            writer.writerow(["Путь", "Формат", "Ширина", "Высота", "Разрешение", "Глубина цвета",
                             "Сжатие", "Объём, байт", "Статус", "Причина"])
            for number in self.shown or range(len(self.items)):
                info = self.items[number]
                writer.writerow([info.path, info.kind, info.width, info.height, info.dpi, info.depth,
                                 info.compression, info.file_size, info.status, info.problem])
        self.state.configure(text=f"Сохранено: {os.path.basename(path)}")

    def show_help(self):
        window = tk.Toplevel(self.root)
        window.title("Справка")
        window.geometry("760x640")
        text = tk.Text(window, wrap="word", padx=14, pady=12, font=("Segoe UI", 10))
        text.pack(fill="both", expand=True)
        text.tag_configure("title", font=("Segoe UI", 12, "bold"))
        text.tag_configure("label", font=("Segoe UI", 10, "bold"))
        text.insert("end", HELP + "\n")
        text.insert("end", "Что означают характеристики\n", "title")
        for label, value in FIELDS.items():
            text.insert("end", label + ": ", "label")
            text.insert("end", value + "\n")
        text.insert("end", "\nОткуда берутся значения в каждом формате\n", "title")
        for kind, fields in SOURCES.items():
            text.insert("end", "\n" + kind + "\n", "label")
            for label, value in fields.items():
                text.insert("end", f"  {label}: {value}\n")
        text.configure(state="disabled")
