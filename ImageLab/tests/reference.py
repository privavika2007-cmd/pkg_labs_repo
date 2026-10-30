import math

import numpy as np

from memory.buffer import resolve_index


def naive_sweep(plane, element, take_min, border, fill):
    height, width = plane.shape
    kernel_h, kernel_w = element.shape
    anchor_y, anchor_x = kernel_h // 2, kernel_w // 2
    result = np.zeros_like(plane)
    for y in range(height):
        for x in range(width):
            best = None
            for i in range(kernel_h):
                for j in range(kernel_w):
                    if not element[i, j]:
                        continue
                    if take_min:
                        yy, xx = y + i - anchor_y, x + j - anchor_x
                    else:
                        yy, xx = y - (i - anchor_y), x - (j - anchor_x)
                    if border == "neutral" and not (0 <= yy < height and 0 <= xx < width):
                        value = fill
                    else:
                        value = int(plane[resolve_index(yy, height, border), resolve_index(xx, width, border)])
                    if best is None or (value < best if take_min else value > best):
                        best = value
            result[y, x] = best
    return result


def naive_erode(plane, element, border):
    return naive_sweep(plane, element, True, border, 255)


def naive_dilate(plane, element, border):
    return naive_sweep(plane, element, False, border, 0)


def naive_equalize(plane):
    hist = [0] * 256
    for value in plane.ravel():
        hist[int(value)] += 1
    total = plane.size
    cdf = []
    running = 0
    for count in hist:
        running += count
        cdf.append(running)
    cdf_min = next(c for c, h in zip(cdf, hist) if h > 0)
    if total == cdf_min:
        return plane.copy()
    result = np.zeros_like(plane)
    for y in range(plane.shape[0]):
        for x in range(plane.shape[1]):
            level = (cdf[int(plane[y, x])] - cdf_min) * 255.0 / (total - cdf_min)
            result[y, x] = min(255, max(0, int(math.floor(level + 0.5))))
    return result


def naive_otsu(plane):
    hist = [0] * 256
    for value in plane.ravel():
        hist[int(value)] += 1
    total = plane.size
    best_t, best_var = 0, -1.0
    for t in range(256):
        w0 = sum(hist[: t + 1])
        w1 = total - w0
        if w0 == 0 or w1 == 0:
            continue
        m0 = sum(i * hist[i] for i in range(t + 1)) / w0
        m1 = sum(i * hist[i] for i in range(t + 1, 256)) / w1
        var = (w0 / total) * (w1 / total) * (m0 - m1) ** 2
        if var > best_var + 1e-12:
            best_var, best_t = var, t
    return best_t
