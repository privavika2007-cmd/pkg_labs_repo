import math

import numpy as np
from PIL import Image, ImageDraw, ImageFont

BACKGROUND = np.array((255, 255, 255), dtype=float)
FILL = np.array((31, 78, 121), dtype=float)
GRID_LINE = np.array((205, 211, 220), dtype=float)
AXIS = np.array((30, 30, 30), dtype=float)
IDEAL = np.array((215, 40, 40), dtype=float)
TICK_STEPS = (1, 2, 5, 10, 20, 25, 50, 100, 200)


def load_font(size):
    for name in ("Arial.ttf", "arial.ttf", "DejaVuSans.ttf", "/System/Library/Fonts/Supplemental/Arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def tick_step(scale):
    for step in TICK_STEPS:
        if step * scale >= 34:
            return step
    return TICK_STEPS[-1]


def ideal_points(shape, scale):
    kind = shape[0]
    if kind == "line":
        x1, y1, x2, y2 = shape[1:]
        count = max(2, int(math.hypot(x2 - x1, y2 - y1) * scale * 2) + 1)
        t = np.linspace(0.0, 1.0, count)
        return x1 + (x2 - x1) * t, y1 + (y2 - y1) * t
    xc, yc, a, b = shape[1:5]
    count = max(16, int(2 * math.pi * max(a, b) * scale * 2))
    t = np.linspace(0.0, 2 * math.pi, count)
    return xc + a * np.cos(t), yc + b * np.sin(t)


class GridPainter:
    def __init__(self, font_size=12):
        self.font = load_font(font_size)

    def render(self, values, scale, center_x, center_y, width, height, shape=None):
        half_height = values.shape[0] // 2
        half_width = values.shape[1] // 2
        world_x = center_x + (np.arange(width) + 0.5 - width / 2) / scale
        world_y = center_y - (np.arange(height) + 0.5 - height / 2) / scale
        cell_x = np.floor(world_x + 0.5).astype(int)
        cell_y = np.floor(world_y + 0.5).astype(int)
        columns = cell_x + half_width
        rows = half_height - cell_y
        good_columns = (columns >= 0) & (columns < values.shape[1])
        good_rows = (rows >= 0) & (rows < values.shape[0])
        intensity = np.zeros((height, width))
        intensity[np.ix_(good_rows, good_columns)] = values[np.ix_(rows[good_rows], columns[good_columns])]
        picture = BACKGROUND + (FILL - BACKGROUND) * intensity[..., None]
        if scale >= 4:
            border_x = ((world_x + 0.5) % 1.0) * scale < 1.0
            border_y = ((world_y + 0.5) % 1.0) * scale < 1.0
            picture[:, border_x] = picture[:, border_x] * 0.55 + GRID_LINE * 0.45
            picture[border_y, :] = picture[border_y, :] * 0.55 + GRID_LINE * 0.45
        axis_x = np.abs(world_x) * scale < 0.75
        axis_y = np.abs(world_y) * scale < 0.75
        picture[:, axis_x] = AXIS
        picture[axis_y, :] = AXIS
        if shape is not None:
            xs, ys = ideal_points(shape, scale)
            screen_x = np.round((xs - center_x) * scale + width / 2 - 0.5).astype(int)
            screen_y = np.round((center_y - ys) * scale + height / 2 - 0.5).astype(int)
            for shift_x, shift_y in ((0, 0), (1, 0), (0, 1)):
                px = screen_x + shift_x
                py = screen_y + shift_y
                inside = (px >= 0) & (px < width) & (py >= 0) & (py < height)
                picture[py[inside], px[inside]] = IDEAL
        image = Image.fromarray(picture.astype(np.uint8), "RGB")
        self._labels(image, scale, center_x, center_y, width, height)
        return image

    def _labels(self, image, scale, center_x, center_y, width, height):
        draw = ImageDraw.Draw(image)
        step = tick_step(scale)
        axis_row = (center_y - 0) * scale + height / 2
        axis_column = (0 - center_x) * scale + width / 2
        label_row = min(max(axis_row + 4, 2), height - 16)
        label_column = min(max(axis_column - 4, 30), width - 2)
        left = math.ceil((center_x - width / 2 / scale) / step) * step
        right = math.floor((center_x + width / 2 / scale) / step) * step
        for value in range(int(left), int(right) + 1, step):
            if value == 0:
                continue
            x = (value - center_x) * scale + width / 2
            draw.text((x, label_row), str(value), fill=(70, 70, 70), font=self.font, anchor="mt")
        bottom = math.ceil((center_y - height / 2 / scale) / step) * step
        top = math.floor((center_y + height / 2 / scale) / step) * step
        for value in range(int(bottom), int(top) + 1, step):
            if value == 0:
                continue
            y = (center_y - value) * scale + height / 2
            draw.text((label_column, y), str(value), fill=(70, 70, 70), font=self.font, anchor="rm")
        draw.text((label_column, label_row), "0", fill=(70, 70, 70), font=self.font, anchor="rt")
        draw.text((width - 6, min(max(axis_row - 4, 14), height - 2)), "x", fill=(0, 0, 0), font=self.font, anchor="rb")
        draw.text((min(max(axis_column + 6, 2), width - 14), 4), "y", fill=(0, 0, 0), font=self.font, anchor="lt")
