def number(value, digits=4):
    text = f"{value:.{digits}f}".rstrip("0").rstrip(".")
    return text.replace(".", ",") if text != "-0" else "0"


def explain_line(name, x1, y1, x2, y2):
    dx = x2 - x1
    dy = y2 - y1
    lines = [f"Отрезок ({x1}, {y1}) — ({x2}, {y2}):  Δx = {dx},  Δy = {dy}."]
    if dx == 0 and dy == 0:
        return lines + ["Концы совпадают — закрашивается один пиксель."]
    along_x = abs(dx) >= abs(dy)
    if name == "Пошаговый":
        if along_x:
            k = dy / dx
            b = y1 - k * x1
            lines.append(f"|Δx| ≥ |Δy| — шагаем по x. k = Δy/Δx = {number(k)},  b = y1 − k·x1 = {number(b)}.")
            lines.append("На каждом шаге y = k·x + b, пиксель (x, ⌊y + 0,5⌋).")
        else:
            k = dx / dy
            b = x1 - k * y1
            lines.append(f"|Δy| > |Δx| — шагаем по y. k = Δx/Δy = {number(k)},  b = x1 − k·y1 = {number(b)}.")
            lines.append("На каждом шаге x = k·y + b, пиксель (⌊x + 0,5⌋, y).")
    elif name == "ЦДА":
        steps = max(abs(dx), abs(dy))
        lines.append(f"Число шагов L = max(|Δx|, |Δy|) = {steps}.")
        lines.append(f"Приращения: Δx/L = {number(dx / steps)},  Δy/L = {number(dy / steps)}.")
        lines.append("x и y накапливаются сложением, пиксель — (⌊x + 0,5⌋, ⌊y + 0,5⌋).")
    elif name.startswith("Брезенхем"):
        big, small = (abs(dx), abs(dy)) if along_x else (abs(dy), abs(dx))
        axis = "x" if along_x else "y"
        other = "y" if along_x else "x"
        lines.append(f"Главная ось {axis}: L = {big}, малое приращение m = {small}.")
        lines.append(f"e₀ = 2m − L = {2 * small - big};  если e ≥ 0: {other} сдвигается, e += 2(m − L) = {2 * (small - big)};"
                     f"  иначе e += 2m = {2 * small}.")
        lines.append("Только целые сложения и сравнение с нулём.")
    elif name.startswith("Ву"):
        if along_x:
            lines.append(f"Шагаем по x, градиент g = Δy/Δx = {number(dy / dx)}.")
        else:
            lines.append(f"|Δy| > |Δx| — оси меняются местами, градиент g = Δx/Δy = {number(dx / dy)}.")
        lines.append("Точная координата y делится на целую часть и дробную f:")
        lines.append("пиксель ⌊y⌋ получает яркость 1 − f, пиксель ⌊y⌋ + 1 — яркость f.")
    elif name.startswith("Кастл"):
        big, small = (abs(dx), abs(dy)) if along_x else (abs(dy), abs(dx))
        lines.append(f"Нормализуем в первый октант: L = {big}, m = {small}. Ход s — шаг по главной оси, d — диагональный.")
        lines.append(f"Начало: x = L − m = {big - small}, y = m = {small}, m1 = s, m2 = d.")
        lines.append("Пока x ≠ y: если x > y, то x −= y, m2 = m1 + обратная(m2); иначе y −= x, m1 = m2 + обратная(m1).")
        lines.append("Итог: (m2 + обратная(m1)), повторённое x раз.")
    return lines


def explain_circle(xc, yc, radius):
    return [f"Окружность: центр ({xc}, {yc}), R = {radius}.",
            f"Строится дуга второго октанта от (0, R) до x = y, остальные 7 октантов — симметрией (±x, ±y), (±y, ±x).",
            f"d₀ = 3 − 2R = {3 - 2 * radius};  если d < 0: d += 4x + 6, иначе d += 4(x − y) + 10 и y −= 1;  x += 1."]


def explain_ellipse(xc, yc, a, b):
    a2 = a * a
    b2 = b * b
    return [f"Эллипс: центр ({xc}, {yc}), a = {a}, b = {b}, a² = {a2}, b² = {b2}.",
            f"F(x, y) = b²x² + a²y² − a²b². Область 1 (пока b²x < a²y): d₀ = 4b² − 4a²b + a² = {4 * b2 - 4 * a2 * b + a2}.",
            "Область 1: d < 0 → (x+1, y), d += 4b²(2x+3); иначе (x+1, y−1), d += 4b²(2x+3) − 8a²(y−1).",
            "Область 2: d > 0 → (x, y−1), d −= 4a²(2y−3); иначе (x+1, y−1), d += 4b²(2x+2) − 4a²(2y−3).",
            "Все величины целые: множитель 4 убирает дроби 1/2 и 1/4 из средней точки."]
