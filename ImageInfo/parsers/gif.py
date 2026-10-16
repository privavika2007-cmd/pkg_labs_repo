from .common import BrokenFile


def skip_blocks(reader):
    while True:
        size = reader.read(1)[0]
        if size == 0:
            return
        reader.seek(reader.tell() + size)


def parse(reader, info):
    reader.seek(0)
    version = reader.read(6).decode("ascii")
    width, height, packed, background, aspect = reader.unpack("<HHBBB")
    if width == 0 or height == 0:
        raise BrokenFile("нулевой логический размер экрана")

    has_table = packed & 0x80
    bits = (packed & 0x07) + 1
    color_resolution = ((packed >> 4) & 0x07) + 1

    info.width = width
    info.height = height
    info.depth = f"{bits} бит (индекс в палитре из {2 ** bits} цветов)"
    info.compression = "LZW"
    info.dpi = "не хранится в формате GIF"
    info.extra["Версия"] = version
    info.extra["Глобальная палитра"] = f"{2 ** bits} цветов" if has_table else "нет"
    info.extra["Разрядность исходных цветов"] = f"{color_resolution} бит на канал"
    if aspect:
        info.extra["Соотношение сторон пикселя"] = f"{(aspect + 15) / 64:.3f}"

    if has_table:
        reader.seek(reader.tell() + 3 * 2 ** bits)

    frames = 0
    local_tables = 0
    transparent = False
    loop = None
    while True:
        block = reader.read(1)[0]
        if block == 0x2C:
            _, _, frame_width, frame_height, flags = reader.unpack("<HHHHB")
            if flags & 0x80:
                local_tables += 1
                reader.seek(reader.tell() + 3 * 2 ** ((flags & 0x07) + 1))
            reader.read(1)
            skip_blocks(reader)
            frames += 1
        elif block == 0x21:
            label = reader.read(1)[0]
            if label == 0xF9:
                size = reader.read(1)[0]
                data = reader.read(size)
                if size >= 4 and data[0] & 1:
                    transparent = True
                skip_blocks(reader)
            elif label == 0xFF:
                size = reader.read(1)[0]
                name = reader.read(size)
                if name[:8] in (b"NETSCAPE", b"ANIMEXTS"):
                    size = reader.read(1)[0]
                    data = reader.read(size)
                    if size >= 3 and data[0] == 1:
                        loop = int.from_bytes(data[1:3], "little")
                skip_blocks(reader)
            else:
                skip_blocks(reader)
        elif block == 0x3B:
            break
        else:
            raise BrokenFile(f"неизвестный блок 0x{block:02X} по смещению {reader.tell() - 1}")

    if frames == 0:
        raise BrokenFile("в файле нет ни одного изображения")
    info.extra["Кадров"] = str(frames) + (" (анимация)" if frames > 1 else "")
    if local_tables:
        info.extra["Локальных палитр"] = str(local_tables)
    if transparent:
        info.extra["Прозрачность"] = "есть (Graphic Control Extension)"
    if loop is not None:
        info.extra["Повторов анимации"] = "бесконечно" if loop == 0 else str(loop)


def wrap(reader, info):
    try:
        parse(reader, info)
    except BrokenFile as error:
        if str(error) in ("неожиданный конец файла", "ссылка за пределы файла"):
            raise BrokenFile("нет завершающего байта 0x3B, файл обрезан")
        raise
