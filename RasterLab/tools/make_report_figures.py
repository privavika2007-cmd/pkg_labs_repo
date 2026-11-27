import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from matplotlib.figure import Figure

from raster.engine import (LINE_ALGORITHMS, bresenham_circle, bresenham_line, dda_line,
                           pitteway_ellipse, wu_line)
from raster.grid import VirtualGrid
from ui.painter import GridPainter, load_font

HERE = os.path.dirname(os.path.abspath(__file__))
FIG = os.path.join(HERE, "fig")
os.makedirs(FIG, exist_ok=True)
painter = GridPainter(13)
title_font = load_font(20)


def render(draw, scale, center, size, shape=None):
    grid = VirtualGrid(60, 60)
    draw(grid)
    return painter.render(np.array(grid.cells), scale, center[0], center[1], size[0], size[1], shape)


def titled(image, text):
    result = Image.new("RGB", (image.width, image.height + 34), "white")
    result.paste(image, (0, 34))
    ImageDraw.Draw(result).text((image.width / 2, 17), text, fill=(0, 0, 0), font=title_font, anchor="mm")
    return result


def sheet(images, columns, name):
    width = max(image.width for image in images)
    height = max(image.height for image in images)
    rows = (len(images) + columns - 1) // columns
    result = Image.new("RGB", (columns * width + (columns - 1) * 16, rows * height + (rows - 1) * 16), "white")
    for index, image in enumerate(images):
        result.paste(image, ((index % columns) * (width + 16), (index // columns) * (height + 16)))
    result.save(os.path.join(FIG, name + ".png"))


def algorithms_figure():
    images = []
    for name, draw in LINE_ALGORITHMS.items():
        image = render(lambda grid: draw(grid, 0, 0, 8, 3), 46, (4, 1.5), (520, 300), ("line", 0, 0, 8, 3))
        images.append(titled(image, name))
    images.append(titled(render(lambda grid: bresenham_circle(grid, 0, 0, 7), 20, (0, 0), (520, 340),
                                ("ellipse", 0, 0, 7, 7)), "Брезенхем (окружность), R = 7"))
    sheet(images[:3], 3, "lines_a")
    sheet(images[3:5] + images[5:], 3, "lines_b")


def ellipse_figure():
    full = render(lambda grid: pitteway_ellipse(grid, 0, 0, 10, 6), 18, (0, 0), (480, 320), ("ellipse", 0, 0, 10, 6))
    arc = render(lambda grid: pitteway_ellipse(grid, 0, 0, 10, 6, None, 0, 135), 18, (0, 0), (480, 320))
    sheet([titled(full, "Эллипс a = 10, b = 6"), titled(arc, "Дуга от 0° до 135°")], 2, "ellipse")


def octants_figure():
    ends = [(12, 5), (5, 12), (-5, 12), (-12, 5), (-12, -5), (-5, -12), (5, -12), (12, -5)]

    def sun(draw):
        def go(grid):
            for x2, y2 in ends:
                draw(grid, 0, 0, x2, y2)
        return go

    left = render(sun(bresenham_line), 17, (0, 0), (470, 470))
    right = render(sun(dda_line), 17, (0, 0), (470, 470))
    sheet([titled(left, "Брезенхем: 8 октантов"), titled(right, "ЦДА: те же отрезки")], 2, "octants")


def wu_figure():
    plain = render(lambda grid: bresenham_line(grid, 0, 0, 20, 7), 26, (10, 3.5), (600, 260), ("line", 0, 0, 20, 7))
    smooth = render(lambda grid: wu_line(grid, 0, 0, 20, 7), 26, (10, 3.5), (600, 260), ("line", 0, 0, 20, 7))
    sheet([titled(plain, "Брезенхем: ступеньки"), titled(smooth, "Ву: яркость по дробной части")], 1, "wu")


def binding_figure():
    def cells(grid):
        grid.set_pixel(0, 0)
        grid.set_pixel(2, 1)
        grid.set_pixel(-1, 2, 0.5)
    image = render(cells, 70, (0.5, 0.8), (520, 380))
    sheet([image], 1, "binding")


def charts():
    data = json.load(open(os.path.join(HERE, "benchmark_result.json"), encoding="utf-8"))
    colors = ("#c0392b", "#e67e22", "#1f4e79", "#27ae60", "#8e44ad")
    figure = Figure(figsize=(8, 4.6), dpi=150)
    axes = figure.add_subplot()
    for color, (name, entry) in zip(colors, data["lines"].items()):
        axes.plot([0] + [c for c, s in entry["marks"]], [0] + [s for c, s in entry["marks"]],
                  marker="o", markersize=3, color=color, label=name)
    axes.set_xlabel("количество отрезков")
    axes.set_ylabel("суммарное время, с")
    axes.grid(alpha=0.3)
    axes.legend()
    figure.tight_layout()
    figure.savefig(os.path.join(FIG, "bench_count.png"))

    figure = Figure(figsize=(8, 4.6), dpi=150)
    axes = figure.add_subplot()
    for color, (name, points) in zip(colors, data["lengths"].items()):
        axes.plot([l for l, v in points], [v for l, v in points], marker="o", markersize=3, color=color, label=name)
    axes.set_xlabel("длина отрезка, пикселей")
    axes.set_ylabel("время одного отрезка, мкс")
    axes.grid(alpha=0.3)
    axes.legend()
    figure.tight_layout()
    figure.savefig(os.path.join(FIG, "bench_length.png"))

    figure = Figure(figsize=(8, 4.0), dpi=150)
    axes = figure.add_subplot()
    for color, (name, entry) in zip(("#16a085", "#7f8c8d"), data["circles"].items()):
        axes.plot([0] + [c for c, s in entry["marks"]], [0] + [s for c, s in entry["marks"]],
                  marker="o", markersize=3, color=color, label=name)
    axes.set_xlabel("количество окружностей")
    axes.set_ylabel("суммарное время, с")
    axes.grid(alpha=0.3)
    axes.legend()
    figure.tight_layout()
    figure.savefig(os.path.join(FIG, "bench_circles.png"))

    names = ["Пошаговый", "ЦДА", "Брезенхем (отрезок)", "Кастл-Питвей (отрезок)", "Ву (сглаживание)"]
    with_grid = [data["lines"][n]["time"] for n in names]
    without = [data["arithmetic"][n] for n in names]
    figure = Figure(figsize=(8, 4.2), dpi=150)
    axes = figure.add_subplot()
    positions = np.arange(len(names))
    axes.bar(positions - 0.2, with_grid, 0.4, label="с записью в VirtualGrid", color="#1f4e79")
    axes.bar(positions + 0.2, without, 0.4, label="только вычисления (пустой set_pixel)", color="#e67e22")
    axes.set_xticks(positions)
    axes.set_xticklabels(["Пошаговый", "ЦДА", "Брезенхем", "Кастл-Питвей", "Ву"])
    axes.set_ylabel("время на 100 000 отрезков, с")
    axes.grid(alpha=0.3, axis="y")
    axes.legend()
    figure.tight_layout()
    figure.savefig(os.path.join(FIG, "bench_split.png"))


if __name__ == "__main__":
    algorithms_figure()
    ellipse_figure()
    octants_figure()
    wu_figure()
    binding_figure()
    charts()
    print("ok")
