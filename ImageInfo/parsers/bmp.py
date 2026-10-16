import struct

from .common import BrokenFile, dpi_text

HEADERS = {
    12: "BITMAPCOREHEADER",
    40: "BITMAPINFOHEADER",
    52: "BITMAPV2INFOHEADER",
    56: "BITMAPV3INFOHEADER",
    108: "BITMAPV4HEADER",
    124: "BITMAPV5HEADER",
}

COMPRESSION = {
    0: "BI_RGB (без сжатия)",
    1: "BI_RLE8 (RLE для 8 бит)",
    2: "BI_RLE4 (RLE для 4 бит)",
    3: "BI_BITFIELDS (без сжатия, маски каналов)",
    4: "BI_JPEG",
    5: "BI_PNG",
    6: "BI_ALPHABITFIELDS",
    11: "BI_CMYK",
    12: "BI_CMYKRLE8",
    13: "BI_CMYKRLE4",
}

INCH = 0.0254


def parse(reader, info):
    signature, declared_size, _, _, data_offset = reader.unpack("<2sIHHI")
    header_size = reader.unpack("<I")[0]

    if header_size == 12:
        width, height, planes, bits = reader.unpack("<HHHH")
        compression = 0
        image_size = x_ppm = y_ppm = colors_used = 0
        color_bytes = 3
    elif header_size in HEADERS:
        width, height, planes, bits, compression, image_size, x_ppm, y_ppm, colors_used, _ = reader.unpack("<iiHHIIiiII")
        color_bytes = 4
    else:
        raise BrokenFile(f"неизвестный размер заголовка DIB: {header_size}")

    top_down = height < 0
    height = abs(height)
    if width <= 0 or height == 0:
        raise BrokenFile("нулевая или отрицательная ширина изображения")
    if planes != 1 or bits not in (1, 2, 4, 8, 16, 24, 32):
        raise BrokenFile("некорректные поля planes / bitCount")
    if compression not in COMPRESSION:
        raise BrokenFile(f"неизвестный тип сжатия: {compression}")

    info.width = width
    info.height = height
    info.depth = f"{bits} бит"
    info.compression = COMPRESSION[compression]
    info.dpi = dpi_text(x_ppm * INCH, y_ppm * INCH)
    info.extra["Заголовок"] = f"BITMAPFILEHEADER + {HEADERS[header_size]} ({header_size} байт)"
    info.extra["Порядок строк"] = "сверху вниз" if top_down else "снизу вверх"
    info.extra["Смещение пикселей"] = f"{data_offset} байт"

    palette_start = 14 + header_size
    if compression in (3, 6) and header_size == 40:
        palette_start += 12 if compression == 3 else 16

    if bits <= 8:
        count = colors_used or 2 ** bits
        if count > 2 ** bits:
            raise BrokenFile("в палитре больше цветов, чем допускает глубина")
        palette = reader.read_at(palette_start, count * color_bytes)
        gray = all(palette[i] == palette[i + 1] == palette[i + 2] for i in range(0, len(palette), color_bytes))
        kind = "оттенки серого" if gray else "цветная"
        info.extra["Палитра"] = f"{count} цветов, {kind}, по {color_bytes} байта на цвет (B, G, R{', резерв' if color_bytes == 4 else ''})"
        info.depth += f" (индекс в палитре из {count} цветов)"
    elif compression in (3, 6):
        mask_start = 14 + 40 if header_size >= 40 else palette_start
        masks = struct.unpack("<III", reader.read_at(mask_start, 12))
        sizes = "-".join(str(bin(mask).count("1")) for mask in masks)
        info.extra["Маски R, G, B"] = " / ".join(f"0x{mask:08X}" for mask in masks)
        info.depth += f" ({sizes})"
    else:
        info.extra["Палитра"] = "нет, цвет хранится прямо в пикселях"

    if declared_size and reader.size < declared_size:
        raise BrokenFile(f"размер файла {reader.size} байт меньше указанного в заголовке ({declared_size})")
    if data_offset > reader.size:
        raise BrokenFile("смещение пикселей указывает за конец файла")

    if compression in (0, 3, 6):
        row = (width * bits + 31) // 32 * 4
        need = data_offset + row * height
        if reader.size < need:
            raise BrokenFile(f"пиксельных данных меньше, чем требует заголовок ({reader.size} < {need} байт)")
    elif image_size and data_offset + image_size > reader.size:
        raise BrokenFile("сжатые данные выходят за конец файла")
