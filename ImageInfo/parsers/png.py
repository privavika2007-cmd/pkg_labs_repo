import zlib

from .common import BrokenFile, dpi_text

COLOR_TYPES = {
    0: ("оттенки серого", 1, (1, 2, 4, 8, 16)),
    2: ("RGB", 3, (8, 16)),
    3: ("палитра", 1, (1, 2, 4, 8)),
    4: ("оттенки серого + альфа", 2, (8, 16)),
    6: ("RGBA", 4, (8, 16)),
}


def parse(reader, info):
    reader.seek(8)
    length, chunk = reader.unpack(">I4s")
    if chunk != b"IHDR" or length != 13:
        raise BrokenFile("первым должен идти чанк IHDR длиной 13 байт")
    data = reader.read(13)
    crc = reader.unpack(">I")[0]
    if zlib.crc32(chunk + data) != crc:
        raise BrokenFile("контрольная сумма CRC чанка IHDR не совпадает")

    width = int.from_bytes(data[0:4], "big")
    height = int.from_bytes(data[4:8], "big")
    bit_depth, color_type, compression, filter_method, interlace = data[8:13]
    if width == 0 or height == 0:
        raise BrokenFile("нулевой размер в IHDR")
    if color_type not in COLOR_TYPES or bit_depth not in COLOR_TYPES[color_type][2]:
        raise BrokenFile("недопустимое сочетание глубины и типа цвета")

    name, channels, _ = COLOR_TYPES[color_type]
    info.width = width
    info.height = height
    if color_type == 3:
        info.depth = f"{bit_depth} бит (индекс в палитре)"
    else:
        info.depth = f"{bit_depth * channels} бит ({name}, {bit_depth} бит на канал)"
    info.compression = "Deflate (zlib)" if compression == 0 else f"неизвестный метод {compression}"
    info.extra["Тип цвета"] = f"{color_type} — {name}"
    info.extra["Фильтрация"] = "адаптивная, метод 0 (5 фильтров на строку)" if filter_method == 0 else f"метод {filter_method}"
    info.extra["Чересстрочность"] = "Adam7" if interlace == 1 else "нет"

    position = 33
    data_chunks = 0
    found_end = False
    info.dpi = "не указано"
    while position + 12 <= reader.size:
        reader.seek(position)
        length, chunk = reader.unpack(">I4s")
        if not chunk.isalpha():
            raise BrokenFile(f"повреждённый заголовок чанка по смещению {position}")
        end = position + 12 + length
        if end > reader.size:
            raise BrokenFile(f"чанк {chunk.decode()} выходит за конец файла")
        if chunk == b"pHYs" and length == 9:
            x, y, unit = reader.unpack(">IIB")
            if unit == 1:
                info.dpi = dpi_text(x * 0.0254, y * 0.0254)
            else:
                info.dpi = f"не указано (соотношение сторон пикселя {x}:{y})"
        elif chunk == b"PLTE":
            info.extra["Палитра"] = f"{length // 3} цветов (чанк PLTE)"
        elif chunk == b"tRNS":
            info.extra["Прозрачность"] = "есть (чанк tRNS)"
        elif chunk == b"IDAT":
            data_chunks += 1
        elif chunk == b"IEND":
            found_end = True
            break
        position = end

    if data_chunks == 0:
        raise BrokenFile("нет ни одного чанка IDAT с данными")
    if not found_end:
        raise BrokenFile("нет завершающего чанка IEND (файл обрезан)")
    info.extra["Чанков IDAT"] = str(data_chunks)
