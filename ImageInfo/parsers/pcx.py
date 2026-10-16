from .common import BrokenFile, dpi_text

VERSIONS = {
    0: "2.5",
    2: "2.8 с палитрой",
    3: "2.8 без палитры",
    4: "Paintbrush для Windows",
    5: "3.0 и выше",
}


def parse(reader, info):
    if reader.size <= 128:
        raise BrokenFile("файл короче заголовка PCX (128 байт)")
    reader.seek(0)
    head = reader.read(128)
    maker, version, encoding, bits = head[0:4]
    x_min, y_min, x_max, y_max, x_dpi, y_dpi = (int.from_bytes(head[i:i + 2], "little") for i in range(4, 16, 2))
    planes = head[65]
    bytes_per_line = int.from_bytes(head[66:68], "little")

    if maker != 0x0A or encoding not in (0, 1) or version not in VERSIONS:
        raise BrokenFile("некорректный заголовок PCX")
    width = x_max - x_min + 1
    height = y_max - y_min + 1
    if width <= 0 or height <= 0 or planes == 0 or bits not in (1, 2, 4, 8):
        raise BrokenFile("некорректные размеры или глубина в заголовке PCX")
    if bytes_per_line * 8 < width * bits:
        raise BrokenFile("длина строки меньше ширины изображения")

    info.width = width
    info.height = height
    info.depth = f"{bits * planes} бит ({planes} плоск. × {bits} бит)"
    info.compression = "RLE (PCX)" if encoding == 1 else "без сжатия"
    info.dpi = dpi_text(x_dpi, y_dpi)
    info.extra["Версия"] = VERSIONS[version]
    info.extra["Байт на строку плоскости"] = str(bytes_per_line)

    if bits == 8 and planes == 1:
        if reader.size >= 128 + 769 and reader.read_at(reader.size - 769, 1) == b"\x0c":
            info.extra["Палитра"] = "256 цветов, в конце файла после байта 0x0C"
            info.depth = "8 бит (индекс в палитре из 256 цветов)"
        else:
            raise BrokenFile("нет 256-цветной палитры в конце файла (файл обрезан)")
    elif bits * planes <= 4:
        info.extra["Палитра"] = f"{2 ** (bits * planes)} цветов, в заголовке (EGA)"
    else:
        info.extra["Палитра"] = "нет, цвет хранится прямо в пикселях"
