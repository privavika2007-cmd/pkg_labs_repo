import os
import sys
import unittest

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from algorithms import contrast, histogram, morphology, pointwise, structuring, threshold
from algorithms.colorspace import to_gray
from memory.buffer import CLAMP, NEUTRAL, REFLECT, PixelBuffer, pad_plane, resolve_index
from tests import reference

RNG = np.random.default_rng(16)


def random_plane(height, width):
    return RNG.integers(0, 256, size=(height, width), dtype=np.uint8)


class BorderTests(unittest.TestCase):
    def test_padding_matches_index_rules(self):
        plane = random_plane(5, 7)
        for mode in (CLAMP, REFLECT):
            padded = pad_plane(plane, 3, 2, 4, 5, mode)
            for y in range(-3, 5 + 2):
                for x in range(-4, 7 + 5):
                    expected = plane[resolve_index(y, 5, mode), resolve_index(x, 7, mode)]
                    self.assertEqual(padded[y + 3, x + 4], expected)

    def test_reflect_on_tiny_image(self):
        self.assertEqual(resolve_index(-5, 1, REFLECT), 0)
        self.assertEqual(pad_plane(np.array([[9]], dtype=np.uint8), 2, 2, 2, 2, REFLECT).tolist(), [[9] * 5] * 5)


class MorphologyTests(unittest.TestCase):
    ELEMENTS = {
        "rect3x5": structuring.make_element("Прямоугольник", 5, 3),
        "ellipse7": structuring.make_element("Эллипс", 7, 7),
        "cross5": structuring.make_element("Крест", 5, 5),
        "diamond5x3": structuring.make_element("Ромб", 5, 3),
        "hline4": structuring.make_element("Горизонтальная линия", 4, 1),
        "vline2": structuring.make_element("Вертикальная линия", 1, 2),
        "diag": structuring.make_element("Диагональ \\", 4, 4),
        "custom": structuring.parse_matrix("1 0 1 1\n0 1 0 0\n1 1 0 1"),
    }

    def test_erode_dilate_match_naive(self):
        plane = random_plane(13, 17)
        for name, element in self.ELEMENTS.items():
            for border in (CLAMP, REFLECT, NEUTRAL):
                with self.subTest(element=name, border=border):
                    self.assertTrue(np.array_equal(
                        morphology.erode(plane, element, border), reference.naive_erode(plane, element, border)))
                    self.assertTrue(np.array_equal(
                        morphology.dilate(plane, element, border), reference.naive_dilate(plane, element, border)))

    def test_single_thread_equals_multi_thread(self):
        plane = random_plane(300, 211)
        element = structuring.make_element("Эллипс", 9, 9)
        one = morphology.erode(plane, element, REFLECT, workers=1)
        many = morphology.erode(plane, element, REFLECT, workers=8)
        self.assertTrue(np.array_equal(one, many))

    def test_compound_operations(self):
        plane = random_plane(20, 20)
        element = structuring.make_element("Прямоугольник", 3, 3)
        eroded = reference.naive_erode(plane, element, CLAMP)
        dilated = reference.naive_dilate(plane, element, CLAMP)
        opened = reference.naive_dilate(eroded, element, CLAMP)
        closed = reference.naive_erode(dilated, element, CLAMP)
        expected = {
            "open": opened,
            "close": closed,
            "gradient": dilated.astype(int) - eroded,
            "inner": plane.astype(int) - eroded,
            "outer": dilated.astype(int) - plane,
            "tophat": plane.astype(int) - opened,
            "blackhat": closed.astype(int) - plane,
        }
        for operation, value in expected.items():
            with self.subTest(operation=operation):
                result = morphology.morph_plane(plane, operation, element, 1, CLAMP)
                self.assertTrue(np.array_equal(result, np.clip(value, 0, 255).astype(np.uint8)))

    def test_iterations_equal_bigger_element(self):
        plane = random_plane(30, 30)
        small = structuring.make_element("Прямоугольник", 3, 3)
        big = structuring.make_element("Прямоугольник", 5, 5)
        twice = morphology.morph_plane(plane, "erode", small, 2, CLAMP)
        once = morphology.morph_plane(plane, "erode", big, 1, CLAMP)
        self.assertTrue(np.array_equal(twice, once))

    def test_algebraic_properties(self):
        plane = random_plane(25, 25)
        element = structuring.make_element("Эллипс", 5, 5)
        opened = morphology.morph_plane(plane, "open", element, 1, REFLECT)
        again = morphology.morph_plane(opened, "open", element, 1, REFLECT)
        self.assertTrue(np.array_equal(opened, again))
        self.assertTrue((opened <= plane).all())
        closed = morphology.morph_plane(plane, "close", element, 1, REFLECT)
        self.assertTrue((closed >= plane).all())

    def test_color_modes(self):
        data = RNG.integers(0, 256, size=(20, 24, 3), dtype=np.uint8)
        buffer = PixelBuffer(data)
        element = structuring.make_element("Крест", 3, 3)
        result, _ = morphology.morphology(buffer, "erode", element, 1, CLAMP, "channels")
        for c in range(3):
            self.assertTrue(np.array_equal(result.plane(c), reference.naive_erode(data[:, :, c], element, CLAMP)))
        value, _ = morphology.morphology(buffer, "dilate", element, 1, CLAMP, "value")
        self.assertEqual(value.data.shape, data.shape)

    def test_binarize_option(self):
        data = np.zeros((20, 20), dtype=np.uint8)
        data[5:15, 5:15] = 200
        data[2, 2] = 200
        element = structuring.make_element("Прямоугольник", 3, 3)
        result, note = morphology.morphology(PixelBuffer(data), "open", element, binarize=True)
        self.assertEqual(set(np.unique(result.data)), {0, 255})
        self.assertEqual(result.data[2, 2, 0], 0)
        self.assertEqual(result.data[10, 10, 0], 255)

    def test_borders_for_symmetric_and_asymmetric_elements(self):
        plane = random_plane(16, 16)
        symmetric = structuring.make_element("Эллипс", 7, 7)
        results = [morphology.erode(plane, symmetric, mode) for mode in (CLAMP, REFLECT, NEUTRAL)]
        self.assertTrue(np.array_equal(results[0], results[1]))
        self.assertTrue(np.array_equal(results[0], results[2]))
        asymmetric = structuring.parse_matrix("1 1 1 1 1 1 1 0 0 0 0")
        clamp = morphology.erode(plane, asymmetric, CLAMP)
        reflect = morphology.erode(plane, asymmetric, REFLECT)
        neutral = morphology.erode(plane, asymmetric, NEUTRAL)
        self.assertTrue(np.array_equal(clamp, neutral))
        self.assertFalse(np.array_equal(clamp, reflect))

    def test_matrix_errors(self):
        for bad in ("", "1 2", "1 1\n1", "0 0"):
            with self.assertRaises(ValueError):
                structuring.parse_matrix(bad)


class ThresholdTests(unittest.TestCase):
    def test_otsu_matches_bruteforce(self):
        for _ in range(8):
            plane = np.clip(RNG.normal(100, 40, (30, 30)), 0, 255).astype(np.uint8)
            plane[:10] = np.clip(RNG.normal(200, 15, (10, 30)), 0, 255).astype(np.uint8)
            self.assertEqual(threshold.otsu_threshold(histogram.histogram(plane)), reference.naive_otsu(plane))

    def test_otsu_two_levels(self):
        plane = np.zeros((10, 10), dtype=np.uint8)
        plane[:, 5:] = 200
        self.assertTrue(0 <= threshold.otsu_threshold(histogram.histogram(plane)) < 200)


class PointwiseTests(unittest.TestCase):
    def test_luts(self):
        levels = np.arange(256)
        self.assertTrue(np.array_equal(pointwise.negative_lut(), 255 - levels))
        self.assertEqual(pointwise.brightness_lut(50)[220], 255)
        self.assertEqual(pointwise.brightness_lut(-50)[20], 0)
        self.assertEqual(pointwise.gamma_lut(1.0).tolist(), levels.tolist())
        self.assertEqual(pointwise.gamma_lut(2.0)[128], round(255 * (128 / 255) ** 2))
        self.assertEqual(pointwise.log_lut(1.0)[255], 255)
        self.assertEqual(pointwise.exp_lut(2.0)[255], 255)
        self.assertEqual(pointwise.exp_lut(2.0)[0], 0)
        self.assertEqual(pointwise.threshold_lut(100)[100], 0)
        self.assertEqual(pointwise.threshold_lut(100)[101], 255)
        self.assertEqual(sorted(set(pointwise.posterize_lut(4).tolist())), [0, 85, 170, 255])

    def test_apply_lut_per_pixel(self):
        data = RNG.integers(0, 256, size=(15, 18, 3), dtype=np.uint8)
        lut = pointwise.gamma_lut(0.6)
        result = pointwise.apply_lut(PixelBuffer(data), lut)
        for y in range(15):
            for x in range(18):
                for c in range(3):
                    self.assertEqual(result.data[y, x, c], lut[data[y, x, c]])

    def test_combine(self):
        a = PixelBuffer(random_plane(10, 12))
        b = PixelBuffer(random_plane(10, 12))
        x = a.data.astype(int)
        y = b.data.astype(int)
        self.assertTrue(np.array_equal(pointwise.combine(a, b, "sum").data, np.clip(x + y, 0, 255)))
        self.assertTrue(np.array_equal(pointwise.combine(a, b, "difference").data, np.clip(x - y, 0, 255)))
        self.assertTrue(np.array_equal(pointwise.combine(a, b, "absdiff").data, np.abs(x - y)))
        self.assertTrue(np.array_equal(pointwise.combine(a, b, "xor").data, x ^ y))
        small = PixelBuffer(random_plane(4, 5))
        self.assertEqual(pointwise.combine(a, small, "max").data.shape, a.data.shape)


class ContrastTests(unittest.TestCase):
    def test_stretch(self):
        data = RNG.integers(90, 151, size=(40, 40), dtype=np.uint8)
        data[0, 0] = 90
        data[0, 1] = 150
        result, _ = contrast.linear_contrast(PixelBuffer(data), "all")
        self.assertEqual(result.data.min(), 0)
        self.assertEqual(result.data.max(), 255)
        order = np.argsort(data.ravel(), kind="stable")
        self.assertTrue((np.diff(result.data.ravel()[order].astype(int)) >= 0).all())

    def test_percentile_clipping(self):
        data = np.full((100, 100), 128, dtype=np.uint8)
        data[0, 0] = 0
        data[0, 1] = 255
        plain = contrast.percentile_bounds(histogram.histogram(data), 0)
        clipped = contrast.percentile_bounds(histogram.histogram(data), 1)
        self.assertEqual(plain, (0, 255))
        self.assertEqual(clipped, (128, 128))

    def test_channels_vs_all(self):
        data = np.zeros((20, 20, 3), dtype=np.uint8)
        data[:, :, 0] = RNG.integers(50, 100, (20, 20))
        data[:, :, 1] = RNG.integers(10, 200, (20, 20))
        data[:, :, 2] = RNG.integers(100, 120, (20, 20))
        per_channel, _ = contrast.linear_contrast(PixelBuffer(data), "channels")
        for c in range(3):
            self.assertEqual(per_channel.plane(c).min(), 0)
            self.assertEqual(per_channel.plane(c).max(), 255)
        common, _ = contrast.linear_contrast(PixelBuffer(data), "all")
        self.assertEqual(common.data.min(), 0)
        self.assertEqual(common.data.max(), 255)

    def test_value_mode_keeps_hue(self):
        data = np.zeros((6, 6, 3), dtype=np.uint8)
        data[:, :] = (40, 20, 10)
        data[0, 0] = (80, 40, 20)
        result, _ = contrast.linear_contrast(PixelBuffer(data), "value")
        self.assertEqual(result.data[0, 0].tolist(), [255, 128, 64])
        self.assertEqual(result.data[3, 3].tolist(), [0, 0, 0])

    def test_equalization_matches_naive(self):
        plane = random_plane(24, 24) // 3 + 40
        result = contrast.equalize(PixelBuffer(plane), "rgb")
        self.assertTrue(np.array_equal(result.plane(0), reference.naive_equalize(plane)))

    def test_equalization_flat(self):
        flat = np.full((8, 8), 77, dtype=np.uint8)
        self.assertTrue(np.array_equal(contrast.equalize(PixelBuffer(flat), "rgb").plane(0), flat))

    def test_clahe_properties(self):
        base = np.tile(np.linspace(80, 120, 64), (64, 1)).astype(np.uint8)
        base = base + RNG.integers(0, 6, base.shape).astype(np.uint8)
        gentle = histogram.clahe_plane(base, 4, 4, 1.0)
        strong = histogram.clahe_plane(base, 4, 4, 8.0)
        self.assertEqual(gentle.shape, base.shape)
        self.assertGreater(int(strong.max()) - int(strong.min()), int(gentle.max()) - int(gentle.min()))
        self.assertGreater(int(gentle.max()) - int(gentle.min()), int(base.max()) - int(base.min()))

    def test_clahe_single_tile_is_clipped_equalization(self):
        plane = random_plane(32, 32)
        result = histogram.clahe_plane(plane, 1, 1, 1000.0)
        table = np.cumsum(histogram.histogram(plane)) * 255.0 / plane.size
        expected = np.clip(np.rint(table[plane]), 0, 255).astype(np.uint8)
        self.assertTrue(np.array_equal(result, expected))

    def test_clahe_threads_equal(self):
        plane = random_plane(200, 150)
        one = histogram.clahe_plane(plane, 8, 8, 3.0, workers=1)
        many = histogram.clahe_plane(plane, 8, 8, 3.0, workers=8)
        self.assertTrue(np.array_equal(one, many))

    def test_clip_histogram_keeps_total(self):
        hist = RNG.integers(0, 500, 256)
        clipped = histogram.clip_histogram(hist, 100)
        self.assertEqual(int(clipped.sum()), int(hist.sum()))


class GrayTests(unittest.TestCase):
    def test_gray_weights(self):
        buffer = PixelBuffer(np.array([[[255, 0, 0], [0, 255, 0], [0, 0, 255]]], dtype=np.uint8))
        self.assertEqual(to_gray(buffer).data[:, :, 0].tolist(), [[76, 150, 29]])


if __name__ == "__main__":
    unittest.main(verbosity=2)
