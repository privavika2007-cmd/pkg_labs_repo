import os
import threading
from concurrent.futures import ThreadPoolExecutor

import numpy as np

WORKERS = max(1, os.cpu_count() or 1)
MIN_ROWS = 32

_pool = ThreadPoolExecutor(max_workers=WORKERS)


class Cancelled(Exception):
    pass


class Job:
    def __init__(self):
        self.total = 0
        self.done = 0
        self.stop = threading.Event()
        self.lock = threading.Lock()

    def add(self, count):
        with self.lock:
            self.total += count

    def tick(self):
        with self.lock:
            self.done += 1

    def check(self):
        if self.stop.is_set():
            raise Cancelled()

    def cancel(self):
        self.stop.set()

    @property
    def fraction(self):
        with self.lock:
            if self.total == 0:
                return 0.0
            return min(1.0, self.done / self.total)


def split_rows(height, parts):
    parts = max(1, min(parts, height))
    edges = np.linspace(0, height, parts + 1).astype(int)
    return [(int(edges[i]), int(edges[i + 1])) for i in range(parts) if edges[i + 1] > edges[i]]


def run_strips(height, task, job=None, workers=None):
    workers = workers or WORKERS
    parts = 1 if workers == 1 else max(1, min(workers * 2, height // MIN_ROWS))
    strips = split_rows(height, parts)
    if job is not None:
        job.add(len(strips))

    def work(strip):
        if job is not None:
            job.check()
        result = task(strip[0], strip[1])
        if job is not None:
            job.tick()
        return result

    if workers == 1 or len(strips) == 1:
        results = [work(strip) for strip in strips]
    else:
        results = list(_pool.map(work, strips))
    return np.concatenate(results, axis=0)
