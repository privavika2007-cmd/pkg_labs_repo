import numpy as np

from core.parallel import run_strips


def otsu_threshold(hist):
    total = hist.sum()
    if total == 0:
        return 127
    levels = np.arange(256, dtype=np.float64)
    prob = hist / total
    weight = np.cumsum(prob)
    mean = np.cumsum(prob * levels)
    mean_total = mean[-1]
    denominator = weight * (1.0 - weight)
    valid = denominator > 1e-12
    between = np.zeros(256)
    between[valid] = (mean_total * weight[valid] - mean[valid]) ** 2 / denominator[valid]
    return int(np.argmax(between))


def binarize_plane(plane, threshold, job=None, workers=None):
    return run_strips(
        plane.shape[0],
        lambda start, end: np.where(plane[start:end] > threshold, 255, 0).astype(np.uint8),
        job,
        workers,
    )
