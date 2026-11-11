#!/usr/bin/env python3
"""Build a Zune 3.3 nk.bin that enables CJK text through GDI FontLink.

The Zune 3.3 shell (gemstone.exe) renders text through the system GDI, whose
FontLink mechanism falls back to another font for missing glyphs. This script
wires that up:

  1. adds HKLM\\SOFTWARE\\Microsoft\\FontLink\\SystemLink entries for the three
     UI faces, pointing at a CJK font on the data volume;
  2. adds an HKLM\\init entry that starts the native loader before the shell;
  3. compresses the registry (CE LZX, 4096-byte blocks) and writes it in place
     over the ROM's default.fdf slot (it must fit — no relocation);
  4. patches the firmware version format string so the Zune client stops
     thinking the firmware is outdated;
  5. rebuilds the B000FF container keeping the ORIGINAL record list.

Registry editing is delegated to the upstream project:
  1977899016-cell/zune30-research  ->  tools/prepare_registry.py  (MIT)
Pass --research-dir pointing at a clone of that repository.

Usage:
  python build_image.py --research-dir ..\\zune30-research \\
      --base auth196.bin --fdf-in default.fdf --out nk.CJK.bin

  python build_image.py ... --version-string ""      # skip the version patch

Requires Windows' makecab.exe for the CE LZX step.
"""
from __future__ import annotations

import argparse
import struct
import sys
from dataclasses import dataclass
from pathlib import Path

# ---- CE LZX encoder (shared with build_cjk_font.py) --------------------------
sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_cjk_font import ce_lzx_encode  # noqa: E402

ROM_BASE_DEFAULT = 0x88200000
FONT_LINK_KEY = r"software\microsoft\fontlink\systemlink"
UI_FACES = ("Zegoe UI", "Zegoe UI Light", "Zegoe UI Semibold")
VERSION_FORMAT = "%02d.%02d.%05d.%02d-%05d"


# ---- B000FF container --------------------------------------------------------
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
    out = bytearray(b"B000FF\n" + struct.pack("<II", image.base, len(flat)))
    for record in image.records:
        start = record.address - image.base
        payload = flat[start:start + len(record.data)]
        out += struct.pack("<III", record.address, len(payload), sum(payload) & 0xFFFFFFFF) + payload
    out += struct.pack("<III", 0, image.entry, 0)
    if parse_bin(bytes(out)).flatten() != flat:
        raise RuntimeError("container round-trip mismatch")
    return bytes(out)


# ---- ROM file table ----------------------------------------------------------
class RomTable:
    def __init__(self, flat: bytearray, base: int):
        self.flat, self.base = flat, base
        self.toc = struct.unpack_from("<I", flat, 0x44)[0] - base
        self.modules = struct.unpack_from("<I", flat, self.toc + 16)[0]
        self.files = struct.unpack_from("<I", flat, self.toc + 48)[0]
        self.first = self.toc + 84 + self.modules * 32

    def _cstr(self, va: int) -> str:
        off = va - self.base
        end = self.flat.find(b"\0", off, off + 256)
        return self.flat[off:end].decode("ascii", "replace")

    def entries(self) -> dict[str, tuple[int, list[int]]]:
        out = {}
        for i in range(self.files):
            off = self.first + i * 28
            entry = list(struct.unpack_from("<7I", self.flat, off))
            out[self._cstr(entry[5])] = (off, entry)
        return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--research-dir", type=Path, required=True,
                    help="clone of 1977899016-cell/zune30-research (uses tools/prepare_registry.py)")
    ap.add_argument("--base", type=Path, required=True, help="AUTH196 nk.bin (official 3.3 + vault re-wrap)")
    ap.add_argument("--fdf-in", type=Path, required=True, help="uncompressed default.fdf from that image")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--font-path", default=r"\Hard Disk\Fonts\ZuneCJK_UI_20261027.ttf",
                    help="path the device will use (\\Hard Disk = the 150 MB system partition)")
    ap.add_argument("--font-family", default="Zune UI CJK")
    ap.add_argument("--loader-path", default=r"\Hard Disk\Fonts\ZCJKBoot.exe")
    ap.add_argument("--version-string", default="03.30.00039.00-00435",
                    help='replace the firmware version format string; "" to skip')
    ap.add_argument("--makecab", type=Path, default=Path(r"C:\Windows\System32\makecab.exe"))
    args = ap.parse_args()

    # ---- registry ------------------------------------------------------------
    sys.path.insert(0, str(args.research_dir / "tools"))
    try:
        import prepare_registry as pr  # upstream, MIT
    except ImportError:
        print("cannot import prepare_registry from --research-dir/tools", file=sys.stderr)
        return 2

    blob = args.fdf_in.read_bytes()
    changes = {face.lower(): pr.value(face, f"{args.font_path},{args.font_family}") for face in UI_FACES}
    blob = pr.update_key(blob, FONT_LINK_KEY, changes)

    values = pr.values(blob)
    dep_type, dep_data = values.get((2, "init", "depend60"), (3, b""))
    deps = list(dict.fromkeys(list(struct.unpack("<" + "H" * (len(dep_data) // 2), dep_data)) + [20, 45]))
    blob = pr.update_key(blob, "init", {
        "launch45": pr.value("Launch45", args.loader_path),
        "depend45": pr.value("Depend45", struct.pack("<H", 30), 3),
        "depend60": pr.value("Depend60", struct.pack("<" + "H" * len(deps), *deps), 3),
    })
    graph = pr.init_graph(blob)
    if not graph["passed"]:
        print(f"init dependency graph failed: {graph['blocked']}", file=sys.stderr)
        return 2
    print(f"registry: {len(blob):,} bytes, launch order {graph['launch_order']}")

    packed = ce_lzx_encode(blob, args.makecab)
    print(f"registry compressed: {len(packed):,} bytes")

    # ---- image ---------------------------------------------------------------
    image = parse_bin(args.base.read_bytes())
    flat = bytearray(image.flatten())
    rom = RomTable(flat, image.base)
    entries = rom.entries()

    off, entry = entries.get("default.fdf", (None, None))
    if off is None:
        print("default.fdf not found in the ROM file table", file=sys.stderr)
        return 2
    slot = entry[4]
    if len(packed) > slot:
        print(f"ERROR: registry needs {len(packed):,} B but the slot is {slot:,} B.\n"
              f"       This builder deliberately does not relocate the registry.\n"
              f"       Reduce the number of FontLink faces or shorten --font-path.",
              file=sys.stderr)
        return 3
    start = entry[6] - image.base
    flat[start:start + slot] = packed + bytes(slot - len(packed))
    entry[3], entry[4], entry[0] = len(blob), len(packed), entry[0] | 0x800
    struct.pack_into("<7I", flat, off, *entry)
    print(f"default.fdf: {len(blob):,} -> {len(packed):,} (slot {slot:,})")

    if args.version_string:
        needle = VERSION_FORMAT.encode("utf-16-le")
        at = flat.find(needle)
        if at < 0:
            print("WARN: version format string not found, skipped")
        else:
            repl = args.version_string.encode("utf-16-le")
            if len(repl) > len(needle):
                print("ERROR: --version-string too long", file=sys.stderr)
                return 2
            flat[at:at + len(needle)] = repl + bytes(len(needle) - len(repl))
            print(f"version string patched at 0x{at:x} -> {args.version_string}")

    result = rebuild(image, bytes(flat))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(result)
    print(f"written: {args.out}  ({len(result):,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
