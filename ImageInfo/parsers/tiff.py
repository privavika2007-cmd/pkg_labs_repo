import struct

from .common import BrokenFile, dpi_text

TYPE_SIZES = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 6: 1, 7: 1, 8: 2, 9: 4, 10: 8, 11: 4, 12: 8, 13: 4, 16: 8, 17: 8, 18: 8}
TYPE_FORMATS = {1: "B", 3: "H", 4: "I", 6: "b", 7: "B", 8: "h", 9: "i", 11: "f", 12: "d", 13: "I", 16: "Q", 17: "q", 18: "Q"}

COMPRESSION = {
    1: "без сжатия",
    2: "CCITT RLE (модифицированный Хаффман)",
    3: "CCITT Group 3 (факс T.4)",
    4: "CCITT Group 4 (факс T.6)",
    5: "LZW",
    6: "JPEG (старый вариант)",
    7: "JPEG",
    8: "Deflate (Adobe)",
    32773: "PackBits (RLE)",
    32946: "Deflate",
    34712: "JPEG 2000",
    34925: "LZMA",
    50000: "Zstandard",
}

PHOTOMETRIC = {
    0: "оттенки серого, 0 — белый",
    1: "оттенки серого, 0 — чёрный",
    2: "RGB",
    3: "палитра",
    4: "маска прозрачности",
    5: "CMYK",
    6: "YCbCr",
    8: "CIE Lab",
}


class Tiff:
    def __init__(self, read_at, size):
        self.read_at = read_at
        self.size = size
        order = read_at(0, 2)
        if order == b"II":
            self.order = "<"
        elif order == b"MM":
            self.order = ">"
        else:
            raise BrokenFile("неизвестный порядок байт TIFF")
        magic = self.number("H", 2)
        if magic == 42:
            self.big = False
            self.first = self.number("I", 4)
        elif magic == 43:
            self.big = True
            self.first = self.number("Q", 8)
        else:
            raise BrokenFile("неверное магическое число TIFF")

    def number(self, fmt, position):
        size = struct.calcsize(fmt)
        return struct.unpack(self.order + fmt, self.read_at(position, size))[0]

    def layout(self):
        if self.big:
            return "Q", 8, 20, 8
        return "H", 2, 12, 4

    def read_ifd(self, offset):
        count_format, count_size, entry_size, value_size = self.layout()
        count = self.number(count_format, offset)
        if count == 0 or count > 4096:
            raise BrokenFile(f"подозрительное число тегов в IFD: {count}")
        start = offset + count_size
        raw = self.read_at(start, count * entry_size)
        number_format = "Q" if self.big else "I"
        tags = {}
        for i in range(count):
            entry = raw[i * entry_size:(i + 1) * entry_size]
            tag, kind = struct.unpack(self.order + "HH", entry[:4])
            amount = struct.unpack(self.order + number_format, entry[4:4 + value_size])[0]
            tags[tag] = (kind, amount, entry[4 + value_size:])
        next_offset = self.number("Q" if self.big else "I", start + count * entry_size)
        return tags, next_offset

    def next_ifd(self, offset):
        count_format, count_size, entry_size, _ = self.layout()
        count = self.number(count_format, offset)
        return self.number("Q" if self.big else "I", offset + count_size + count * entry_size)

    def values(self, entry):
        kind, amount, field = entry
        if kind not in TYPE_SIZES or amount == 0:
            return []
        total = TYPE_SIZES[kind] * amount
        if total > 64 * 1024 * 1024:
            raise BrokenFile("слишком большой массив значений тега")
        if total <= len(field):
            data = field[:total]
        else:
            position = struct.unpack(self.order + ("Q" if self.big else "I"), field)[0]
            data = self.read_at(position, total)
        if kind == 2:
            return [data.split(b"\0")[0].decode("latin-1").strip()]
        if kind in (5, 10):
            parts = struct.unpack(self.order + ("I" if kind == 5 else "i") * (amount * 2), data)
            return [parts[i] / parts[i + 1] if parts[i + 1] else 0 for i in range(0, len(parts), 2)]
        return list(struct.unpack(self.order + TYPE_FORMATS[kind] * amount, data))

    def get(self, tags, tag, default=None):
        if tag in tags:
            found = self.values(tags[tag])
            if found:
                return found
        return default


def resolution_text(x, y, unit):
    if not x:
        return "не указано"
    y = y or x
    if unit == 3:
        return dpi_text(x[0] * 2.54, y[0] * 2.54)
    if unit == 1:
        return f"не указано (соотношение {x[0]:g}:{y[0]:g} без единиц)"
    return dpi_text(x[0], y[0])


def parse(reader, info):
    tiff = Tiff(reader.read_at, reader.size)
    tags, next_offset = tiff.read_ifd(tiff.first)

    width = tiff.get(tags, 256)
    height = tiff.get(tags, 257)
    if not width or not height:
        raise BrokenFile("в IFD нет тегов ImageWidth / ImageLength")
    info.width = width[0]
    info.height = height[0]

    samples = tiff.get(tags, 277, [1])[0]
    bits = tiff.get(tags, 258, [1])
    if len(bits) < samples:
        bits = bits * samples
    photometric = tiff.get(tags, 262, [None])[0]
    color = PHOTOMETRIC.get(photometric, f"код {photometric}")
    if 338 in tags:
        color += " + альфа-канал"
    info.depth = f"{sum(bits[:samples])} бит ({samples} × {bits[0]} бит, {color})"

    compression = tiff.get(tags, 259, [1])[0]
    info.compression = COMPRESSION.get(compression, f"код {compression}")
    info.dpi = resolution_text(tiff.get(tags, 282), tiff.get(tags, 283), tiff.get(tags, 296, [2])[0])

    offsets = tiff.get(tags, 273) or tiff.get(tags, 324)
    counts = tiff.get(tags, 279) or tiff.get(tags, 325)
    if not offsets:
        raise BrokenFile("нет смещений данных изображения (StripOffsets / TileOffsets)")
    if counts:
        if len(counts) != len(offsets):
            raise BrokenFile("число смещений и длин полос не совпадает")
        end = max(o + c for o, c in zip(offsets, counts))
        if end > reader.size:
            raise BrokenFile(f"данные изображения выходят за конец файла ({end} > {reader.size} байт)")

    pages = 1
    seen = {tiff.first}
    while next_offset:
        if next_offset in seen or next_offset >= reader.size:
            raise BrokenFile("ссылка на следующую страницу (IFD) ведёт в никуда")
        seen.add(next_offset)
        next_offset = tiff.next_ifd(next_offset)
        pages += 1

    info.extra["Порядок байт"] = "Intel (II, little-endian)" if tiff.order == "<" else "Motorola (MM, big-endian)"
    if tiff.big:
        info.extra["Вариант"] = "BigTIFF (64-битные смещения)"
    info.extra["Страниц (IFD)"] = str(pages)
    info.extra["Тегов в первом IFD"] = str(len(tags))
    info.extra["Хранение"] = f"{'плитки' if 324 in tags else 'полосы'}: {len(offsets)} шт."
    if 320 in tags:
        info.extra["Палитра"] = f"{tags[320][1] // 3} цветов (тег ColorMap)"
    planar = tiff.get(tags, 284, [1])[0]
    info.extra["Расположение каналов"] = "по пикселям (RGBRGB…)" if planar == 1 else "плоскостями (RR…GG…BB…)"
    predictor = tiff.get(tags, 317, [1])[0]
    if predictor != 1:
        info.extra["Предиктор"] = "горизонтальная разность" if predictor == 2 else f"код {predictor}"
    software = tiff.get(tags, 305)
    if software:
        info.extra["Программа"] = software[0]


def read_exif(data):
    def read_at(position, count):
        if position < 0 or position + count > len(data):
            raise BrokenFile("Exif ссылается за пределы сегмента")
        return data[position:position + count]

    tiff = Tiff(read_at, len(data))
    tags, _ = tiff.read_ifd(tiff.first)
    result = {}
    x = tiff.get(tags, 282)
    if x:
        result["dpi"] = resolution_text(x, tiff.get(tags, 283), tiff.get(tags, 296, [2])[0])
    camera = " ".join(part[0] for part in (tiff.get(tags, 271), tiff.get(tags, 272)) if part)
    if camera:
        result["Камера"] = camera
    orientation = tiff.get(tags, 274)
    if orientation:
        result["Ориентация (Exif)"] = str(orientation[0])
    return result
