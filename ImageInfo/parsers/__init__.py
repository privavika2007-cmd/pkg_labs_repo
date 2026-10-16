import os
import struct

from . import bmp, gif, jpeg, pcx, png, tiff
from .common import (BROKEN, NOT_IMAGE, READ_ERROR, WRONG_EXTENSION, BrokenFile,
                     ImageInfo, Reader)

PARSERS = {
    "BMP": bmp.parse,
    "PNG": png.parse,
    "JPEG": jpeg.parse,
    "GIF": gif.wrap,
    "TIFF": tiff.parse,
    "PCX": pcx.parse,
}

EXTENSIONS = {
    ".bmp": "BMP", ".dib": "BMP",
    ".png": "PNG",
    ".jpg": "JPEG", ".jpeg": "JPEG", ".jpe": "JPEG", ".jfif": "JPEG",
    ".gif": "GIF",
    ".tif": "TIFF", ".tiff": "TIFF",
    ".pcx": "PCX",
}


def detect(head):
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "PNG"
    if head.startswith(b"\xff\xd8\xff"):
        return "JPEG"
    if head[:6] in (b"GIF87a", b"GIF89a"):
        return "GIF"
    if head[:4] in (b"II*\x00", b"MM\x00*", b"II+\x00", b"MM\x00+"):
        return "TIFF"
    if head[:2] == b"BM" and len(head) >= 18:
        return "BMP"
    if len(head) >= 4 and head[0] == 0x0A and head[1] in (0, 2, 3, 4, 5) and head[2] in (0, 1) and head[3] in (1, 2, 4, 8):
        return "PCX"
    return None


def inspect(path):
    info = ImageInfo(path=path, name=os.path.basename(path))
    extension = os.path.splitext(path)[1].lower()
    expected = EXTENSIONS.get(extension)
    try:
        with open(path, "rb") as file:
            info.file_size = os.fstat(file.fileno()).st_size
            if info.file_size == 0:
                info.status = BROKEN
                info.problem = "файл пустой (0 байт)"
                return info
            head = file.read(32)
            info.kind = detect(head) or ""
            if not info.kind:
                info.status = NOT_IMAGE
                if expected:
                    info.problem = f"расширение {extension}, но сигнатура {expected} не найдена — файл переименован или испорчен"
                else:
                    info.problem = "сигнатура не похожа ни на один поддерживаемый формат"
                return info
            reader = Reader(file, info.file_size)
            reader.seek(0)
            PARSERS[info.kind](reader, info)
    except BrokenFile as error:
        info.status = BROKEN
        info.problem = str(error)
    except (struct.error, ValueError, IndexError, OverflowError, UnicodeDecodeError, ZeroDivisionError):
        info.status = BROKEN
        info.problem = "заголовок содержит некорректные значения"
    except OSError as error:
        info.status = READ_ERROR
        info.problem = error.strerror or str(error)
        return info

    if info.kind and expected != info.kind:
        note = f"расширение {extension or '(нет)'}, а по содержимому это {info.kind}"
        if info.status == BROKEN:
            info.problem = f"{info.problem}; {note}"
        else:
            info.status = WRONG_EXTENSION
            info.problem = note
    return info
