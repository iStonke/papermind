#!/usr/bin/env python3
"""Erzeugt waehrend eines SANE-PNM-Scans eine kleine, atomare PNG-Vorschau.

Der Helfer liest nur bereits vollstaendig geschriebene Bildzeilen. Noch nicht
gescannte Bereiche bleiben weiss, sodass die Vorschau in der App in derselben
Geometrie wie die fertige A4-Seite von oben nach unten aufgebaut wird.
"""

from __future__ import annotations

import argparse
import math
import os
import struct
import time
import zlib
from pathlib import Path


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _process_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _read_token(handle) -> bytes:
    token = bytearray()
    while True:
        char = handle.read(1)
        if not char:
            raise EOFError("PNM header is incomplete")
        if char == b"#":
            handle.readline()
            continue
        if not char.isspace():
            token.extend(char)
            break
    while True:
        char = handle.read(1)
        if not char:
            raise EOFError("PNM header is incomplete")
        if char.isspace():
            return bytes(token)
        token.extend(char)


def read_pnm_header(path: Path) -> dict[str, int | bytes]:
    with path.open("rb") as handle:
        magic = _read_token(handle)
        if magic not in {b"P4", b"P5", b"P6"}:
            raise ValueError(f"Unsupported PNM format: {magic!r}")
        width = int(_read_token(handle))
        height = int(_read_token(handle))
        max_value = 1 if magic == b"P4" else int(_read_token(handle))
        if width <= 0 or height <= 0 or max_value <= 0 or max_value > 65535:
            raise ValueError("Invalid PNM dimensions")
        channels = 3 if magic == b"P6" else 1
        bytes_per_sample = 2 if max_value > 255 else 1
        row_bytes = math.ceil(width / 8) if magic == b"P4" else width * channels * bytes_per_sample
        return {
            "magic": magic,
            "width": width,
            "height": height,
            "max_value": max_value,
            "bytes_per_sample": bytes_per_sample,
            "row_bytes": row_bytes,
            "data_offset": handle.tell(),
        }


def _scale_sample(value: int, max_value: int) -> int:
    if max_value == 255:
        return value
    return max(0, min(255, round(value * 255 / max_value)))


def _sample_row(raw: bytes, header: dict[str, int | bytes], step: int) -> bytes:
    magic = header["magic"]
    width = int(header["width"])
    max_value = int(header["max_value"])
    bytes_per_sample = int(header["bytes_per_sample"])
    output = bytearray()
    for x in range(0, width, step):
        if magic == b"P4":
            # P4: 1 = schwarz, 0 = weiss, most-significant bit zuerst.
            value = 0 if raw[x // 8] & (0x80 >> (x % 8)) else 255
            output.extend((value, value, value))
            continue
        channels = 3 if magic == b"P6" else 1
        offset = x * channels * bytes_per_sample
        values = []
        for channel in range(channels):
            sample_offset = offset + channel * bytes_per_sample
            if bytes_per_sample == 1:
                sample = raw[sample_offset]
            else:
                sample = int.from_bytes(raw[sample_offset : sample_offset + 2], "big")
            values.append(_scale_sample(sample, max_value))
        if channels == 1:
            output.extend((values[0], values[0], values[0]))
        else:
            output.extend(values)
    return bytes(output)


def _png_chunk(kind: bytes, payload: bytes) -> bytes:
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)


def write_rgb_png(path: Path, width: int, height: int, rows: list[bytes]) -> None:
    white_row = b"\xff" * (width * 3)
    raw = bytearray()
    for index in range(height):
        raw.append(0)  # PNG filter: None
        raw.extend(rows[index] if index < len(rows) else white_row)
    payload = bytearray(PNG_SIGNATURE)
    payload.extend(_png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)))
    payload.extend(_png_chunk(b"IDAT", zlib.compress(bytes(raw), level=3)))
    payload.extend(_png_chunk(b"IEND", b""))
    temp = path.with_name(f"{path.name}.incoming")
    temp.write_bytes(payload)
    temp.replace(path)


def write_status(path: Path, *, progress: int, revision: int, width: int, height: int) -> None:
    temp = path.with_name(f"{path.name}.incoming")
    temp.write_text(
        f"PROGRESS={progress}\nREVISION={revision}\nWIDTH={width}\nHEIGHT={height}\n",
        encoding="utf-8",
    )
    temp.replace(path)


def render_loop(
    source: Path,
    preview: Path,
    status: Path,
    scan_pid: int,
    *,
    interval: float = 0.5,
    max_width: int = 640,
) -> None:
    header = None
    while header is None:
        try:
            header = read_pnm_header(source)
        except (FileNotFoundError, EOFError):
            if not _process_alive(scan_pid):
                return
            time.sleep(0.05)

    width = int(header["width"])
    height = int(header["height"])
    row_bytes = int(header["row_bytes"])
    data_offset = int(header["data_offset"])
    step = max(1, math.ceil(width / max_width))
    output_width = math.ceil(width / step)
    output_height = math.ceil(height / step)
    sampled_rows: list[bytes] = []
    next_source_row = 0
    revision = 0

    while True:
        try:
            available_bytes = max(0, source.stat().st_size - data_offset)
        except FileNotFoundError:
            available_bytes = 0
        available_rows = min(height, available_bytes // row_bytes)

        if available_rows > next_source_row:
            with source.open("rb") as handle:
                while next_source_row < available_rows:
                    handle.seek(data_offset + next_source_row * row_bytes)
                    raw = handle.read(row_bytes)
                    if len(raw) != row_bytes:
                        break
                    sampled_rows.append(_sample_row(raw, header, step))
                    next_source_row += step

            revision += 1
            progress = min(100, round(available_rows * 100 / height))
            write_rgb_png(preview, output_width, output_height, sampled_rows)
            write_status(
                status,
                progress=progress,
                revision=revision,
                width=output_width,
                height=output_height,
            )

        alive = _process_alive(scan_pid)
        if not alive:
            # Nach Prozessende einmal alle vom Kernel gepufferten Zeilen lesen.
            try:
                final_rows = max(0, source.stat().st_size - data_offset) // row_bytes
            except FileNotFoundError:
                final_rows = 0
            if available_rows >= min(height, final_rows):
                return
        time.sleep(max(0.1, interval))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("preview", type=Path)
    parser.add_argument("status", type=Path)
    parser.add_argument("scan_pid", type=int)
    parser.add_argument("--interval", type=float, default=0.5)
    parser.add_argument("--max-width", type=int, default=640)
    args = parser.parse_args()
    render_loop(
        args.source,
        args.preview,
        args.status,
        args.scan_pid,
        interval=args.interval,
        max_width=max(64, min(args.max_width, 1280)),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
