import math
import random
import unittest

from raster.engine import (LINE_ALGORITHMS, bresenham_circle, bresenham_line, castle_pitteway_line,
                           castle_pitteway_moves, dda_line, pitteway_ellipse, step_line, wu_line)
from raster.grid import VirtualGrid
from raster.target import PixelList

EXACT_LINES = {name: draw for name, draw in LINE_ALGORITHMS.items() if draw is not wu_line}
OCTANT_ENDS = [(10, 3), (3, 10), (-3, 10), (-10, 3), (-10, -3), (-3, -10), (3, -10), (10, -3)]


def draw_points(draw, *args):
    target = PixelList()
    draw(target, *args)
    return target.points()


def deviation(points, x1, y1, x2, y2):
    if abs(x2 - x1) >= abs(y2 - y1):
        if x1 == x2:
            return 0.0
        return max(abs(y - (y1 + (y2 - y1) * (x - x1) / (x2 - x1))) for x, y in points)
    return max(abs(x - (x1 + (x2 - x1) * (y - y1) / (y2 - y1))) for x, y in points)


class LineTests(unittest.TestCase):
    def check_line(self, draw, x1, y1, x2, y2):
        points = draw_points(draw, x1, y1, x2, y2)
        self.assertEqual(len(points), max(abs(x2 - x1), abs(y2 - y1)) + 1)
        self.assertEqual(points[0], (x1, y1))
        self.assertEqual(points[-1], (x2, y2))
        self.assertLessEqual(deviation(points, x1, y1, x2, y2), 0.5 + 1e-9)
        for (ax, ay), (bx, by) in zip(points, points[1:]):
            self.assertEqual(max(abs(ax - bx), abs(ay - by)), 1)

    def test_all_octants(self):
        for name, draw in EXACT_LINES.items():
            for x2, y2 in OCTANT_ENDS:
                with self.subTest(algorithm=name, end=(x2, y2)):
                    self.check_line(draw, 0, 0, x2, y2)

    def test_special_cases(self):
        cases = [(0, 0, 0, 0), (0, 0, 7, 0), (0, 0, 0, -7), (0, 0, 6, 6), (0, 0, -6, 6), (2, -3, -5, 4)]
        for name, draw in EXACT_LINES.items():
            for case in cases:
                with self.subTest(algorithm=name, case=case):
                    self.check_line(draw, *case)

    def test_random_lines(self):
        generator = random.Random(4)
        for _ in range(2000):
            case = [generator.randint(-80, 80) for _ in range(4)]
            for name, draw in EXACT_LINES.items():
                with self.subTest(algorithm=name, case=case):
                    self.check_line(draw, *case)

    def test_known_example(self):
        self.assertEqual(draw_points(bresenham_line, 0, 0, 8, 3),
                         [(0, 0), (1, 0), (2, 1), (3, 1), (4, 2), (5, 2), (6, 2), (7, 3), (8, 3)])

    def test_castle_pitteway_equals_bresenham(self):
        generator = random.Random(5)
        for _ in range(3000):
            case = [generator.randint(-100, 100) for _ in range(4)]
            self.assertEqual(draw_points(castle_pitteway_line, *case), draw_points(bresenham_line, *case))

    def test_castle_pitteway_moves(self):
        self.assertEqual(castle_pitteway_moves(8, 3), "sdsdssds")
        for length in range(1, 60):
            for rise in range(length + 1):
                moves = castle_pitteway_moves(length, rise)
                self.assertEqual(len(moves), length)
                self.assertEqual(moves.count("d"), rise)

    def test_step_and_dda_differ_only_in_ties(self):
        generator = random.Random(6)
        for _ in range(2000):
            x1, y1, x2, y2 = [generator.randint(-80, 80) for _ in range(4)]
            step = draw_points(step_line, x1, y1, x2, y2)
            dda = draw_points(dda_line, x1, y1, x2, y2)
            for (ax, ay), (bx, by) in zip(step, dda):
                if (ax, ay) == (bx, by):
                    continue
                if abs(x2 - x1) >= abs(y2 - y1):
                    exact = y1 + (y2 - y1) * (ax - x1) / (x2 - x1)
                else:
                    exact = x1 + (x2 - x1) * (ay - y1) / (y2 - y1)
                self.assertAlmostEqual(abs(exact - math.floor(exact)), 0.5)


class WuTests(unittest.TestCase):
    def test_pairs_sum_to_one(self):
        for x2, y2 in OCTANT_ENDS + [(17, 5), (-9, 23)]:
            target = PixelList()
            wu_line(target, 0, 0, x2, y2)
            intensities = [intensity for x, y, intensity in target.pixels]
            for first, second in zip(intensities[::2], intensities[1::2]):
                self.assertAlmostEqual(first + second, 1.0)

    def test_fraction_gives_alpha(self):
        target = PixelList()
        wu_line(target, 0, 0, 10, 3)
        x, y, lower = target.pixels[2]
        x2, y2, upper = target.pixels[3]
        self.assertEqual((x, y, x2, y2), (1, 0, 1, 1))
        self.assertAlmostEqual(upper, 0.3)
        self.assertAlmostEqual(lower, 0.7)

    def test_brightness_center_on_ideal_line(self):
        generator = random.Random(7)
        for _ in range(300):
            x1, y1, x2, y2 = [generator.randint(-50, 50) for _ in range(4)]
            if abs(x2 - x1) < abs(y2 - y1) or x1 == x2:
                continue
            target = PixelList()
            wu_line(target, x1, y1, x2, y2)
            for (ax, ay, a), (bx, by, b) in zip(target.pixels[::2], target.pixels[1::2]):
                ideal = y1 + (y2 - y1) * (ax - x1) / (x2 - x1)
                self.assertAlmostEqual(ay * a + by * b, ideal)


class CircleTests(unittest.TestCase):
    def test_radius_error(self):
        for radius in range(0, 120):
            for x, y in draw_points(bresenham_circle, 5, -7, radius):
                self.assertLess(abs(math.hypot(x - 5, y + 7) - radius), 0.75)

    def test_symmetry(self):
        for radius in (1, 5, 17, 40):
            points = set(draw_points(bresenham_circle, 0, 0, radius))
            for x, y in points:
                for other in ((-x, y), (x, -y), (y, x), (-y, -x)):
                    self.assertIn(other, points)

    def test_closed_contour(self):
        for radius in range(1, 80):
            points = set(draw_points(bresenham_circle, 0, 0, radius))
            for x, y in points:
                neighbours = sum((x + i, y + j) in points for i in (-1, 0, 1) for j in (-1, 0, 1) if i or j)
                self.assertGreaterEqual(neighbours, 2)


class EllipseTests(unittest.TestCase):
    def test_close_to_ellipse(self):
        generator = random.Random(8)
        for _ in range(300):
            a = generator.randint(1, 70)
            b = generator.randint(1, 70)
            points = set(draw_points(pitteway_ellipse, 0, 0, a, b))
            for x, y in points:
                self.assertLessEqual(abs(math.hypot(x / a, y / b) - 1) * min(a, b), 1.0)
                neighbours = sum((x + i, y + j) in points for i in (-1, 0, 1) for j in (-1, 0, 1) if i or j)
                self.assertGreaterEqual(neighbours, 1)

    def test_axes_points(self):
        points = set(draw_points(pitteway_ellipse, 0, 0, 12, 5))
        for point in ((12, 0), (-12, 0), (0, 5), (0, -5)):
            self.assertIn(point, points)

    def test_circle_matches_radius(self):
        for radius in range(1, 60):
            for x, y in draw_points(pitteway_ellipse, 0, 0, radius, radius):
                self.assertLess(abs(math.hypot(x, y) - radius), 0.75)

    def test_arc(self):
        points = draw_points(pitteway_ellipse, 0, 0, 20, 10, None, 0, 90)
        self.assertTrue(points)
        self.assertTrue(all(x >= 0 and y >= 0 for x, y in points))


class GridTests(unittest.TestCase):
    def test_coordinates(self):
        grid = VirtualGrid(5, 3)
        grid.set_pixel(0, 0)
        grid.set_pixel(5, 3, 0.5)
        grid.set_pixel(-5, -3)
        grid.set_pixel(6, 0)
        self.assertEqual(grid.cells[3][5], 1.0)
        self.assertEqual(grid.cells[0][10], 0.5)
        self.assertEqual(grid.cells[6][0], 1.0)
        self.assertEqual(grid.filled(), 3)

    def test_keeps_brightest(self):
        grid = VirtualGrid(2, 2)
        grid.set_pixel(1, 1, 0.3)
        grid.set_pixel(1, 1, 0.8)
        grid.set_pixel(1, 1, 0.1)
        self.assertEqual(grid.get(1, 1), 0.8)
        grid.clear()
        self.assertEqual(grid.filled(), 0)


if __name__ == "__main__":
    unittest.main()
