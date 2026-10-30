import numpy as np

from core.parallel import run_strips
from memory.buffer import PixelBuffer


def to_gray(buffer, job=None, workers=None):
    if not buffer.is_color:
        return buffer.copy()
    data = buffer.data

    def task(start, end):
        part = data[start:end].astype(np.uint32)
        gray = (299 * part[:, :, 0] + 587 * part[:, :, 1] + 114 * part[:, :, 2] + 500) // 1000
        return gray.astype(np.uint8)

    return PixelBuffer(run_strips(buffer.height, task, job, workers))


def value_channel(buffer):
    return buffer.data.max(axis=2)


def replace_value(buffer, new_value, job=None, workers=None):
    data = buffer.data
    old_value = data.max(axis=2)

    def task(start, end):
        rgb = data[start:end].astype(np.float32)
        old = old_value[start:end].astype(np.float32)
        new = new_value[start:end].astype(np.float32)
        scale = np.where(old > 0, new / np.maximum(old, 1.0), 0.0)
        result = rgb * scale[:, :, None]
        flat = old == 0
        result[flat] = new[flat][:, None]
        return np.clip(np.rint(result), 0, 255).astype(np.uint8)

    return PixelBuffer(run_strips(buffer.height, task, job, workers))
