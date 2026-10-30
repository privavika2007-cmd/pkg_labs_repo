import numpy as np

from algorithms.colorspace import replace_value, to_gray, value_channel
from algorithms.histogram import histogram
from algorithms.structuring import element_runs
from algorithms.threshold import binarize_plane, otsu_threshold
from core.parallel import run_strips
from memory.buffer import PixelBuffer, pad_plane

OPERATIONS = {
    "erode": "Эрозия",
    "dilate": "Дилатация",
    "open": "Открытие (эрозия, затем дилатация)",
    "close": "Закрытие (дилатация, затем эрозия)",
    "gradient": "Морфологический градиент (дилатация - эрозия)",
    "inner": "Внутренний градиент (изображение - эрозия)",
    "outer": "Внешний градиент (дилатация - изображение)",
    "tophat": "Top-Hat (изображение - открытие)",
    "blackhat": "Black-Hat (закрытие - изображение)",
}


def window_reduce(array, length, reducer):
    if length == 1:
        return array
    result = array
    span = 1
    while span * 2 <= length:
        result = reducer(result[:, :-span], result[:, span:])
        span *= 2
    if span < length:
        shift = length - span
        result = reducer(result[:, :-shift], result[:, shift:])
    return result


def extreme_of_strip(padded, runs, reducer, out_height, out_width):
    cache = {}
    result = None
    for row, start, length in runs:
        if length not in cache:
            cache[length] = window_reduce(padded, length, reducer)
        part = cache[length][row:row + out_height, start:start + out_width]
        if result is None:
            result = part.copy()
        else:
            reducer(result, part, out=result)
    return result


def sweep(plane, element, anchor, reducer, fill, border, job=None, workers=None):
    kernel_h, kernel_w = element.shape
    anchor_y, anchor_x = anchor
    height, width = plane.shape
    padded = pad_plane(plane, anchor_y, kernel_h - 1 - anchor_y, anchor_x, kernel_w - 1 - anchor_x, border, fill)
    runs = element_runs(element)

    def task(start, end):
        return extreme_of_strip(padded[start:end + kernel_h - 1], runs, reducer, end - start, width)

    return run_strips(height, task, job, workers)


def erode(plane, element, border, job=None, workers=None):
    anchor = (element.shape[0] // 2, element.shape[1] // 2)
    return sweep(plane, element, anchor, np.minimum, 255, border, job, workers)


def dilate(plane, element, border, job=None, workers=None):
    kernel_h, kernel_w = element.shape
    flipped = element[::-1, ::-1]
    anchor = (kernel_h - 1 - kernel_h // 2, kernel_w - 1 - kernel_w // 2)
    return sweep(plane, flipped, anchor, np.maximum, 0, border, job, workers)


def repeat(function, plane, element, border, count, job, workers):
    for _ in range(count):
        plane = function(plane, element, border, job, workers)
    return plane


def difference(larger, smaller):
    return np.clip(larger.astype(np.int16) - smaller.astype(np.int16), 0, 255).astype(np.uint8)


def morph_plane(plane, operation, element, iterations, border, job=None, workers=None):
    def eroded(source):
        return repeat(erode, source, element, border, iterations, job, workers)

    def dilated(source):
        return repeat(dilate, source, element, border, iterations, job, workers)

    if operation == "erode":
        return eroded(plane)
    if operation == "dilate":
        return dilated(plane)
    if operation == "open":
        return dilated(eroded(plane))
    if operation == "close":
        return eroded(dilated(plane))
    if operation == "gradient":
        return difference(dilated(plane), eroded(plane))
    if operation == "inner":
        return difference(plane, eroded(plane))
    if operation == "outer":
        return difference(dilated(plane), plane)
    if operation == "tophat":
        return difference(plane, dilated(eroded(plane)))
    if operation == "blackhat":
        return difference(eroded(dilated(plane)), plane)
    raise ValueError("неизвестная операция")


def morphology(buffer, operation, element, iterations=1, border="clamp", color_mode="channels",
               binarize=False, threshold=0, job=None, workers=None):
    note = ""
    if binarize:
        gray = to_gray(buffer, job, workers)
        plane = gray.plane(0)
        used = threshold if threshold > 0 else otsu_threshold(histogram(plane))
        binary = binarize_plane(plane, used, job, workers)
        result = morph_plane(binary, operation, element, iterations, border, job, workers)
        source = "Оцу" if threshold <= 0 else "ручной"
        return PixelBuffer(result), f"бинаризация, порог {used} ({source})"

    if buffer.is_color and color_mode == "value":
        value = value_channel(buffer)
        result = morph_plane(value, operation, element, iterations, border, job, workers)
        return replace_value(buffer, result, job, workers), "обработан канал яркости V (HSV)"

    planes = [morph_plane(p, operation, element, iterations, border, job, workers) for p in buffer.planes()]
    if buffer.is_color:
        note = "каждый канал RGB обработан отдельно"
    return PixelBuffer.from_planes(planes), note
