from raster.target import RasterTarget


class VirtualGrid(RasterTarget):
    def __init__(self, half_width, half_height):
        self.half_width = half_width
        self.half_height = half_height
        self.width = 2 * half_width + 1
        self.height = 2 * half_height + 1
        self.cells = [[0.0] * self.width for _ in range(self.height)]
        self.painted = 0

    def set_pixel(self, x, y, intensity=1.0):
        column = x + self.half_width
        row = self.half_height - y
        if 0 <= column < self.width and 0 <= row < self.height:
            self.painted += 1
            if intensity > self.cells[row][column]:
                self.cells[row][column] = intensity

    def get(self, x, y):
        column = x + self.half_width
        row = self.half_height - y
        if 0 <= column < self.width and 0 <= row < self.height:
            return self.cells[row][column]
        return 0.0

    def clear(self):
        for row in self.cells:
            row[:] = [0.0] * self.width
        self.painted = 0

    def filled(self):
        return sum(1 for row in self.cells for value in row if value > 0)
