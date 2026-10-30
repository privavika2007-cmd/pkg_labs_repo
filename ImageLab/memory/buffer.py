import numpy as np

CLAMP = "clamp"
REFLECT = "reflect"
NEUTRAL = "neutral"

BORDER_NAMES = {
    CLAMP: "Дублирование границы (Clamp)",
    REFLECT: "Зеркальное отражение (Reflect)",
    NEUTRAL: "Нейтральное значение",
}


def resolve_index(index, size, mode):
    if mode == CLAMP:
        return min(max(index, 0), size - 1)
    if size == 1:
        return 0
    period = 2 * (size - 1)
    index %= period
    if index >= size:
        index = period - index
    return index


def pad_plane(plane, top, bottom, left, right, mode, fill=0):
    widths = ((top, bottom), (left, right))
    if mode == CLAMP:
        return np.pad(plane, widths, mode="edge")
    if mode == REFLECT:
        return np.pad(plane, widths, mode="reflect")
    return np.pad(plane, widths, mode="constant", constant_values=fill)


class PixelBuffer:
    def __init__(self, data):
        data = np.asarray(data)
        if data.ndim == 2:
            data = data[:, :, None]
        self.data = np.ascontiguousarray(data, dtype=np.uint8)

    @property
    def height(self):
        return self.data.shape[0]

    @property
    def width(self):
        return self.data.shape[1]

    @property
    def channels(self):
        return self.data.shape[2]

    @property
    def is_color(self):
        return self.channels == 3

    def plane(self, index):
        return self.data[:, :, index]

    def planes(self):
        return [self.data[:, :, i] for i in range(self.channels)]

    def pixel(self, y, x, mode=CLAMP):
        y = resolve_index(y, self.height, mode)
        x = resolve_index(x, self.width, mode)
        return self.data[y, x]

    def copy(self):
        return PixelBuffer(self.data.copy())

    def to_array(self):
        if self.channels == 1:
            return self.data[:, :, 0]
        return self.data

    @classmethod
    def from_planes(cls, planes):
        return cls(np.stack(planes, axis=2))
