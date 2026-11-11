#!/usr/bin/env python3
"""Assemble a CJK-capable Zune 3.3 nk.bin.

Input : an AUTH196 nk.bin (official 3.3 + vault re-wrap) built with the
        zune30-research tooling, plus a compressed CJK font from build_cjk_font.py
Output: a B000FF image where

  * the MTP firmware version string is forced to a known-good value,
  * skin_default.gem is CE-LZX compressed in place (frees ~130 KB),
  * a CJK TTF is stored (compressed) in the freed space,
  * ZegoeUI.ttf / ZegoeUI_L.ttf / ZegoeUI_SB.ttf all point at that font,
  * the ORIGINAL record list is preserved (do not re-chunk: the loader accepts it,
    the OS does not).

Usage:
  python patch_nk.py --base auth196.bin --font-packed font.packed.bin \
      --font-unpacked font.ttf --out nk.CJK.bin

Requires Windows' makecab.exe for the skin compression step.
"""
from __future__ import annotations

import argparse
import struct
import sys
from dataclasses import dataclass
from pathlib import Path

from build_cjk_font import ce_lzx_encode, ce_lzx_verify  # same directory

# ------------------------------------------------------------------ B000FF (CE bin)
@dataclass(frozen=True)
class Record:
    address: int
    data: bytes


@dataclass(frozen=True)
class Image:
    base: int
    span: int
    entry: int
    records: tuple[Record, ...]

    def flatten(self) -> bytes:
        flat = bytearray(self.span)
        for record in self.records:
            start = record.address - self.base
            flat[start:start + len(record.data)] = record.data
        return bytes(flat)


def parse_bin(data: bytes) -> Image:
    if len(data) < 39 or data[:7] != b"B000FF\n":
        raise ValueError("not a CE B000FF container")
    base, span = struct.unpack_from("<II", data, 7)
    at, records, spans = 15, [], []
    while at + 12 <= len(data):
        address, size, checksum = struct.unpack_from("<III", data, at)
        at += 12
        if address == 0:
            if checksum or at != len(data):
                raise ValueError("invalid terminal record")
            return Image(base, span, size, tuple(records))
        if not size or not base <= address < address + size <= base + span or at + size > len(data):
            raise ValueError("out-of-range record")
        if any(max(address, lo) < min(address + size, hi) for lo, hi in spans):
            raise ValueError("overlapping records")
        payload = data[at:at + size]
        if sum(payload) & 0xFFFFFFFF != checksum:
            raise ValueError("record checksum mismatch")
        records.append(Record(address, payload))
        spans.append((address, address + size))
        at += size
    raise ValueError("missing terminal record")


def rebuild(image: Image, flat: bytes) -> bytes:
    """Rebuild with the ORIGINAL record layout (this matters, see docs/06)."""
    out = bytearray(b"B000FF\n" + struct.pack("<II", image.base, len(flat)))
    for record in image.records:
        start = record.address - image.base
        payload = flat[start:start + len(record.data)]
        out += struct.pack("<III", record.address, len(payload), sum(payload) & 0xFFFFFFFF) + payload
    out += struct.pack("<III", 0, image.entry, 0)
    if parse_bin(bytes(out)).flatten() != flat:
        raise RuntimeError("container round-trip mismatch")
    return bytes(out)


# ------------------------------------------------------------------ ROM file table
class Rom:
    """Minimal reader/writer for the CE ROM file table inside a flattened image."""

    def __init__(self, flat: bytearray, base: int):
        self.flat, self.base = flat, base
        self.toc = struct.unpack_from("<I", flat, 0x44)[0] - base
        self.modules = struct.unpack_from("<I", flat, self.toc + 16)[0]
        self.files = struct.unpack_from("<I", flat, self.toc + 48)[0]
        self.first_entry = self.toc + 84 + self.modules * 32

    def _cstr(self, va: int) -> str:
        off = va - self.base
        end = self.flat.find(b"\0", off, off + 256)
        return self.flat[off:end].decode("ascii", "replace")

    def entries(self) -> dict[str, tuple[int, list[int]]]:
        result: dict[str, tuple[int, list[int]]] = {}
        for i in range(self.files):
            off = self.first_entry + i * 28
            entry = list(struct.unpack_from("<7I", self.flat, off))
            result[self._cstr(entry[5])] = (off, entry)
        return result

    def data(self, entry: list[int]) -> bytes:
        start = entry[6] - self.base
        return bytes(self.flat[start:start + entry[4]])

    def set_entry(self, off: int, entry: list[int], *, address: int | None = None,
                  size: int | None = None, compressed: int | None = None) -> None:
        if address is not None:
            entry[6] = self.base + address
        if size is not None:
            entry[3] = size
        if compressed is not None:
            entry[4] = compressed
        entry[0] |= 0x800          # mark as CE-compressed
        struct.pack_into("<7I", self.flat, off, *entry)

    def write(self, address: int, data: bytes) -> None:
        self.flat[address:address + len(data)] = data


# ------------------------------------------------------------------ main
VERSION_FORMAT = "%02d.%02d.%05d.%02d-%05d"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", type=Path, required=True, help="AUTH196 nk.bin")
    ap.add_argument("--font-packed", type=Path, required=True, help="CE-LZX compressed CJK font")
    ap.add_argument("--font-unpacked", type=Path, required=True, help="the same font, uncompressed")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--version-string", default="03.30.00039.00-00435",
                    help="replacement for the MTP firmware version format string")
    ap.add_argument("--skin-compress", action="store_true",
                    help="compress skin_default.gem in place to free contiguous space")
    ap.add_argument("--limit-va", type=lambda s: int(s, 0), default=0xD64784,
                    help="hard upper bound for the font (default: zuneroots.p7b start)")
    ap.add_argument("--makecab", type=Path, default=Path(r"C:\Windows\System32\makecab.exe"))
    ap.add_argument("--decompressor-dir", type=Path, help="optional CE decoder for round-trip checks")
    args = ap.parse_args()

    image = parse_bin(args.base.read_bytes())
    flat = bytearray(image.flatten())
    rom = Rom(flat, image.base)
    entries = rom.entries()

    for required in ("skin_default.gem", "ZegoeUI.ttf", "ZegoeUI_L.ttf", "ZegoeUI_SB.ttf"):
        if required not in entries:
            print(f"ERROR: {required} not found in ROM file table", file=sys.stderr)
            return 2

    # ---- 1) firmware version string -------------------------------------------
    needle = VERSION_FORMAT.encode("utf-16-le")
    pos = flat.find(needle)
    if pos < 0:
        print("WARN: version format string not found, skipping", file=sys.stderr)
    else:
        replacement = args.version_string.encode("utf-16-le")
        if len(replacement) > len(needle):
            print("ERROR: replacement version string is too long", file=sys.stderr)
            return 2
        flat[pos:pos + len(needle)] = replacement + bytes(len(needle) - len(replacement))
        print(f"version string patched at 0x{pos:x} -> {args.version_string}")

    # ---- 2) compress skin_default.gem in place --------------------------------
    font_start_va = None
    if args.skin_compress:
        off, entry = entries["skin_default.gem"]
        skin = rom.data(entry)
        packed = ce_lzx_encode(skin, args.makecab)
        if len(packed) >= len(skin):
            print("ERROR: skin did not compress, refusing", file=sys.stderr)
            return 2
        if args.decompressor_dir and not ce_lzx_verify(packed, skin, args.decompressor_dir):
            print("ERROR: skin compression round-trip failed", file=sys.stderr)
            return 2
        start = entry[6] - image.base
        rom.write(start, packed + bytes(len(skin) - len(packed)))
        rom.set_entry(off, entry, size=len(skin), compressed=len(packed))
        font_start_va = (start + len(packed) + 3) & ~3
        print(f"skin_default.gem: {len(skin):,} -> {len(packed):,}  (font at 0x{font_start_va:x})")
    else:
        # fall back to the tail of the three Zegoe slots
        font_start_va = entries["ZegoeUI.ttf"][1][6] - image.base
        print(f"skin untouched; using the Zegoe slots at 0x{font_start_va:x}")

    # ---- 3) place the font -----------------------------------------------------
    font_packed = args.font_packed.read_bytes()
    font_size = args.font_unpacked.stat().st_size
    font_end_va = font_start_va + len(font_packed)
    if font_end_va > args.limit_va:
        print(f"ERROR: font 0x{font_start_va:x}..0x{font_end_va:x} exceeds limit "
              f"0x{args.limit_va:x}", file=sys.stderr)
        return 2
    rom.write(font_start_va, font_packed)
    print(f"font placed       : 0x{font_start_va:x}..0x{font_end_va:x}  ({len(font_packed):,} B)")

    # ---- 4) repoint the three faces -------------------------------------------
    for face in ("ZegoeUI.ttf", "ZegoeUI_L.ttf", "ZegoeUI_SB.ttf"):
        off, entry = entries[face]
        rom.set_entry(off, entry, address=font_start_va, size=font_size,
                      compressed=len(font_packed))
        print(f"  {face:<14} -> 0x{font_start_va:x}  ({font_size:,} B uncompressed)")

    # ---- 5) rebuild ------------------------------------------------------------
    result = rebuild(image, bytes(flat))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(result)
    print(f"written           : {args.out}  ({len(result):,} B)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
