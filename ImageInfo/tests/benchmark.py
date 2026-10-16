import os
import sys
import time
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine import Scanner


def main():
    folder = sys.argv[1]
    scanner = Scanner()
    started = time.perf_counter()
    scanner.start([folder])
    rows = []
    while True:
        message = scanner.messages.get()
        if message[0] == "rows":
            rows.extend(message[1])
        elif message[0] == "done":
            break
    elapsed = time.perf_counter() - started
    size = sum(row.file_size for row in rows)
    print(f"файлов: {len(rows)}, объём: {size / 1024 ** 3:.2f} ГБ")
    print(f"время: {elapsed:.2f} с, скорость: {len(rows) / elapsed:.0f} файлов/с")
    print("статусы:", dict(Counter(row.status for row in rows)))


if __name__ == "__main__":
    main()
