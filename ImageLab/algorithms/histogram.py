import numpy as np

from core.parallel import run_strips


def histogram(plane):
    return np.bincount(np.ascontiguousarray(plane).ravel(), minlength=256).astype(np.int64)


def equalize_lut(hist):
    total = int(hist.sum())
    cdf = np.cumsum(hist)
    nonzero = cdf[hist > 0]
    if total == 0 or nonzero.size == 0:
        return np.arange(256, dtype=np.uint8)
    cdf_min = int(nonzero[0])
    if total == cdf_min:
        return np.arange(256, dtype=np.uint8)
    lut = np.rint((cdf - cdf_min) * 255.0 / (total - cdf_min))
    return np.clip(lut, 0, 255).astype(np.uint8)


def apply_lut_plane(plane, lut, job=None, workers=None):
    return run_strips(plane.shape[0], lambda start, end: lut[plane[start:end]], job, workers)


def clip_histogram(hist, limit):
    hist = hist.astype(np.int64).copy()
    over = np.maximum(hist - limit, 0)
    excess = int(over.sum())
    hist -= over
    hist += excess // 256
    rest = excess % 256
    if rest:
        step = max(1, 256 // rest)
        hist[0:step * rest:step] += 1
    return hist


def clahe_tables(plane, tiles_y, tiles_x, clip_limit):
    height, width = plane.shape
    tile_h = -(-height // tiles_y)
    tile_w = -(-width // tiles_x)
    tables = np.zeros((tiles_y, tiles_x, 256), dtype=np.float64)
    for ty in range(tiles_y):
        for tx in range(tiles_x):
            part = plane[ty * tile_h:(ty + 1) * tile_h, tx * tile_w:(tx + 1) * tile_w]
            count = part.size
            if count == 0:
                tables[ty, tx] = np.arange(256)
                continue
            hist = histogram(part)
            limit = max(1, int(clip_limit * count / 256))
            hist = clip_histogram(hist, limit)
            tables[ty, tx] = np.cumsum(hist) * 255.0 / count
    return tables, tile_h, tile_w


def clahe_plane(plane, tiles_y, tiles_x, clip_limit, job=None, workers=None):
    height, width = plane.shape
    tiles_y = max(1, min(tiles_y, height))
    tiles_x = max(1, min(tiles_x, width))
    tables, tile_h, tile_w = clahe_tables(plane, tiles_y, tiles_x, clip_limit)

    gx = (np.arange(width) + 0.5) / tile_w - 0.5
    x0 = np.floor(gx).astype(np.int64)
    fx = (gx - x0)[None, :]
    x1 = np.clip(x0 + 1, 0, tiles_x - 1)
    x0 = np.clip(x0, 0, tiles_x - 1)
    x0 = x0[None, :]
    x1 = x1[None, :]

    def task(start, end):
        gy = (np.arange(start, end) + 0.5) / tile_h - 0.5
        y0 = np.floor(gy).astype(np.int64)
        fy = (gy - y0)[:, None]
        y1 = np.clip(y0 + 1, 0, tiles_y - 1)[:, None]
        y0 = np.clip(y0, 0, tiles_y - 1)[:, None]
        values = plane[start:end]
        top = tables[y0, x0, values] * (1 - fx) + tables[y0, x1, values] * fx
        bottom = tables[y1, x0, values] * (1 - fx) + tables[y1, x1, values] * fx
        result = top * (1 - fy) + bottom * fy
        return np.clip(np.rint(result), 0, 255).astype(np.uint8)

    return run_strips(height, task, job, workers)
