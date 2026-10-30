import os
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from algorithms import contrast, morphology, pointwise, structuring
from core.parallel import WORKERS
from memory.buffer import PixelBuffer

HEIGHT, WIDTH = 3000, 4000


def measure(function, repeat=2):
    best = None
    for _ in range(repeat):
        start = time.perf_counter()
        function()
        spent = time.perf_counter() - start
        best = spent if best is None else min(best, spent)
    return best


def main():
    rng = np.random.default_rng(1)
    gray = PixelBuffer(rng.integers(0, 256, (HEIGHT, WIDTH), dtype=np.uint8))
    color = PixelBuffer(rng.integers(0, 256, (HEIGHT, WIDTH, 3), dtype=np.uint8))
    disk = structuring.make_element("Эллипс", 15, 15)
    box = structuring.make_element("Прямоугольник", 15, 15)
    cases = [
        ("Эрозия, эллипс 15×15, серое 12 Мп", lambda w: morphology.erode(gray.plane(0), disk, "clamp", workers=w)),
        ("Открытие, эллипс 15×15, серое 12 Мп", lambda w: morphology.morph_plane(gray.plane(0), "open", disk, 1, "clamp", workers=w)),
        ("Top-Hat, прямоугольник 15×15, серое 12 Мп", lambda w: morphology.morph_plane(gray.plane(0), "tophat", box, 1, "reflect", workers=w)),
        ("Градиент, эллипс 15×15, цветное 12 Мп", lambda w: morphology.morphology(color, "gradient", disk, 1, "clamp", workers=w)),
        ("Линейное контрастирование, цветное 12 Мп", lambda w: contrast.linear_contrast(color, "channels", 1.0, workers=w)),
        ("Гамма-коррекция, цветное 12 Мп", lambda w: pointwise.apply_lut(color, pointwise.gamma_lut(0.5), workers=w)),
        ("CLAHE 8×8, цветное 12 Мп", lambda w: contrast.clahe(color, 8, 3.0, workers=w)),
    ]
    print(f"{'Операция':<50}{'1 поток':>10}{f'{WORKERS} потоков':>14}{'ускорение':>12}")
    for title, function in cases:
        one = measure(lambda: function(1), 1)
        many = measure(lambda: function(WORKERS), 2)
        print(f"{title:<50}{one:>9.2f}с{many:>13.2f}с{one / many:>11.1f}×")


if __name__ == "__main__":
    main()
