import math

import numpy as np

from algorithms.histogram import apply_lut_plane
from core.parallel import run_strips
from memory.buffer import PixelBuffer

LEVELS = np.arange(256, dtype=np.float64)


def finish(values):
    return np.clip(np.rint(values), 0, 255).astype(np.uint8)


def negative_lut():
    return finish(255 - LEVELS)


def linear_lut(gain, offset):
    return finish(gain * LEVELS + offset)


def brightness_lut(shift):
    return linear_lut(1.0, shift)


def contrast_lut(gain):
    return finish((LEVELS - 127.5) * gain + 127.5)


def gamma_lut(gamma):
    return finish(255.0 * (LEVELS / 255.0) ** gamma)


def log_lut(strength):
    scale = 255.0 / math.log(1.0 + 255.0 * strength)
    return finish(scale * np.log1p(strength * LEVELS))


def exp_lut(strength):
    scale = 255.0 / (math.exp(strength) - 1.0)
    return finish(scale * (np.exp(strength * LEVELS / 255.0) - 1.0))


def threshold_lut(threshold):
    return np.where(LEVELS > threshold, 255, 0).astype(np.uint8)


def solarize_lut(threshold):
    return finish(np.where(LEVELS < threshold, LEVELS, 255 - LEVELS))


def posterize_lut(levels):
    step = 256.0 / levels
    bins = np.floor(LEVELS / step)
    return finish(bins * 255.0 / (levels - 1))


def apply_lut(buffer, lut, job=None, workers=None):
    planes = [apply_lut_plane(plane, lut, job, workers) for plane in buffer.planes()]
    return PixelBuffer.from_planes(planes)


def apply_luts(buffer, luts, job=None, workers=None):
    planes = [apply_lut_plane(plane, luts[i], job, workers) for i, plane in enumerate(buffer.planes())]
    return PixelBuffer.from_planes(planes)


def resize_nearest(buffer, height, width):
    rows = np.minimum((np.arange(height) * buffer.height) // height, buffer.height - 1)
    cols = np.minimum((np.arange(width) * buffer.width) // width, buffer.width - 1)
    return PixelBuffer(buffer.data[rows][:, cols])


def match_channels(buffer, channels):
    if buffer.channels == channels:
        return buffer
    if channels == 3:
        return PixelBuffer(np.repeat(buffer.data, 3, axis=2))
    gray = (299 * buffer.data[:, :, 0].astype(np.uint32) + 587 * buffer.data[:, :, 1] + 114 * buffer.data[:, :, 2] + 500) // 1000
    return PixelBuffer(gray.astype(np.uint8))


def combine(first, second, operation, alpha=0.5, job=None, workers=None):
    second = match_channels(second, first.channels)
    if (second.height, second.width) != (first.height, first.width):
        second = resize_nearest(second, first.height, first.width)
    a = first.data
    b = second.data

    def task(start, end):
        x = a[start:end].astype(np.int32)
        y = b[start:end].astype(np.int32)
        if operation == "sum":
            result = x + y
        elif operation == "difference":
            result = x - y
        elif operation == "absdiff":
            result = np.abs(x - y)
        elif operation == "product":
            result = np.rint(x * y / 255.0)
        elif operation == "average":
            result = np.rint((x + y) / 2.0)
        elif operation == "blend":
            result = np.rint(alpha * x + (1.0 - alpha) * y)
        elif operation == "min":
            result = np.minimum(x, y)
        elif operation == "max":
            result = np.maximum(x, y)
        elif operation == "and":
            result = x & y
        elif operation == "or":
            result = x | y
        else:
            result = x ^ y
        return np.clip(result, 0, 255).astype(np.uint8)

    return PixelBuffer(run_strips(first.height, task, job, workers))
