import numpy as np

SHAPES = [
    "Прямоугольник",
    "Эллипс",
    "Крест",
    "Ромб",
    "Горизонтальная линия",
    "Вертикальная линия",
    "Диагональ \\",
    "Диагональ /",
    "Своя матрица",
]


def make_element(shape, width, height, matrix_text=""):
    width = max(1, int(width))
    height = max(1, int(height))
    ys, xs = np.mgrid[0:height, 0:width]
    cy = (height - 1) / 2.0
    cx = (width - 1) / 2.0
    if shape == "Прямоугольник":
        return np.ones((height, width), dtype=bool)
    if shape == "Эллипс":
        return ((xs - cx) / (width / 2.0)) ** 2 + ((ys - cy) / (height / 2.0)) ** 2 <= 1.0
    if shape == "Крест":
        return (xs == int(cx)) | (ys == int(cy))
    if shape == "Ромб":
        rx = max(cx, 0.5)
        ry = max(cy, 0.5)
        return np.abs(xs - cx) / rx + np.abs(ys - cy) / ry <= 1.0 + 1e-9
    if shape == "Горизонтальная линия":
        return np.ones((1, width), dtype=bool)
    if shape == "Вертикальная линия":
        return np.ones((height, 1), dtype=bool)
    size = max(width, height)
    if shape == "Диагональ \\":
        return np.eye(size, dtype=bool)
    if shape == "Диагональ /":
        return np.eye(size, dtype=bool)[:, ::-1]
    return parse_matrix(matrix_text)


def parse_matrix(text):
    rows = []
    for line in text.replace("/", "\n").splitlines():
        line = line.replace(",", " ").replace(";", " ").strip()
        if not line:
            continue
        cells = line.split() if " " in line else list(line)
        if any(cell not in ("0", "1") for cell in cells):
            raise ValueError("матрица должна состоять из 0 и 1")
        rows.append([cell == "1" for cell in cells])
    if not rows:
        raise ValueError("матрица структурирующего элемента пуста")
    if len({len(row) for row in rows}) != 1:
        raise ValueError("строки матрицы должны быть одной длины")
    element = np.array(rows, dtype=bool)
    if not element.any():
        raise ValueError("в матрице нет ни одной единицы")
    return element


def element_runs(element):
    runs = []
    for row in range(element.shape[0]):
        column = 0
        width = element.shape[1]
        while column < width:
            if element[row, column]:
                start = column
                while column < width and element[row, column]:
                    column += 1
                runs.append((row, start, column - start))
            else:
                column += 1
    return runs


def element_text(element):
    return "\n".join("".join("█" if cell else "·" for cell in row) for row in element)
