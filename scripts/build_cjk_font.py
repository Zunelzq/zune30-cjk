#!/usr/bin/env python3
"""Build a CE-ROM-sized CJK font subset for the Zune 3.3 shell.

The Zune 3.3 shell (gemstone.exe / XUI) loads its UI faces from three ROM files
(\\Windows\\ZegoeUI.ttf, _L.ttf, _SB.ttf). To make it render CJK we replace those
files with one compressed TrueType face that contains the glyphs we need.

This script:
  * subsets a source TTF to ASCII + kana + the Han characters you list,
  * strips hinting (required: hints roughly double the size),
  * renames the face so it matches the registry entry it replaces,
  * compresses it with the CE LZX variant (4096-byte blocks only),
  * refuses to write output larger than --limit bytes.

Usage:
  python build_cjk_font.py --font simsun.ttf --charset charset.txt \
      --limit 180600 --family "Zegoe UI Semibold" \
      --out font.ttf --out-packed font.packed.bin

charset.txt: UTF-8 text, one or more characters per line is fine; duplicates ignored.
Requires: fonttools.  Compression requires Windows' makecab.exe.
Verification (optional): --decompressor-dir pointing at a directory that contains
wincedecompr.py (from the zune30-research project) or wince_decompr/wincedecompr.py.
"""
from __future__ import annotations

import argparse
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

BLOCK = 4096  # the CE decoder used by this device only accepts 4096-byte blocks


# ---------------------------------------------------------------- CE LZX (encode)
def ce_lzx_encode(data: bytes, makecab: Path = Path(r"C:\Windows\System32\makecab.exe")) -> bytes:
    """Produce a CE-ROM compressed stream (LZX, 4096-byte blocks)."""
    chunks: list[bytes] = []
    with tempfile.TemporaryDirectory(prefix="ce-lzx-") as tmp:
        root = Path(tmp)
        for index in range(0, len(data), BLOCK):
            block = data[index:index + BLOCK]
            src, dst = root / "in.dat", root / "out.cab"
            src.write_bytes(block)
            if dst.exists():
                dst.unlink()
            proc = subprocess.run(
                [str(makecab), "/D", "CompressionType=LZX", "/D", "CompressionMemory=15",
                 str(src), str(dst)],
                capture_output=True,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if proc.returncode:
                raise RuntimeError(f"makecab failed ({proc.returncode})")
            cab = dst.read_bytes()
            if cab[:4] != b"MSCF":
                raise RuntimeError("makecab produced an invalid CAB")
            offset, blocks, compression = struct.unpack_from("<IHH", cab, 36)
            if blocks != 1 or compression != (15 << 8) | 3:
                raise RuntimeError("unexpected LZX block layout")
            _, compressed, uncompressed = struct.unpack_from("<IHH", cab, offset)
            payload = cab[offset + 8:offset + 8 + compressed]
            if uncompressed != len(block) or len(payload) != compressed:
                raise RuntimeError("CAB payload length mismatch")
            chunks.append(struct.pack("<4I", 15, len(block), len(payload), len(block)) + payload)

    position = (len(chunks) + 1) * 3
    table = [len(data)]
    for chunk in chunks:
        position += len(chunk)
        table.append(position)
    return b"".join(n.to_bytes(3, "little") for n in table) + b"".join(chunks)


def ce_lzx_verify(packed: bytes, data: bytes, decompressor_dir: Path) -> bool:
    """Optional round-trip check using the community CE decoder (not bundled)."""
    import importlib.util

    for candidate in (decompressor_dir / "wincedecompr.py",
                      decompressor_dir / "wince_decompr" / "wincedecompr.py"):
        if candidate.is_file():
            spec = importlib.util.spec_from_file_location("local_ce_decoder", candidate)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            out = bytearray(len(data) + 4096)
            count = module.CEDecompressROM(packed, len(packed), out, len(data), 0, 1, BLOCK)
            return count == len(data) and bytes(out[:count]) == data
    raise FileNotFoundError("wincedecompr.py not found in --decompressor-dir")


# ---------------------------------------------------------------- font subsetting
def build_font(font_path: Path, chars: set[str], family: str, keep_hinting: bool = False) -> bytes:
    from fontTools import subset
    from fontTools.ttLib import TTFont

    opts = subset.Options()
    # Hinting is what makes small CJK text look sharp on the device. It roughly doubles
    # the file size, which does not matter on the FontLink path (the font lives on disk),
    # but does matter on the ROM-replacement path (see docs/06-rom-space.md).
    opts.hinting = keep_hinting
    opts.drop_tables += ["GSUB", "kern", "vhea", "vmtx"]
    if not keep_hinting:
        opts.drop_tables += ["cvt ", "fpgm", "prep", "gasp"]

    font = subset.load_font(str(font_path), opts)
    subsetter = subset.Subsetter(options=opts)
    subsetter.populate(text="".join(sorted(chars)))
    subsetter.subset(font)

    for record in font["name"].names:
        if record.nameID == 1:
            record.string = family
        elif record.nameID == 2:
            record.string = "Regular"
        elif record.nameID == 4:
            record.string = family
        elif record.nameID == 6:
            record.string = family.replace(" ", "")
        elif record.nameID == 16:
            record.string = family
        elif record.nameID == 17:
            record.string = "Regular"

    with tempfile.TemporaryDirectory(prefix="cjk-ttf-") as tmp:
        out = Path(tmp) / "font.ttf"
        font.save(str(out))
        return out.read_bytes()


def default_charset() -> set[str]:
    chars = {chr(c) for c in range(0x20, 0x7F)}           # ASCII
    chars |= {chr(c) for c in range(0x3040, 0x30FF)}      # hiragana + katakana
    chars |= set("　、。・「」『』【】〈〉《》（）—…～·♪★☆")
    return chars


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--font", type=Path, required=True, help="source TTF/OTF you are licensed to use")
    ap.add_argument("--charset", type=Path, help="UTF-8 text with the Han characters you need")
    ap.add_argument("--limit", type=int, default=180600, help="max compressed size in bytes")
    ap.add_argument("--keep-hinting", action="store_true",
                    help="keep TrueType hinting (sharper small text, ~2x size; use this on the FontLink path)")
    ap.add_argument("--family", default="Zegoe UI Semibold", help="family name to embed")
    ap.add_argument("--out", type=Path, required=True, help="uncompressed TTF output")
    ap.add_argument("--out-packed", type=Path, required=True, help="CE-LZX compressed output")
    ap.add_argument("--makecab", type=Path, default=Path(r"C:\Windows\System32\makecab.exe"))
    ap.add_argument("--decompressor-dir", type=Path, help="optional: verify round-trip")
    args = ap.parse_args()

    chars = default_charset()
    if args.charset:
        chars |= set(args.charset.read_text(encoding="utf-8"))

    ttf = build_font(args.font, chars, args.family, keep_hinting=args.keep_hinting)
    packed = ce_lzx_encode(ttf, args.makecab)

    size_ok = len(packed) <= args.limit
    print(f"glyph-capable chars : {len(chars)}")
    print(f"TTC/TTF            : {len(ttf):,} B")
    print(f"CE-LZX             : {len(packed):,} B  (limit {args.limit:,})")
    print(f"fits               : {size_ok}")

    if args.decompressor_dir:
        print(f"round-trip verify  : {ce_lzx_verify(packed, ttf, args.decompressor_dir)}")

    if not size_ok:
        print("ERROR: over the limit — remove characters with --charset or use a smaller face.",
              file=sys.stderr)
        return 2

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(ttf)
    args.out_packed.parent.mkdir(parents=True, exist_ok=True)
    args.out_packed.write_bytes(packed)
    print(f"written            : {args.out} , {args.out_packed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
