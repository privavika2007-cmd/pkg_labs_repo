import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "images")
RNG = np.random.default_rng(2026)
WIDTH, HEIGHT = 640, 480


def scene():
    ys, xs = np.mgrid[0:HEIGHT, 0:WIDTH].astype(np.float64)
    image = np.zeros((HEIGHT, WIDTH, 3))
    sky = ys / HEIGHT
    image[:, :, 0] = 90 + 110 * sky
    image[:, :, 1] = 150 + 70 * sky
    image[:, :, 2] = 235 - 20 * sky
    sun = (xs - 500) ** 2 + (ys - 90) ** 2 < 45 ** 2
    image[sun] = (255, 236, 150)
    ridge = 250 + 40 * np.sin(xs / 70.0) + 25 * np.sin(xs / 23.0 + 1.0)
    mountain = ys > ridge
    image[mountain, 0] = 95 + 20 * np.sin(xs[mountain] / 40.0)
    image[mountain, 1] = 105
    image[mountain, 2] = 120
    ground = ys > 330
    shade = 0.5 + 0.5 * (ys[ground] - 330) / 150
    image[ground, 0] = 60 * shade
    image[ground, 1] = 150 * shade
    image[ground, 2] = 55 * shade
    image[300:400, 120:260] = (200, 170, 130)
    for row in range(250, 300):
        half = (row - 250) * 1.6 + 5
        left = max(120, int(190 - half))
        right = min(260, int(190 + half))
        image[row, left:right] = (170, 55, 45)
    image[335:400, 170:210] = (90, 55, 30)
    image[320:350, 130:160] = (170, 210, 235)
    image[320:350, 225:255] = (170, 210, 235)
    trees = RNG.integers(300, 600, 6)
    for x in trees:
        image[360:410, x - 4:x + 4] = (70, 45, 25)
        crown = (xs - x) ** 2 + (ys - 335) ** 2 < 32 ** 2
        image[crown] = (25, 95, 35)
    return image


def save(name, array):
    array = np.clip(np.rint(array), 0, 255).astype(np.uint8)
    Image.fromarray(array).save(os.path.join(OUT, name))


def squeeze(image, low, high, noise=2.0):
    scaled = low + image / 255.0 * (high - low)
    return scaled + RNG.normal(0, noise, image.shape)


def font(size):
    return ImageFont.load_default(size=size)


def text_page(background, ink, lines, size=34):
    page = Image.new("L", (WIDTH, HEIGHT), background)
    draw = ImageDraw.Draw(page)
    y = 30
    for line in lines:
        draw.text((30, y), line, fill=ink, font=font(size))
        y += size + 22
    return np.asarray(page, dtype=np.float64)


LINES = [
    "MORPHOLOGY OF IMAGES",
    "Erosion removes small bright",
    "details, dilation grows objects.",
    "Opening, closing, gradient,",
    "Top-Hat and Black-Hat.",
    "Variant 16 / Group 10A",
]


def blobs(count, radius_range, fill, background, specks):
    ys, xs = np.mgrid[0:HEIGHT, 0:WIDTH]
    image = np.full((HEIGHT, WIDTH), background, dtype=np.float64)
    for _ in range(count):
        cx = RNG.integers(40, WIDTH - 40)
        cy = RNG.integers(40, HEIGHT - 40)
        radius = RNG.integers(*radius_range)
        image[(xs - cx) ** 2 + (ys - cy) ** 2 < radius ** 2] = fill
    for _ in range(specks):
        x = RNG.integers(2, WIDTH - 2)
        y = RNG.integers(2, HEIGHT - 2)
        image[y:y + 2, x:x + 2] = fill
    return image


def shapes_with_noise():
    image = Image.new("L", (WIDTH, HEIGHT), 0)
    draw = ImageDraw.Draw(image)
    draw.ellipse((60, 60, 260, 260), fill=255)
    draw.rectangle((320, 80, 560, 220), fill=255)
    draw.polygon([(100, 420), (230, 300), (360, 420)], fill=255)
    draw.rectangle((420, 300, 590, 440), fill=255)
    array = np.asarray(image, dtype=np.float64)
    total = WIDTH * HEIGHT
    pepper = RNG.choice(total, int(total * 0.03), replace=False)
    salt = RNG.choice(total, int(total * 0.03), replace=False)
    flat = array.ravel().copy()
    flat[pepper] = 0
    flat[salt] = 255
    return flat.reshape(HEIGHT, WIDTH)


def broken_lines():
    image = Image.new("L", (WIDTH, HEIGHT), 0)
    draw = ImageDraw.Draw(image)
    for y in range(60, HEIGHT, 90):
        draw.line((30, y, WIDTH - 30, y), fill=255, width=6)
    for x in range(80, WIDTH, 120):
        draw.line((x, 30, x, HEIGHT - 30), fill=255, width=6)
    array = np.asarray(image, dtype=np.float64)
    for _ in range(90):
        x = RNG.integers(20, WIDTH - 30)
        y = RNG.integers(20, HEIGHT - 30)
        array[y:y + 7, x:x + 7] = 0
    return array


def traces():
    image = Image.new("L", (WIDTH, HEIGHT), 20)
    draw = ImageDraw.Draw(image)
    for y in (80, 190, 300, 410):
        draw.line((20, y, WIDTH - 20, y), fill=230, width=14)
    for x in (110, 300, 500):
        draw.line((x, 30, x, HEIGHT - 30), fill=230, width=14)
    draw.ellipse((50, 140, 90, 180), fill=230)
    array = np.asarray(image, dtype=np.float64)
    for _ in range(70):
        x = RNG.integers(20, WIDTH - 30)
        y = RNG.integers(20, HEIGHT - 30)
        if array[y, x] > 100:
            array[y:y + 4, x:x + 4] = 20
        else:
            array[y:y + 3, x:x + 3] = 230
    return array


def moving_frames():
    ys, xs = np.mgrid[0:HEIGHT, 0:WIDTH]
    base = scene().mean(axis=2)
    first = base.copy()
    second = base.copy()
    first[(xs - 200) ** 2 + (ys - 430) ** 2 < 30 ** 2] = 255
    second[(xs - 330) ** 2 + (ys - 430) ** 2 < 30 ** 2] = 255
    return first, second


def mask_circle():
    ys, xs = np.mgrid[0:HEIGHT, 0:WIDTH]
    return np.where((xs - 320) ** 2 + (ys - 240) ** 2 < 200 ** 2, 255, 0).astype(np.float64)


def main():
    os.makedirs(OUT, exist_ok=True)
    base = scene()
    save("01_low_contrast_scene.png", squeeze(base, 100, 160))
    save("02_dark_scene.png", 255 * (base / 255.0) ** 2.6 * 0.55 + RNG.normal(0, 1.5, base.shape))
    save("03_overexposed_scene.png", 255 - 255 * ((255 - base) / 255.0) ** 2.2 * 0.5 + RNG.normal(0, 1.5, base.shape))
    save("04_low_contrast_text.png", text_page(135, 105, LINES) + RNG.normal(0, 2, (HEIGHT, WIDTH)))
    ys, xs = np.mgrid[0:HEIGHT, 0:WIDTH]
    light = 245 - 190 * (xs / WIDTH) ** 1.2
    page = text_page(255, 0, LINES) / 255.0
    save("05_text_uneven_light.png", np.where(page < 0.5, light * 0.35, light) + RNG.normal(0, 2, (HEIGHT, WIDTH)))
    save("06_salt_pepper_shapes.png", shapes_with_noise())
    save("07_cells_and_specks.png", blobs(16, (5, 30), 215, 40, 450) + RNG.normal(0, 3, (HEIGHT, WIDTH)))
    save("08_broken_lines.png", broken_lines())
    save("09_traces_with_defects.png", traces())
    ramp = np.tile(np.linspace(0, 255, 256), (120, 1))
    save("10_gradient_ramp.png", ramp)
    save("11_color_noisy_scene.png", base + RNG.normal(0, 22, base.shape))
    first, second = moving_frames()
    save("12_frame_a.png", first)
    save("13_frame_b.png", second)
    save("14_mask_circle.png", mask_circle())
    dull = squeeze(base, 60, 110, 1.5)
    dull[..., 0] *= 1.35
    save("15_low_contrast_color_cast.png", dull)


if __name__ == "__main__":
    main()
