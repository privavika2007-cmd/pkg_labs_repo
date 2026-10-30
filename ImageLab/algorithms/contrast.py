import numpy as np

from algorithms.colorspace import replace_value, value_channel
from algorithms.histogram import apply_lut_plane, clahe_plane, equalize_lut, histogram
from memory.buffer import PixelBuffer


def stretch_lut(low, high):
    levels = np.arange(256, dtype=np.float64)
    if high <= low:
        return np.where(levels > low, 255, 0).astype(np.uint8)
    values = (levels - low) * 255.0 / (high - low)
    return np.clip(np.rint(values), 0, 255).astype(np.uint8)


def percentile_bounds(hist, percent):
    total = int(hist.sum())
    if total == 0:
        return 0, 255
    target = total * percent / 100.0
    below = np.cumsum(hist)
    above = total - below + hist
    low = int(np.argmax(below > target))
    candidates = np.nonzero(above > target)[0]
    high = int(candidates[-1]) if candidates.size else 255
    return low, high


def linear_contrast(buffer, mode, percent=0.0, low=0, high=255, job=None, workers=None):
    if mode == "manual":
        lut = stretch_lut(low, high)
        planes = [apply_lut_plane(p, lut, job, workers) for p in buffer.planes()]
        return PixelBuffer.from_planes(planes), f"окно [{low}; {high}] -> [0; 255]"

    if mode == "value" and buffer.is_color:
        value = value_channel(buffer)
        hist = histogram(value)
        low, high = percentile_bounds(hist, percent)
        mapped = apply_lut_plane(value, stretch_lut(low, high), job, workers)
        return replace_value(buffer, mapped, job, workers), f"V (HSV): [{low}; {high}] -> [0; 255]"

    hists = [histogram(p) for p in buffer.planes()]
    if mode == "channels":
        planes = []
        notes = []
        for plane, hist in zip(buffer.planes(), hists):
            lo, hi = percentile_bounds(hist, percent)
            planes.append(apply_lut_plane(plane, stretch_lut(lo, hi), job, workers))
            notes.append(f"[{lo}; {hi}]")
        return PixelBuffer.from_planes(planes), "по каналам: " + ", ".join(notes)

    lo, hi = percentile_bounds(sum(hists), percent)
    lut = stretch_lut(lo, hi)
    planes = [apply_lut_plane(p, lut, job, workers) for p in buffer.planes()]
    return PixelBuffer.from_planes(planes), f"общее окно [{lo}; {hi}] -> [0; 255]"


def equalize(buffer, mode, job=None, workers=None):
    if mode == "value" and buffer.is_color:
        value = value_channel(buffer)
        mapped = apply_lut_plane(value, equalize_lut(histogram(value)), job, workers)
        return replace_value(buffer, mapped, job, workers)
    planes = [apply_lut_plane(p, equalize_lut(histogram(p)), job, workers) for p in buffer.planes()]
    return PixelBuffer.from_planes(planes)


def clahe(buffer, tiles, clip_limit, job=None, workers=None):
    if buffer.is_color:
        value = value_channel(buffer)
        mapped = clahe_plane(value, tiles, tiles, clip_limit, job, workers)
        return replace_value(buffer, mapped, job, workers)
    return PixelBuffer(clahe_plane(buffer.plane(0), tiles, tiles, clip_limit, job, workers))
