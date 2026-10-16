import struct

from .common import BrokenFile, dpi_text
from .tiff import read_exif

FRAMES = {
    0xC0: "Baseline DCT, Хаффман",
    0xC1: "Extended sequential DCT, Хаффман",
    0xC2: "Progressive DCT, Хаффман",
    0xC3: "Lossless, Хаффман",
    0xC5: "Differential sequential DCT, Хаффман",
    0xC6: "Differential progressive DCT, Хаффман",
    0xC7: "Differential lossless, Хаффман",
    0xC9: "Extended sequential DCT, арифметическое",
    0xCA: "Progressive DCT, арифметическое",
    0xCB: "Lossless, арифметическое",
    0xCD: "Differential sequential DCT, арифметическое",
    0xCE: "Differential progressive DCT, арифметическое",
    0xCF: "Differential lossless, арифметическое",
}

ZIGZAG = [
    0, 1, 8, 16, 9, 2, 3, 10, 17, 24, 32, 25, 18, 11, 4, 5,
    12, 19, 26, 33, 40, 48, 41, 34, 27, 20, 13, 6, 7, 14, 21, 28,
    35, 42, 49, 56, 57, 50, 43, 36, 29, 22, 15, 23, 30, 37, 44, 51,
    58, 59, 52, 45, 38, 31, 39, 46, 53, 60, 61, 54, 47, 55, 62, 63,
]

STANDARD_LUMA = [
    16, 11, 10, 16, 24, 40, 51, 61, 12, 12, 14, 19, 26, 58, 60, 55,
    14, 13, 16, 24, 40, 57, 69, 56, 14, 17, 22, 29, 51, 87, 80, 62,
    18, 22, 37, 56, 68, 109, 103, 77, 24, 35, 55, 64, 81, 104, 113, 92,
    49, 64, 78, 87, 103, 121, 120, 101, 72, 92, 95, 98, 112, 100, 103, 99,
]

SUBSAMPLING = {(1, 1): "4:4:4", (2, 1): "4:2:2", (2, 2): "4:2:0", (1, 2): "4:4:0", (4, 1): "4:1:1"}


def read_tables(data, tables):
    i = 0
    while i < len(data):
        precision = data[i] >> 4
        number = data[i] & 15
        size = 128 if precision else 64
        chunk = data[i + 1:i + 1 + size]
        if len(chunk) < size:
            raise BrokenFile("обрезанная таблица квантования DQT")
        values = struct.unpack(">64H", chunk) if precision else chunk
        table = [0] * 64
        for k in range(64):
            table[ZIGZAG[k]] = values[k]
        tables[number] = table
        i += 1 + size


def estimate_quality(table):
    scale = sum(table[i] * 100 / STANDARD_LUMA[i] for i in range(64)) / 64
    if scale <= 100:
        quality = (200 - scale) / 2
    else:
        quality = 5000 / scale
    return max(1, min(100, round(quality)))


def table_text(table):
    return "\n".join(" ".join(f"{value:3}" for value in table[row * 8:row * 8 + 8]) for row in range(8))


def parse(reader, info):
    reader.seek(2)
    frame = None
    jfif = None
    exif = None
    adobe = None
    tables = {}

    while True:
        if reader.read(1)[0] != 0xFF:
            raise BrokenFile(f"ожидался маркер FF по смещению {reader.tell() - 1}")
        marker = reader.read(1)[0]
        while marker == 0xFF:
            marker = reader.read(1)[0]
        if marker == 0x01 or 0xD0 <= marker <= 0xD8:
            continue
        if marker == 0xD9:
            raise BrokenFile("маркер EOI встретился раньше данных изображения")
        length = reader.unpack(">H")[0]
        start = reader.tell()
        if length < 2 or start + length - 2 > reader.size:
            raise BrokenFile(f"сегмент FF{marker:02X} выходит за конец файла")

        if marker == 0xDA:
            break
        if marker == 0xE0 and length >= 16:
            data = reader.read(14)
            if data[:5] == b"JFIF\0":
                jfif = struct.unpack(">BBBHH", data[5:12])
        elif marker == 0xE1 and length > 16:
            data = reader.read(length - 2)
            if data[:6] == b"Exif\0\0":
                try:
                    exif = read_exif(data[6:])
                except (BrokenFile, struct.error, ValueError):
                    info.extra["Exif"] = "есть, но повреждён"
        elif marker == 0xEE and length >= 14:
            data = reader.read(12)
            if data[:5] == b"Adobe":
                adobe = data[11]
        elif marker == 0xDB:
            read_tables(reader.read(length - 2), tables)
        elif marker in FRAMES:
            data = reader.read(length - 2)
            precision, height, width, count = struct.unpack(">BHHB", data[:6])
            parts = [data[6 + 3 * k:9 + 3 * k] for k in range(count)]
            if len(parts[-1]) < 3:
                raise BrokenFile("обрезанный маркер SOF")
            frame = (marker, precision, height, width, count, parts)
        reader.seek(start + length - 2)

    if frame is None:
        raise BrokenFile("нет маркера SOF с размерами изображения")
    marker, precision, height, width, count, parts = frame
    if width == 0:
        raise BrokenFile("нулевая ширина в маркере SOF")

    info.width = width
    info.height = height
    if count == 1:
        model = "оттенки серого"
    elif count == 3:
        model = "RGB" if adobe == 0 and jfif is None else "YCbCr"
    elif count == 4:
        model = "YCCK" if adobe == 2 else "CMYK"
    else:
        model = f"{count} компонент"
    info.depth = f"{precision * count} бит ({count} × {precision} бит, {model})"
    info.compression = FRAMES[marker]
    info.extra["Тип сжатия"] = "без потерь" if marker in (0xC3, 0xC7, 0xCB, 0xCF) else "с потерями (ДКП + квантование)"
    if count >= 3:
        luma = (parts[0][1] >> 4, parts[0][1] & 15)
        info.extra["Субдискретизация цветности"] = SUBSAMPLING.get(luma, f"{luma[0]}×{luma[1]}")

    if jfif and jfif[2] in (1, 2) and jfif[3]:
        factor = 1 if jfif[2] == 1 else 2.54
        info.dpi = dpi_text(jfif[3] * factor, jfif[4] * factor)
    elif exif and "dpi" in exif:
        info.dpi = exif.pop("dpi")
    elif jfif:
        info.dpi = f"не указано (соотношение сторон пикселя {jfif[3]}:{jfif[4]})"
    else:
        info.dpi = "не указано"
    if exif:
        exif.pop("dpi", None)
        info.extra.update(exif)
    if jfif:
        info.extra["JFIF"] = f"версия {jfif[0]}.{jfif[1]:02d}"

    if 0 in tables:
        info.extra["Оценка качества"] = f"≈ {estimate_quality(tables[0])} (по таблице яркости)"
    for number, table in sorted(tables.items()):
        name = "яркость" if number == 0 else "цветность"
        info.extra[f"Таблица квантования {number} ({name})"] = table_text(table)

    if reader.read_at(reader.size - 2, 2) != b"\xff\xd9":
        tail = reader.read_at(max(0, reader.size - 4096), min(reader.size, 4096))
        place = tail.rfind(b"\xff\xd9")
        if place < 0:
            raise BrokenFile("нет маркера конца изображения EOI (FF D9), файл обрезан")
        info.extra["После EOI"] = f"{len(tail) - place - 2} байт лишних данных"
