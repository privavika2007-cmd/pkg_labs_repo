import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image, ImageDraw

LAB = os.path.expanduser("~/Desktop/Вика_ЛР3_Вариант16/ImageLab")
sys.path.insert(0, LAB)
from algorithms import contrast, histogram as H, morphology, pointwise, structuring, threshold
from algorithms.colorspace import to_gray
from memory.buffer import PixelBuffer

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fig")
os.makedirs(OUT, exist_ok=True)
IMG = os.path.join(LAB, "images")
METRICS = {}
plt.rcParams.update({"font.size": 8, "axes.titlesize": 8.5, "figure.dpi": 150})


def load(name):
    with Image.open(os.path.join(IMG, name)) as image:
        image = image.convert("L") if image.mode in ("L", "1") else image.convert("RGB")
        return PixelBuffer(np.asarray(image))


def gray_plane(buffer):
    return to_gray(buffer).plane(0)


def stats(buffer):
    g = gray_plane(buffer)
    hist = H.histogram(g)
    p = hist[hist > 0] / hist.sum()
    return {
        "min": int(g.min()), "max": int(g.max()), "range": int(g.max()) - int(g.min()),
        "mean": round(float(g.mean()), 1), "std": round(float(g.std()), 1),
        "levels": int((hist > 0).sum()), "entropy": round(float(-(p * np.log2(p)).sum()), 2),
    }


def show(ax, buffer, title):
    ax.imshow(buffer.to_array(), cmap="gray", vmin=0, vmax=255, interpolation="nearest" if buffer.width < 200 else "bilinear")
    ax.set_title(title)
    ax.axis("off")


def draw_hist(ax, buffer, title=None):
    gray = H.histogram(gray_plane(buffer))
    ax.fill_between(range(256), gray, color="#9aa0a6", step="mid")
    if buffer.is_color:
        for c, col in enumerate(("#d9382b", "#2f9e44", "#2b6fd9")):
            ax.plot(H.histogram(buffer.plane(c)), color=col, lw=0.7)
    ax.set_xlim(0, 255)
    ax.set_yticks([])
    ax.set_xticks([0, 64, 128, 192, 255])
    if title:
        ax.set_title(title)


def sheet(name, items, hist=True, cols=None, width=7.0, note=None):
    cols = cols or len(items)
    rows = -(-len(items) // cols)
    per = 2 if hist else 1
    height_ratios = ([3.2, 1.2] if hist else [3.2]) * rows
    fig, axes = plt.subplots(rows * per, cols, figsize=(width, (width / cols) * rows * (1.15 if hist else 0.85)),
                             gridspec_kw={"height_ratios": height_ratios}, squeeze=False, layout="constrained")
    for ax in axes.ravel():
        ax.axis("off")
    for index, (title, buffer) in enumerate(items):
        r, c = divmod(index, cols)
        show(axes[r * per][c], buffer, title)
        if hist:
            axes[r * per + 1][c].axis("on")
            draw_hist(axes[r * per + 1][c], buffer)
    fig.savefig(os.path.join(OUT, name + ".png"))
    plt.close(fig)


scene = load("01_low_contrast_scene.png")
dark = load("02_dark_scene.png")
bright = load("03_overexposed_scene.png")
lowtext = load("04_low_contrast_text.png")
uneven = load("05_text_uneven_light.png")
shapes = load("06_salt_pepper_shapes.png")
cells = load("07_cells_and_specks.png")
lines = load("08_broken_lines.png")
traces = load("09_traces_with_defects.png")
noisy = load("11_color_noisy_scene.png")
framea = load("12_frame_a.png")
frameb = load("13_frame_b.png")
mask = load("14_mask_circle.png")
cast = load("15_low_contrast_color_cast.png")

names = sorted(os.listdir(IMG))
fig, axes = plt.subplots(3, 5, figsize=(7.0, 4.6))
for ax, name in zip(axes.ravel(), names):
    b = load(name)
    ax.imshow(b.to_array(), cmap="gray", vmin=0, vmax=255)
    ax.set_title(name[:-4].replace("_", " "), fontsize=6.5)
    ax.axis("off")
fig.tight_layout(pad=0.4)
fig.savefig(os.path.join(OUT, "base.png"))
plt.close(fig)

lin_all, note_all = contrast.linear_contrast(scene, "all")
lin_clip, note_clip = contrast.linear_contrast(scene, "all", 1.0)
sheet("linear_basic", [("Исходное", scene), ("Растяжение [min; max]", lin_all), ("Растяжение с отсечением 1 %", lin_clip)])
METRICS["lin_scene"] = {"src": stats(scene), "all": stats(lin_all), "clip": stats(lin_clip), "note_all": note_all, "note_clip": note_clip}

c_all, n1 = contrast.linear_contrast(cast, "all", 0.5)
c_ch, n2 = contrast.linear_contrast(cast, "channels", 0.5)
c_v, n3 = contrast.linear_contrast(cast, "value", 0.5)
sheet("linear_modes", [("Исходное", cast), ("Общее окно", c_all), ("По каналам RGB", c_ch), ("По яркости V", c_v)], width=7.4)
METRICS["modes"] = {k: stats(v) for k, v in {"src": cast, "all": c_all, "ch": c_ch, "v": c_v}.items()}
METRICS["modes_notes"] = [n1, n2, n3]

def mean_rgb(b):
    return [round(float(b.plane(c).mean()), 1) for c in range(3)]
METRICS["modes_rgb"] = {k: mean_rgb(v) for k, v in {"src": cast, "all": c_all, "ch": c_ch, "v": c_v}.items()}

eq_rgb = contrast.equalize(scene, "rgb")
eq_v = contrast.equalize(scene, "value")
cl = contrast.clahe(scene, 8, 3.0)
sheet("lin_vs_eq", [("Исходное", scene), ("Линейное, 1 %", lin_clip), ("Эквализация RGB", eq_rgb), ("Эквализация V", eq_v), ("CLAHE 8×8, клип 3", cl)], cols=5, width=8.6)
METRICS["lin_vs_eq"] = {k: stats(v) for k, v in {"src": scene, "lin": lin_clip, "eqrgb": eq_rgb, "eqv": eq_v, "clahe": cl}.items()}
METRICS["lin_vs_eq_rgb"] = {k: mean_rgb(v) for k, v in {"src": scene, "lin": lin_clip, "eqrgb": eq_rgb, "eqv": eq_v, "clahe": cl}.items()}

noisy_g = noisy
eq_n = contrast.equalize(noisy_g, "value")
cl_n = contrast.clahe(noisy_g, 8, 2.0)
low_text_lin, _ = contrast.linear_contrast(lowtext, "all", 0.5)
low_text_eq = contrast.equalize(lowtext, "rgb")
low_text_cl = contrast.clahe(lowtext, 4, 8.0)
sheet("text_contrast", [("Исходное", lowtext), ("Линейное, 0,5 %", low_text_lin), ("Эквализация", low_text_eq), ("CLAHE 4×4, клип 8", low_text_cl)], width=7.4)
METRICS["text"] = {k: stats(v) for k, v in {"src": lowtext, "lin": low_text_lin, "eq": low_text_eq, "clahe": low_text_cl}.items()}

g05 = pointwise.apply_lut(dark, pointwise.gamma_lut(0.45))
l05 = pointwise.apply_lut(dark, pointwise.log_lut(4.0))
n04 = pointwise.apply_lut(scene, pointwise.negative_lut())
g22 = pointwise.apply_lut(bright, pointwise.gamma_lut(2.2))
e22 = pointwise.apply_lut(bright, pointwise.exp_lut(2.0))
sheet("point_dark", [("Тёмное исходное", dark), ("Гамма γ = 0,45", g05), ("Логарифм c = 4", l05)], width=7.0)
sheet("point_bright", [("Пересвеченное исходное", bright), ("Гамма γ = 2,2", g22), ("Экспонента c = 2", e22)], width=7.0)
METRICS["point"] = {k: stats(v) for k, v in {"dark": dark, "g05": g05, "l05": l05, "bright": bright, "g22": g22, "e22": e22}.items()}

post = pointwise.apply_lut(scene, pointwise.posterize_lut(4))
sol = pointwise.apply_lut(lin_clip, pointwise.solarize_lut(128))
thr = pointwise.apply_lut(lin_clip, pointwise.threshold_lut(128))
sheet("point_other", [("Негатив", n04), ("Постеризация, 4 уровня", pointwise.apply_lut(lin_clip, pointwise.posterize_lut(4))), ("Соляризация T = 128", sol), ("Порог T = 128", thr)], hist=False, width=7.4)

diff = pointwise.combine(framea, frameb, "absdiff")
prod = pointwise.combine(framea, mask, "product")
blend = pointwise.combine(framea, frameb, "blend", 0.5)
sheet("pair", [("Кадр A", framea), ("Кадр B", frameb), ("|A - B|", diff), ("A · маска", prod), ("0,5·A + 0,5·B", blend)], hist=False, cols=5, width=8.6)

fig, axes = plt.subplots(1, 7, figsize=(7.4, 1.5))
for ax, (title, element) in zip(axes, [
    ("Прямоугольник 5×3", structuring.make_element("Прямоугольник", 5, 3)),
    ("Эллипс 9×9", structuring.make_element("Эллипс", 9, 9)),
    ("Крест 7×7", structuring.make_element("Крест", 7, 7)),
    ("Ромб 7×7", structuring.make_element("Ромб", 7, 7)),
    ("Гориз. линия 9", structuring.make_element("Горизонтальная линия", 9, 1)),
    ("Диагональ 7", structuring.make_element("Диагональ \\", 7, 7)),
    ("Своя матрица", structuring.parse_matrix("1 0 1 1/0 1 0 0/1 1 0 1")),
]):
    ax.imshow(element, cmap="gray_r", vmin=0, vmax=1)
    ax.set_title(title, fontsize=6.5)
    ax.set_xticks([]); ax.set_yticks([])
fig.tight_layout(pad=0.3)
fig.savefig(os.path.join(OUT, "elements.png"))
plt.close(fig)

truth_img = Image.new("L", (640, 480), 0)
d = ImageDraw.Draw(truth_img)
d.ellipse((60, 60, 260, 260), fill=255)
d.rectangle((320, 80, 560, 220), fill=255)
d.polygon([(100, 420), (230, 300), (360, 420)], fill=255)
d.rectangle((420, 300, 590, 440), fill=255)
truth = np.asarray(truth_img)
disk5 = structuring.make_element("Эллипс", 5, 5)


def morph(buffer, op, element, border="clamp", iters=1, **kw):
    return morphology.morphology(buffer, op, element, iters, border, **kw)[0]


er = morph(shapes, "erode", disk5)
di = morph(shapes, "dilate", disk5)
op = morph(shapes, "open", disk5)
cl_ = morph(shapes, "close", disk5)
oc = morph(op, "close", disk5)
sheet("morph_basic", [("Исходное: шум «соль и перец»", shapes), ("Эрозия", er), ("Дилатация", di), ("Открытие", op), ("Закрытие", cl_), ("Открытие, затем закрытие", oc)], hist=False, cols=3, width=7.0)


def wrong(buffer):
    return int((buffer.plane(0) != truth).sum())


METRICS["shapes"] = {k: wrong(v) for k, v in {"src": shapes, "er": er, "di": di, "op": op, "cl": cl_, "oc": oc}.items()}
METRICS["shapes_total"] = int(truth.size)

smooth = oc
grad = morph(smooth, "gradient", structuring.make_element("Прямоугольник", 3, 3))
inner = morph(smooth, "inner", structuring.make_element("Прямоугольник", 3, 3))
outer = morph(smooth, "outer", structuring.make_element("Прямоугольник", 3, 3))
sheet("gradients", [("Морфологический градиент", grad), ("Внутренний градиент", inner), ("Внешний градиент", outer)], hist=False, width=7.0)
METRICS["gradients"] = {k: int((v.plane(0) > 0).sum()) for k, v in {"grad": grad, "inner": inner, "outer": outer}.items()}

rect15 = structuring.make_element("Прямоугольник", 15, 15)
bh = morph(uneven, "blackhat", rect15, "reflect")
th = morph(uneven, "tophat", rect15, "reflect")
bh_lin, _ = contrast.linear_contrast(bh, "all", 0.0)
t_plain = threshold.otsu_threshold(H.histogram(gray_plane(uneven)))
plain_bin = PixelBuffer(threshold.binarize_plane(uneven.plane(0), t_plain))
t_bh = threshold.otsu_threshold(H.histogram(bh_lin.plane(0)))
bh_bin = PixelBuffer(np.where(bh_lin.plane(0) > t_bh, 255, 0).astype(np.uint8))
inverted_plain = PixelBuffer(255 - plain_bin.data)
sheet("hats", [("Текст на неравномерном фоне", uneven), ("Black-Hat 15×15", bh_lin), ("Оцу по исходному", inverted_plain), ("Оцу после Black-Hat", bh_bin)], hist=False, width=7.4)
METRICS["hats"] = {"t_plain": t_plain, "t_bh": t_bh, "src": stats(uneven), "bh": stats(bh_lin)}

page = Image.new("L", (640, 480), 255)
dr = ImageDraw.Draw(page)
from tests.make_images import LINES, font
y = 30
for line in LINES:
    dr.text((30, y), line, fill=0, font=font(34))
    y += 34 + 22
text_truth = (np.asarray(page) < 128)
METRICS["hats"]["err_plain"] = int((inverted_plain.plane(0).astype(bool) != text_truth).sum())
METRICS["hats"]["err_bh"] = int((bh_bin.plane(0).astype(bool) != text_truth).sum())
METRICS["hats"]["text_pixels"] = int(text_truth.sum())

truth_cells = None
open5 = morph(cells, "open", structuring.make_element("Эллипс", 5, 5))
open9 = morph(cells, "open", structuring.make_element("Эллипс", 9, 9))
open21 = morph(cells, "open", structuring.make_element("Эллипс", 21, 21))
sheet("cells", [("Клетки и пятнышки + шум", cells), ("Открытие, эллипс 5×5", open5), ("Открытие, эллипс 9×9", open9), ("Открытие, эллипс 21×21", open21)], hist=False, width=7.4)
cb, _ = morphology.morphology(cells, "open", structuring.make_element("Эллипс", 1, 1), binarize=True)
def comps(plane):
    mask_ = plane > 127
    seen = np.zeros(mask_.shape, dtype=bool)
    count = 0
    h, w = mask_.shape
    for y0 in range(h):
        for x0 in range(w):
            if mask_[y0, x0] and not seen[y0, x0]:
                count += 1
                stack = [(y0, x0)]
                seen[y0, x0] = True
                while stack:
                    y1, x1 = stack.pop()
                    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        y2, x2 = y1 + dy, x1 + dx
                        if 0 <= y2 < h and 0 <= x2 < w and mask_[y2, x2] and not seen[y2, x2]:
                            seen[y2, x2] = True
                            stack.append((y2, x2))
    return count
def binar(b):
    g = b.plane(0)
    t = threshold.otsu_threshold(H.histogram(g))
    return np.where(g > t, 255, 0).astype(np.uint8)
METRICS["cells"] = {k: comps(binar(v)) for k, v in {"src": cells, "o5": open5, "o9": open9, "o21": open21}.items()}

disk3 = structuring.make_element("Эллипс", 5, 5)
tr_open = morph(traces, "open", disk3)
tr_close = morph(traces, "close", disk3)
tr_both = morph(tr_open, "close", disk3)
sheet("traces", [("Дорожки с дефектами", traces), ("Открытие 5×5", tr_open), ("Закрытие 5×5", tr_close), ("Открытие + закрытие", tr_both)], hist=False, width=7.4)

true_tr = Image.new("L", (640, 480), 20)
dd = ImageDraw.Draw(true_tr)
for yy in (80, 190, 300, 410):
    dd.line((20, yy, 620, yy), fill=230, width=14)
for xx in (110, 300, 500):
    dd.line((xx, 30, xx, 450), fill=230, width=14)
dd.ellipse((50, 140, 90, 180), fill=230)
tt = np.asarray(true_tr) > 125
def terr(b):
    return int(((b.plane(0) > 125) != tt).sum())
METRICS["traces"] = {k: terr(v) for k, v in {"src": traces, "open": tr_open, "close": tr_close, "both": tr_both}.items()}

closed_lines = morph(lines, "close", structuring.make_element("Прямоугольник", 9, 9))
sheet("lines", [("Линии с разрывами", lines), ("Закрытие 9×9", closed_lines)], hist=False, width=5.2)
line_truth = Image.new("L", (640, 480), 0)
ld = ImageDraw.Draw(line_truth)
for yy in range(60, 480, 90):
    ld.line((30, yy, 610, yy), fill=255, width=6)
for xx in range(80, 640, 120):
    ld.line((xx, 30, xx, 450), fill=255, width=6)
lt = np.asarray(line_truth) > 127
METRICS["lines"] = {"src": int(((lines.plane(0) > 127) != lt).sum()), "closed": int(((closed_lines.plane(0) > 127) != lt).sum())}

crop = to_gray(noisy).plane(0)[0:48, 0:48]
crop_buffer = PixelBuffer(crop)
sym = structuring.make_element("Эллипс", 9, 9)
asym = structuring.parse_matrix("1 1 1 1 1 1 1 1 1 0 0 0 0")
res_sym = {b: morph(crop_buffer, "erode", sym, b).plane(0) for b in ("clamp", "reflect", "neutral")}
res_asym = {b: morph(crop_buffer, "erode", asym, b).plane(0) for b in ("clamp", "reflect", "neutral")}
diff_map = np.abs(res_asym["reflect"].astype(int) - res_asym["clamp"].astype(int))
METRICS["borders"] = {
    "sym_clamp_reflect": int((res_sym["clamp"] != res_sym["reflect"]).sum()),
    "sym_clamp_neutral": int((res_sym["clamp"] != res_sym["neutral"]).sum()),
    "asym_clamp_reflect": int((res_asym["clamp"] != res_asym["reflect"]).sum()),
    "asym_clamp_neutral": int((res_asym["clamp"] != res_asym["neutral"]).sum()),
    "asym_reflect_neutral": int((res_asym["reflect"] != res_asym["neutral"]).sum()),
    "max_diff": int(diff_map.max()),
}
fig, axes = plt.subplots(1, 4, figsize=(7.0, 2.1), layout="constrained")
panels = [("Фрагмент 48×48", crop, 0, 255), ("Clamp", res_asym["clamp"], 0, 255),
          ("Reflect", res_asym["reflect"], 0, 255), ("|Reflect - Clamp|", diff_map, 0, max(1, diff_map.max()))]
for ax, (title, arr, lo, hi) in zip(axes, panels):
    ax.imshow(arr, cmap="gray", vmin=lo, vmax=hi, interpolation="nearest")
    ax.set_title(title)
    ax.axis("off")
fig.savefig(os.path.join(OUT, "borders.png"))
plt.close(fig)

hist_row = [("Исходное", cast), ("Общее окно", c_all), ("По каналам RGB", c_ch)]
fig, axes = plt.subplots(1, 3, figsize=(7.4, 1.9))
for ax, (title, b) in zip(axes, hist_row):
    ax.axis("on")
    draw_hist(ax, b, title)
fig.tight_layout(pad=0.4)
fig.savefig(os.path.join(OUT, "cast_hist.png"))
plt.close(fig)

json.dump(METRICS, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "metrics.json"), "w"), ensure_ascii=False, indent=1)
print(json.dumps(METRICS, ensure_ascii=False, indent=1))
