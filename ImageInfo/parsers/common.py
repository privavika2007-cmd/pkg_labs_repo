import struct
from dataclasses import dataclass, field

OK = "OK"
BROKEN = "Файл повреждён"
NOT_IMAGE = "Не изображение"
WRONG_EXTENSION = "Расширение не совпадает"
READ_ERROR = "Ошибка чтения"


class BrokenFile(Exception):
    pass


@dataclass
class ImageInfo:
    path: str
    name: str
    file_size: int = 0
    kind: str = ""
    width: int = 0
    height: int = 0
    dpi: str = "—"
    depth: str = "—"
    compression: str = "—"
    status: str = OK
    problem: str = ""
    extra: dict = field(default_factory=dict)

    @property
    def size_text(self):
        if self.width and self.height:
            return f"{self.width} × {self.height}"
        return "—"


class Reader:
    def __init__(self, file, size):
        self.file = file
        self.size = size

    def seek(self, position):
        if position < 0 or position > self.size:
            raise BrokenFile("ссылка за пределы файла")
        self.file.seek(position)

    def tell(self):
        return self.file.tell()

    def read(self, count):
        data = self.file.read(count)
        if len(data) < count:
            raise BrokenFile("неожиданный конец файла")
        return data

    def read_at(self, position, count):
        if position < 0 or position + count > self.size:
            raise BrokenFile("данные выходят за конец файла")
        self.file.seek(position)
        return self.read(count)

    def unpack(self, fmt):
        return struct.unpack(fmt, self.read(struct.calcsize(fmt)))


def dpi_text(x, y):
    x = round(x)
    y = round(y)
    if x <= 0 and y <= 0:
        return "не указано"
    if x == y:
        return f"{x} dpi"
    return f"{x} × {y} dpi"
