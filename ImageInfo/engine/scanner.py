import os
import queue
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from parsers import EXTENSIONS, inspect

BATCH = 64


def find_files(paths, all_files, stop):
    folders = []
    for path in paths:
        if os.path.isdir(path):
            folders.append(path)
        elif os.path.isfile(path):
            yield path
    while folders and not stop.is_set():
        folder = folders.pop()
        try:
            with os.scandir(folder) as entries:
                for entry in entries:
                    if entry.is_dir(follow_symlinks=False):
                        folders.append(entry.path)
                    elif entry.is_file(follow_symlinks=False):
                        if all_files or os.path.splitext(entry.name)[1].lower() in EXTENSIONS:
                            yield entry.path
        except OSError:
            continue


def inspect_batch(paths, stop):
    if stop.is_set():
        return []
    return [inspect(path) for path in paths]


class Scanner:
    def __init__(self):
        self.messages = queue.Queue()
        self.stop = threading.Event()
        self.thread = None

    @property
    def busy(self):
        return self.thread is not None and self.thread.is_alive()

    def start(self, paths, all_files=False):
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self.run, args=(paths, all_files, self.stop), daemon=True)
        self.thread.start()

    def cancel(self):
        self.stop.set()

    def run(self, paths, all_files, stop):
        started = time.perf_counter()
        files = []
        for path in find_files(paths, all_files, stop):
            files.append(path)
            if len(files) % 2000 == 0:
                self.messages.put(("found", len(files)))
        self.messages.put(("total", len(files)))

        workers = min(8, (os.cpu_count() or 4) * 2)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            jobs = [pool.submit(inspect_batch, files[i:i + BATCH], stop) for i in range(0, len(files), BATCH)]
            for job in as_completed(jobs):
                rows = job.result()
                if rows:
                    self.messages.put(("rows", rows))
                if stop.is_set():
                    pool.shutdown(wait=False, cancel_futures=True)
                    break
        self.messages.put(("done", time.perf_counter() - started, stop.is_set()))
