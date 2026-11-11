#!/usr/bin/env python3
"""Patch the fixed font-size constant inside ZCJKBoot.exe (the native CE font loader).

The upstream loader shipped with `1977899016-cell/zune30-research` hard-codes
GetFileSize(...) == 8,206,424. That is a plain 32-bit literal in a pool inside the
2 KB binary, so any other font size can be supported by rewriting it.

Usage:
    python patch_loader.py --in ZCJKBoot.exe --size 1945600 --out ZCJKBoot_1.9MB.exe
    python patch_loader.py --in ZCJKBoot.exe --size 1945600 --out out.exe --show

Requires: nothing (pure stdlib).
"""
from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

UPSTREAM_SIZE = 8_206_424


def find_constant(data: bytes, value: int) -> list[int]:
    pattern = struct.pack("<I", value)
    hits, at = [], data.find(pattern)
    while at >= 0:
        hits.append(at)
        at = data.find(pattern, at + 1)
    return hits


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--in", dest="src", type=Path, required=True, help="original ZCJKBoot.exe")
    ap.add_argument("--size", type=int, required=True, help="your font file size in bytes")
    ap.add_argument("--out", type=Path, required=True, help="patched loader")
    ap.add_argument("--offset", type=lambda s: int(s, 0),
                    help="explicit offset of the constant (default: auto-detect 8206424)")
    ap.add_argument("--show", action="store_true", help="only report offsets, do not write")
    args = ap.parse_args()

    data = bytearray(args.src.read_bytes())
    if args.offset is not None:
        offsets = [args.offset]
    else:
        offsets = find_constant(data, UPSTREAM_SIZE)
        if len(offsets) != 1:
            print(f"expected exactly one {UPSTREAM_SIZE} literal, found {len(offsets)}: "
                  f"{[hex(o) for o in offsets]}", file=sys.stderr)
            print("pass --offset 0x... explicitly (see --show)", file=sys.stderr)
            return 2

    for off in offsets:
        print(f"size constant at 0x{off:x}: {struct.unpack_from('<I', data, off)[0]:,}")

    if args.show:
        return 0

    if not 1 <= args.size <= 64 * 1024 * 1024:
        print("size must be 1..64 MiB", file=sys.stderr)
        return 2

    for off in offsets:
        struct.pack_into("<I", data, off, args.size)
        print(f"patched 0x{off:x} -> {args.size:,}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(bytes(data))
    print(f"written: {args.out}  ({len(data)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
