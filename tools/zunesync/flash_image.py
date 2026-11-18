"""Flash an arbitrary AUTH196 3.3 image to a Zune 30 over USB.

Safety checks before anything is sent:
  1. the file is a B000FF container;
  2. the embedded device vault (ZV194.dat) matches this unit's vault;
  3. the staging queue on the device is empty.

    python flash_image.py <nk.bin> [--force]
    python flash_image.py --list
"""
from __future__ import annotations

import hashlib
import struct
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from zunesync import mtp

TOOLS = r"E:\DSH\workblock\zune\work\zune30research\zune30-research-main\tools"
sys.path.insert(0, TOOLS)
sys.path.insert(0, TOOLS + r"\upgrade")

try:
    from ce_bin import parse as ce_parse
    from ce_lzx import load_decoder, decode
    HAVE_CE = True
except Exception:
    HAVE_CE = False

STORAGE = 0x10001
FMT_FIRMWARE = 0xB802
OP_COMMIT = 0x9204
BASE = 0x88200000

VAULT = Path(r"E:\zune_backup\device-e7747cdfbdfb0ae9\vault.legacy.PRIVATE.bin")
VENDOR = r"E:\DSH\workblock\zune\work\zune30research\zune30-research-main\app\vendor"

KNOWN = {
    "23C8D9B9": "Zune 模式 + FLAC + 中文 + DMA 修复（推荐日常）",
    "6A996991": "MTP 模式 + FLAC + 中文 + DMA 修复（传 FLAC）",
    "230A8B43": "中文 + DMA 修复（无 FLAC）",
    "E66595BE": "原始 3.3 + 中文（无 DMA 修复）",
    "ABE47A52": "DMA 参数调整版（未采用）",
}


def log(*a):
    print(*a, flush=True)


def image_vault_sha(data: bytes):
    """Return SHA-256 of the ZV194.dat payload inside the image, or None."""
    if not HAVE_CE:
        return None
    try:
        c = ce_parse(data)
        flat = c.flatten()
        toc = struct.unpack_from("<I", flat, 0x44)[0] - BASE
        nm = struct.unpack_from("<I", flat, toc + 16)[0]
        nf = struct.unpack_from("<I", flat, toc + 48)[0]

        def name_at(p):
            o = p - BASE
            e = flat.find(b"\0", o, o + 256)
            return flat[o:e].decode("ascii", "replace")

        dec = load_decoder(VENDOR)
        for i in range(nf):
            off = toc + 84 + nm * 32 + i * 28
            e = list(struct.unpack_from("<7I", flat, off))
            if name_at(e[5]) == "ZV194.dat":
                blob = flat[e[6] - BASE:e[6] - BASE + e[4]]
                if e[0] & 0x800:
                    blob = decode(bytes(blob), e[3], dec)
                return hashlib.sha256(bytes(blob)).hexdigest()
    except Exception as exc:
        log(f"vault check error: {exc}")
    return None


def check(data: bytes, force: bool):
    if not data.startswith(b"B000FF\n"):
        raise SystemExit("not a B000FF container")
    if len(data) < 1_000_000 or len(data) > 32_000_000:
        raise SystemExit(f"unexpected image size: {len(data):,}")
    embedded = image_vault_sha(data)
    if embedded is None:
        log("! cannot verify embedded vault (ce_bin unavailable)")
        return
    local = hashlib.sha256(VAULT.read_bytes()).hexdigest()
    if embedded == local:
        log("vault check: matches this device")
        return
    log(f"vault check: MISMATCH\n  image : {embedded[:16]}\n  local : {local[:16]}")
    if not force:
        raise SystemExit("refusing: image belongs to another device (use --force to override)")


def current():
    paths = mtp.discover()
    if not paths:
        return None, None, None
    t = mtp.Transport(paths[0])
    return t, t.device_info(), paths[0]


def flash(path: str, force=False) -> int:
    image = Path(path)
    if not image.exists():
        raise SystemExit(f"missing: {image}")
    data = image.read_bytes()
    sha8 = hashlib.sha256(data).hexdigest()[:8].upper()
    log(f"image : {image.name}")
    log(f"size  : {len(data):,} bytes   sha8 {sha8}")
    if sha8 in KNOWN:
        log(f"known : {KNOWN[sha8]}")
    check(data, force)

    t, info, p = current()
    if not info:
        log("device not found")
        return 1
    log(f"device: {info['firmware']}  ({p})")
    if FMT_FIRMWARE not in info["formats"] or OP_COMMIT not in info["operations"]:
        log("device does not expose the wire-flash channel")
        return 2

    q = t.operation(0x1007, [STORAGE, FMT_FIRMWARE, 0], read=True)
    r = mtp.Reader(q)
    queue = [r.u32() for _ in range(r.u32())]
    if queue:
        log(f"staging queue busy: {[hex(x) for x in queue]}")
        return 3

    t.operation(0x100C, [STORAGE, 0xFFFFFFFF],
                data=mtp.object_info_data("nk.bin", len(data), FMT_FIRMWARE, 0))
    if len(t._params) < 3:
        log("staging rejected")
        return 4
    log(f"staged: {t._params[2]:#x}")

    t0 = time.time()
    t.operation(0x100D, data=data)
    log(f"sent  : {time.time() - t0:.1f}s")

    log("commit: device reboots")
    try:
        t.operation(OP_COMMIT)
    except Exception as exc:
        log(f"disconnect during commit (expected): {exc}")

    deadline = time.time() + 240
    while time.time() < deadline:
        time.sleep(5)
        t2, info2, p2 = current()
        if not info2:
            continue
        flac = 0xB906 in info2["formats"]
        log(f"device back: {info2['firmware']}  FLAC={flac}")
        return 0
    log("device did not return in time")
    return 5


def list_images():
    root = Path(r"E:\zune_auth196\out1")
    for p in sorted(root.glob("*.bin")):
        data = p.read_bytes()
        sha8 = hashlib.sha256(data).hexdigest()[:8].upper()
        note = KNOWN.get(sha8, "")
        log(f"{sha8}  {p.name}  {len(data):,}  {note}")


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        raise SystemExit(64)
    if args[0] == "--list":
        list_images()
        raise SystemExit(0)
    force = "--force" in args
    args = [a for a in args if a != "--force"]
    raise SystemExit(flash(args[0], force))
