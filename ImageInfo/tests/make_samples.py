import json
import os
import struct
import sys

from PIL import Image

FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "samples")


def picture(mode, size=(64, 48)):
    image = Image.new("RGB", size)
    for x in range(size[0]):
        for y in range(size[1]):
            image.putpixel((x, y), (x * 4 % 256, y * 5 % 256, (x + y) * 3 % 256))
    if mode == "RGB":
        return image
    if mode == "P":
        return image.quantize(256)
    if mode == "P16":
        return image.quantize(16)
    return image.convert(mode)


def save(manifest, name, image, expected, **options):
    path = os.path.join(FOLDER, name)
    image.save(path, **options)
    manifest[name] = expected


def bmp_rle8(path, width=32, height=16):
    rows = b""
    for y in range(height):
        rows += bytes([width, y * 10 % 256, 0, 0])
    rows += b"\x00\x01"
    palette = b"".join(bytes([i, i, i, 0]) for i in range(256))
    offset = 14 + 40 + len(palette)
    header = struct.pack("<2sIHHI", b"BM", offset + len(rows), 0, 0, offset)
    info = struct.pack("<IiiHHIIiiII", 40, width, height, 1, 8, 1, len(rows), 3780, 3780, 256, 0)
    with open(path, "wb") as file:
        file.write(header + info + palette + rows)


def bmp_565(path, width=10, height=4):
    row = (width * 16 + 31) // 32 * 4
    pixels = b"\x1f\xf8" * width + b"\x00" * (row - width * 2)
    masks = struct.pack("<III", 0xF800, 0x07E0, 0x001F)
    offset = 14 + 40 + 12
    size = offset + row * height
    header = struct.pack("<2sIHHI", b"BM", size, 0, 0, offset)
    info = struct.pack("<IiiHHIIiiII", 40, width, -height, 1, 16, 3, row * height, 2835, 2835, 0, 0)
    with open(path, "wb") as file:
        file.write(header + info + masks + pixels * height)


def cut(source, target, keep):
    with open(os.path.join(FOLDER, source), "rb") as file:
        data = file.read()
    with open(os.path.join(FOLDER, target), "wb") as file:
        file.write(data[:keep] if keep > 0 else data[:len(data) + keep])


def main():
    os.makedirs(FOLDER, exist_ok=True)
    manifest = {}

    save(manifest, "bmp_1bit.bmp", picture("1"), {"kind": "BMP", "bits": 1, "dpi": 96, "compression": "BI_RGB"}, dpi=(96, 96))
    save(manifest, "bmp_4bit.bmp", picture("P16"), {"kind": "BMP", "bits": 8, "compression": "BI_RGB"})
    save(manifest, "bmp_8bit_gray.bmp", picture("L"), {"kind": "BMP", "bits": 8, "compression": "BI_RGB"})
    save(manifest, "bmp_24bit_300dpi.bmp", picture("RGB"), {"kind": "BMP", "bits": 24, "dpi": 300, "compression": "BI_RGB"}, dpi=(300, 300))
    save(manifest, "bmp_32bit.bmp", picture("RGBA"), {"kind": "BMP", "bits": 32})
    bmp_rle8(os.path.join(FOLDER, "bmp_rle8.bmp"))
    manifest["bmp_rle8.bmp"] = {"kind": "BMP", "bits": 8, "dpi": 96, "compression": "BI_RLE8"}
    bmp_565(os.path.join(FOLDER, "bmp_16bit_565.bmp"))
    manifest["bmp_16bit_565.bmp"] = {"kind": "BMP", "bits": 16, "compression": "BI_BITFIELDS", "width": 10, "height": 4}

    save(manifest, "png_rgb_72dpi.png", picture("RGB"), {"kind": "PNG", "bits": 24, "dpi": 72, "compression": "Deflate"}, dpi=(72, 72))
    save(manifest, "png_rgba.png", picture("RGBA"), {"kind": "PNG", "bits": 32})
    save(manifest, "png_gray_1bit.png", picture("1"), {"kind": "PNG", "bits": 1})
    save(manifest, "png_palette.png", picture("P"), {"kind": "PNG", "bits": 8})
    save(manifest, "png_gray16.png", picture("I;16"), {"kind": "PNG", "bits": 16})
    save(manifest, "png_interlaced.png", picture("RGB"), {"kind": "PNG", "bits": 24}, interlace=1)

    save(manifest, "jpeg_baseline_300dpi.jpg", picture("RGB"), {"kind": "JPEG", "bits": 24, "dpi": 300, "compression": "Baseline"}, dpi=(300, 300), quality=90)
    save(manifest, "jpeg_progressive.jpg", picture("RGB"), {"kind": "JPEG", "bits": 24, "compression": "Progressive"}, progressive=True, quality=75)
    save(manifest, "jpeg_gray.jpg", picture("L"), {"kind": "JPEG", "bits": 8, "compression": "Baseline"})
    save(manifest, "jpeg_cmyk.jpg", picture("CMYK"), {"kind": "JPEG", "bits": 32, "compression": "Baseline"})
    exif = Image.Exif()
    exif[282] = 240
    exif[283] = 240
    exif[296] = 2
    exif[271] = "TestCam"
    exif[272] = "Model X"
    image = picture("RGB")
    path = os.path.join(FOLDER, "jpeg_exif_240dpi.jpg")
    image.save(path, exif=exif.tobytes(), quality=85)
    with open(path, "rb") as file:
        data = file.read()
    start = data.find(b"\xff\xe0")
    if start == 2:
        length = int.from_bytes(data[4:6], "big")
        data = data[:2] + data[4 + length:]
    with open(path, "wb") as file:
        file.write(data)
    manifest["jpeg_exif_240dpi.jpg"] = {"kind": "JPEG", "bits": 24, "dpi": 240}

    save(manifest, "gif_static.gif", picture("P"), {"kind": "GIF", "bits": 8, "compression": "LZW"})
    frames = [picture("RGB").rotate(angle).quantize(64) for angle in (0, 90, 180)]
    path = os.path.join(FOLDER, "gif_animated.gif")
    frames[0].save(path, save_all=True, append_images=frames[1:], loop=0, duration=100)
    manifest["gif_animated.gif"] = {"kind": "GIF", "frames": 3, "compression": "LZW"}

    save(manifest, "tiff_raw_150dpi.tif", picture("RGB"), {"kind": "TIFF", "bits": 24, "dpi": 150, "compression": "без сжатия"}, dpi=(150, 150))
    save(manifest, "tiff_lzw.tif", picture("RGB"), {"kind": "TIFF", "bits": 24, "compression": "LZW"}, compression="tiff_lzw")
    save(manifest, "tiff_deflate.tif", picture("RGBA"), {"kind": "TIFF", "bits": 32, "compression": "Deflate"}, compression="tiff_adobe_deflate")
    save(manifest, "tiff_packbits_gray.tif", picture("L"), {"kind": "TIFF", "bits": 8, "compression": "PackBits"}, compression="packbits")
    save(manifest, "tiff_cmyk.tif", picture("CMYK"), {"kind": "TIFF", "bits": 32})
    save(manifest, "tiff_g4_1bit.tif", picture("1"), {"kind": "TIFF", "bits": 1, "compression": "Group 4"}, compression="group4")
    pages = [picture("RGB"), picture("L"), picture("1")]
    path = os.path.join(FOLDER, "tiff_3pages.tif")
    pages[0].save(path, save_all=True, append_images=pages[1:])
    manifest["tiff_3pages.tif"] = {"kind": "TIFF", "pages": 3}

    save(manifest, "pcx_8bit.pcx", picture("P"), {"kind": "PCX", "bits": 8, "compression": "RLE"})
    save(manifest, "pcx_24bit.pcx", picture("RGB"), {"kind": "PCX", "bits": 24, "compression": "RLE"})
    save(manifest, "pcx_1bit.pcx", picture("1"), {"kind": "PCX", "bits": 1, "compression": "RLE"})

    cut("png_rgb_72dpi.png", "broken_png_no_iend.png", -12)
    manifest["broken_png_no_iend.png"] = {"status": "Файл повреждён", "problem": "IEND"}
    cut("jpeg_baseline_300dpi.jpg", "broken_jpeg_no_eoi.jpg", -400)
    manifest["broken_jpeg_no_eoi.jpg"] = {"status": "Файл повреждён", "problem": "EOI"}
    cut("bmp_24bit_300dpi.bmp", "broken_bmp_short.bmp", -1000)
    manifest["broken_bmp_short.bmp"] = {"status": "Файл повреждён", "problem": "меньше"}
    cut("gif_animated.gif", "broken_gif_cut.gif", -200)
    manifest["broken_gif_cut.gif"] = {"status": "Файл повреждён", "problem": "0x3B"}
    cut("tiff_raw_150dpi.tif", "broken_tiff_cut.tif", 600)
    manifest["broken_tiff_cut.tif"] = {"status": "Файл повреждён"}
    cut("pcx_8bit.pcx", "broken_pcx_no_palette.pcx", -769)
    manifest["broken_pcx_no_palette.pcx"] = {"status": "Файл повреждён", "problem": "палитры"}
    cut("png_rgb_72dpi.png", "broken_png_header_only.png", 20)
    manifest["broken_png_header_only.png"] = {"status": "Файл повреждён"}
    with open(os.path.join(FOLDER, "empty.jpg"), "wb"):
        pass
    manifest["empty.jpg"] = {"status": "Файл повреждён", "problem": "пустой"}

    with open(os.path.join(FOLDER, "text_renamed.jpg"), "w", encoding="utf-8") as file:
        file.write("Это обычный текстовый файл, переименованный в jpg.\n" * 20)
    manifest["text_renamed.jpg"] = {"status": "Не изображение"}
    cut("png_rgb_72dpi.png", "png_renamed.jpg", 10 ** 9)
    manifest["png_renamed.jpg"] = {"kind": "PNG", "status": "Расширение не совпадает"}
    cut("bmp_8bit_gray.bmp", "bmp_renamed.gif", 10 ** 9)
    manifest["bmp_renamed.gif"] = {"kind": "BMP", "status": "Расширение не совпадает"}

    with open(os.path.join(FOLDER, "manifest.json"), "w", encoding="utf-8") as file:
        json.dump(manifest, file, ensure_ascii=False, indent=1)
    print(f"создано файлов: {len(manifest)} в {FOLDER}")


if __name__ == "__main__":
    sys.exit(main())
