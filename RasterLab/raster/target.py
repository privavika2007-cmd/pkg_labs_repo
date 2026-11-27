class RasterTarget:
    def set_pixel(self, x, y, intensity=1.0):
        raise NotImplementedError


class PixelList(RasterTarget):
    def __init__(self):
        self.pixels = []

    def set_pixel(self, x, y, intensity=1.0):
        self.pixels.append((x, y, intensity))

    def points(self):
        return [(x, y) for x, y, intensity in self.pixels if intensity > 0]
