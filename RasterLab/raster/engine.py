import math


def _directions(x1, y1, x2, y2):
    dx = abs(x2 - x1)
    dy = abs(y2 - y1)
    sx = 1 if x2 >= x1 else -1
    sy = 1 if y2 >= y1 else -1
    if dx >= dy:
        return dx, dy, sx, 0, 0, sy
    return dy, dx, 0, sy, sx, 0


def step_line(target, x1, y1, x2, y2, trace=None):
    dx = x2 - x1
    dy = y2 - y1
    if dx == 0 and dy == 0:
        target.set_pixel(x1, y1, 1.0)
        if trace is not None:
            trace.append({"шаг": 0, "x": x1, "y точное": y1, "пиксель": (x1, y1)})
        return
    if abs(dx) >= abs(dy):
        k = dy / dx
        b = y1 - k * x1
        step = 1 if dx > 0 else -1
        for index, x in enumerate(range(x1, x2 + step, step)):
            y = k * x + b
            pixel_y = math.floor(y + 0.5)
            target.set_pixel(x, pixel_y, 1.0)
            if trace is not None:
                trace.append({"шаг": index, "x": x, "y = kx + b": round(y, 4), "пиксель": (x, pixel_y)})
    else:
        k = dx / dy
        b = x1 - k * y1
        step = 1 if dy > 0 else -1
        for index, y in enumerate(range(y1, y2 + step, step)):
            x = k * y + b
            pixel_x = math.floor(x + 0.5)
            target.set_pixel(pixel_x, y, 1.0)
            if trace is not None:
                trace.append({"шаг": index, "y": y, "x = ky + b": round(x, 4), "пиксель": (pixel_x, y)})


def dda_line(target, x1, y1, x2, y2, trace=None):
    steps = max(abs(x2 - x1), abs(y2 - y1))
    if steps == 0:
        target.set_pixel(x1, y1, 1.0)
        if trace is not None:
            trace.append({"шаг": 0, "x": x1, "y": y1, "пиксель": (x1, y1)})
        return
    x_step = (x2 - x1) / steps
    y_step = (y2 - y1) / steps
    x = float(x1)
    y = float(y1)
    for index in range(steps + 1):
        pixel_x = math.floor(x + 0.5)
        pixel_y = math.floor(y + 0.5)
        target.set_pixel(pixel_x, pixel_y, 1.0)
        if trace is not None:
            trace.append({"шаг": index, "x": round(x, 4), "y": round(y, 4), "пиксель": (pixel_x, pixel_y)})
        x += x_step
        y += y_step


def bresenham_line(target, x1, y1, x2, y2, trace=None):
    dx = abs(x2 - x1)
    dy = abs(y2 - y1)
    sx = 1 if x2 >= x1 else -1
    sy = 1 if y2 >= y1 else -1
    x, y = x1, y1
    if dx >= dy:
        error = 2 * dy - dx
        up = 2 * dy
        down = 2 * (dy - dx)
        for index in range(dx + 1):
            target.set_pixel(x, y, 1.0)
            if trace is not None:
                trace.append({"шаг": index, "пиксель": (x, y), "e": error, "сдвиг по y": "да" if error >= 0 else "нет"})
            if error >= 0:
                y += sy
                error += down
            else:
                error += up
            x += sx
    else:
        error = 2 * dx - dy
        up = 2 * dx
        down = 2 * (dx - dy)
        for index in range(dy + 1):
            target.set_pixel(x, y, 1.0)
            if trace is not None:
                trace.append({"шаг": index, "пиксель": (x, y), "e": error, "сдвиг по x": "да" if error >= 0 else "нет"})
            if error >= 0:
                x += sx
                error += down
            else:
                error += up
            y += sy


def bresenham_circle(target, xc, yc, radius, trace=None):
    x = 0
    y = radius
    d = 3 - 2 * radius
    index = 0
    while x <= y:
        for px, py in ((x, y), (y, x), (-x, y), (-y, x), (x, -y), (y, -x), (-x, -y), (-y, -x)):
            target.set_pixel(xc + px, yc + py, 1.0)
        if trace is not None:
            trace.append({"шаг": index, "x": x, "y": y, "d": d, "выбор": "(x+1, y)" if d < 0 else "(x+1, y−1)"})
        if d < 0:
            d += 4 * x + 6
        else:
            d += 4 * (x - y) + 10
            y -= 1
        x += 1
        index += 1


def wu_line(target, x1, y1, x2, y2, trace=None):
    steep = abs(y2 - y1) > abs(x2 - x1)
    if steep:
        x1, y1, x2, y2 = y1, x1, y2, x2
    if x1 > x2:
        x1, y1, x2, y2 = x2, y2, x1, y1
    dx = x2 - x1
    gradient = (y2 - y1) / dx if dx else 0.0
    y = float(y1)
    for index, x in enumerate(range(x1, x2 + 1)):
        base = math.floor(y)
        fraction = y - base
        lower = 1.0 - fraction
        upper = fraction
        if steep:
            target.set_pixel(base, x, lower)
            target.set_pixel(base + 1, x, upper)
            pair = ((base, x), (base + 1, x))
        else:
            target.set_pixel(x, base, lower)
            target.set_pixel(x, base + 1, upper)
            pair = ((x, base), (x, base + 1))
        if trace is not None:
            trace.append({"шаг": index, "y точное": round(y, 4), "дробная часть": round(fraction, 4),
                          "пиксель 1": pair[0], "яркость 1": round(lower, 3),
                          "пиксель 2": pair[1], "яркость 2": round(upper, 3)})
        y += gradient


def castle_pitteway_moves(length, rise, trace=None):
    if length == 0:
        return ""
    if rise == 0:
        return "s" * length
    if rise == length:
        return "d" * length
    x = length - rise
    y = rise
    first = "s"
    second = "d"
    if trace is not None:
        trace.append({"x": x, "y": y, "m1": first, "m2": second})
    while x != y:
        if x > y:
            x -= y
            second = first + second[::-1]
        else:
            y -= x
            first = second + first[::-1]
        if trace is not None:
            trace.append({"x": x, "y": y, "m1": first, "m2": second})
    return (second + first[::-1]) * x


def castle_pitteway_line(target, x1, y1, x2, y2, trace=None):
    length, rise, step_x, step_y, shift_x, shift_y = _directions(x1, y1, x2, y2)
    moves = castle_pitteway_moves(length, rise, trace)
    x, y = x1, y1
    target.set_pixel(x, y, 1.0)
    for move in moves:
        if move == "d":
            x += shift_x
            y += shift_y
        x += step_x
        y += step_y
        target.set_pixel(x, y, 1.0)
    if trace is not None:
        trace.append({"x": "итог", "y": "", "m1": f"ходы: {moves}", "m2": f"s — {moves.count('s')}, d — {moves.count('d')}"})


def _in_arc(px, py, start, end):
    if start is None:
        return True
    angle = math.degrees(math.atan2(py, px)) % 360
    start %= 360
    end %= 360
    if start <= end:
        return start <= angle <= end
    return angle >= start or angle <= end


def pitteway_ellipse(target, xc, yc, a, b, trace=None, start=None, end=None):
    a2 = a * a
    b2 = b * b
    x = 0
    y = b
    d = 4 * b2 - 4 * a2 * b + a2
    index = 0

    def plot(px, py):
        for qx, qy in ((px, py), (-px, py), (px, -py), (-px, -py)):
            if _in_arc(qx, qy, start, end):
                target.set_pixel(xc + qx, yc + qy, 1.0)

    while b2 * x < a2 * y:
        plot(x, y)
        if trace is not None:
            trace.append({"шаг": index, "область": 1, "x": x, "y": y, "d": d,
                          "выбор": "(x+1, y)" if d < 0 else "(x+1, y−1)"})
        if d < 0:
            d += 4 * b2 * (2 * x + 3)
        else:
            d += 4 * b2 * (2 * x + 3) - 8 * a2 * (y - 1)
            y -= 1
        x += 1
        index += 1
    d = b2 * (2 * x + 1) ** 2 + 4 * a2 * (y - 1) ** 2 - 4 * a2 * b2
    while y >= 0:
        plot(x, y)
        if trace is not None:
            trace.append({"шаг": index, "область": 2, "x": x, "y": y, "d": d,
                          "выбор": "(x, y−1)" if d > 0 else "(x+1, y−1)"})
        if d > 0:
            d -= 4 * a2 * (2 * y - 3)
        else:
            d += 4 * b2 * (2 * x + 2) - 4 * a2 * (2 * y - 3)
            x += 1
        y -= 1
        index += 1


LINE_ALGORITHMS = {
    "Пошаговый": step_line,
    "ЦДА": dda_line,
    "Брезенхем (отрезок)": bresenham_line,
    "Ву (сглаживание)": wu_line,
    "Кастл-Питвей (отрезок)": castle_pitteway_line,
}
