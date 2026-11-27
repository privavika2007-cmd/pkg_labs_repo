import math
import random
import time

from raster.engine import (LINE_ALGORITHMS, bresenham_circle, pitteway_ellipse)
from raster.grid import VirtualGrid
from raster.target import RasterTarget

GRID_HALF = 500
LINE_COUNT = 100_000
CIRCLE_COUNT = 50_000
CHECKPOINTS = 10
LENGTHS = (25, 50, 100, 150, 200, 300, 400)
LINES_PER_LENGTH = 2_000
REPEATS = 3
CIRCLE_ALGORITHMS = {
    "Брезенхем (окружность)": lambda grid, x, y, r: bresenham_circle(grid, x, y, r),
    "Питвей (окружность a = b)": lambda grid, x, y, r: pitteway_ellipse(grid, x, y, r, r),
}


class Stopped(Exception):
    pass


class EmptyTarget(RasterTarget):
    def set_pixel(self, x, y, intensity=1.0):
        pass


def sun_lines(count, min_length, max_length, seed):
    generator = random.Random(seed)
    lines = []
    for _ in range(count):
        angle = generator.uniform(0, 2 * math.pi)
        length = generator.uniform(min_length, max_length)
        x2 = round(length * math.cos(angle))
        y2 = round(length * math.sin(angle))
        lines.append((0, 0, x2, y2))
    return lines


def random_circles(count, min_radius, max_radius, seed):
    generator = random.Random(seed)
    return [(generator.randint(-100, 100), generator.randint(-100, 100),
             generator.randint(min_radius, max_radius)) for _ in range(count)]


def octant(x2, y2):
    angle = math.degrees(math.atan2(y2, x2)) % 360
    return int(angle // 45) + 1


class Benchmark:
    def __init__(self, line_count=LINE_COUNT, circle_count=CIRCLE_COUNT, max_length=200, max_radius=100):
        self.line_count = line_count
        self.circle_count = circle_count
        self.max_length = max_length
        self.max_radius = max_radius
        self.stop_requested = False

    def stop(self):
        self.stop_requested = True

    def _check(self):
        if self.stop_requested:
            raise Stopped()

    def _measure(self, algorithms, items, report, title):
        grids = {name: VirtualGrid(GRID_HALF, GRID_HALF) for name in algorithms}
        totals = {name: 0.0 for name in algorithms}
        marks = {name: [] for name in algorithms}
        step = max(1, len(items) // CHECKPOINTS)
        for start in range(0, len(items), step):
            chunk = items[start:start + step]
            for name, draw in algorithms.items():
                self._check()
                totals[name] += self._time(draw, grids[name], chunk)
                marks[name].append((start + len(chunk), totals[name]))
            report(title, start + len(chunk), len(items))
        return {name: {"marks": marks[name], "time": totals[name], "pixels": grids[name].painted}
                for name in algorithms}

    def _time(self, draw, target, items):
        begin = time.perf_counter()
        for item in items:
            draw(target, *item)
        return time.perf_counter() - begin

    def run(self, report=lambda title, done, total: None):
        lines = sun_lines(self.line_count, 1, self.max_length, 1)
        circles = random_circles(self.circle_count, 1, self.max_radius, 2)
        octants = [0] * 8
        for x1, y1, x2, y2 in lines:
            octants[octant(x2, y2) - 1] += 1
        grid = VirtualGrid(GRID_HALF, GRID_HALF)
        result = {"line_count": self.line_count, "circle_count": self.circle_count,
                  "max_length": self.max_length, "max_radius": self.max_radius,
                  "octants": octants, "lines": {}, "circles": {}, "lengths": {}, "arithmetic": {}}
        result["lines"] = self._measure(LINE_ALGORITHMS, lines, report, "Отрезки")
        result["circles"] = self._measure(CIRCLE_ALGORITHMS, circles, report, "Окружности")
        empty = EmptyTarget()
        for repeat in range(REPEATS):
            for name, draw in LINE_ALGORITHMS.items():
                self._check()
                elapsed = self._time(draw, empty, lines)
                best = result["arithmetic"].get(name, elapsed)
                result["arithmetic"][name] = min(best, elapsed)
            report("Без записи в растр", repeat + 1, REPEATS)
        batches = {length: sun_lines(LINES_PER_LENGTH, length, length, length) for length in LENGTHS}
        best = {(name, length): float("inf") for name in LINE_ALGORITHMS for length in LENGTHS}
        for repeat in range(REPEATS):
            for length in LENGTHS:
                for name, draw in LINE_ALGORITHMS.items():
                    self._check()
                    grid.clear()
                    best[name, length] = min(best[name, length], self._time(draw, grid, batches[length]))
            report("Зависимость от длины", repeat + 1, REPEATS)
        for name in LINE_ALGORITHMS:
            result["lengths"][name] = [(length, best[name, length] / LINES_PER_LENGTH * 1e6) for length in LENGTHS]
        return result


def per_pixel_ns(entry):
    return entry["time"] / entry["pixels"] * 1e9 if entry["pixels"] else 0.0


if __name__ == "__main__":
    import json
    import sys

    def show(title, done, total):
        print(f"\r{title}: {done}/{total}", end="", flush=True)

    data = Benchmark().run(show)
    print()
    for group in ("lines", "circles"):
        for name, entry in data[group].items():
            print(f"{name:28} {entry['time']:8.3f} с  {entry['pixels']:>10} пикс.  {per_pixel_ns(entry):7.1f} нс/пикс.")
    if len(sys.argv) > 1:
        with open(sys.argv[1], "w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=1)
