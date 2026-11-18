"""Switch a Zune 30 between the two working firmware modes over USB.

    python switch.py            interactive menu
    python switch.py zune       Zune mode  (045E: Zune software sync + FLAC playback)
    python switch.py mtp        MTP mode   (1209: Explorer file transfer)
    python switch.py status     show current state

The image is verified (B000FF magic, size, SHA-256 prefix) before sending, and
the device is polled after the reboot instead of assuming success.
"""
from __future__ import annotations

import hashlib
import sys
import time
from pathlib import Path

sys.path.insert(0, r"E:\DSH\workblock\zune\PROJECT\zune-sync")
from zunesync import mtp

STORAGE = 0x10001
FMT_FIRMWARE = 0xB802
OP_COMMIT = 0x9204

IMAGES = {
    "zune": {
        "path": r"E:\zune_auth196\out1\nk.AUTH196-CLEAN-FLAC-ZUNE.PRIVATE.bin",
        "sha8": "23C8D9B9",
        "label": "Zune mode: Zune 4.8 sync + FLAC playback",
        "vid": "045E",
    },
    "mtp": {
        "path": r"E:\zune_auth196\out1\nk.AUTH196-CJK-FLAC-SAFE.PRIVATE.bin",
        "sha8": "6A996991",
        "label": "MTP mode: Explorer file transfer",
        "vid": "1209",
    },
}


def log(*a):
    print(*a, flush=True)


def check_image(spec):
    path = Path(spec["path"])
    if not path.exists():
        raise SystemExit(f"missing image: {path}")
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()[:8].upper()
    if digest != spec["sha8"]:
        raise SystemExit(f"image hash mismatch: {digest} != {spec['sha8']}")
    if not data.startswith(b"B000FF\n"):
        raise SystemExit("not a B000FF container")
    return data


def current():
    paths = mtp.discover()
    if not paths:
        return None, None, None
    transport = mtp.Transport(paths[0])
    return transport, transport.device_info(), paths[0]


def mode_of(path):
    low = path.lower()
    if "vid_045e" in low:
        return "zune"
    if "vid_1209" in low:
        return "mtp"
    return "unknown"


def status():
    t, info, path = current()
    if not info:
        log("no device")
        return 1
    log(f"usb mode : {mode_of(path)}")
    log(f"firmware : {info['firmware']}")
    log(f"0xb802   : {'yes' if FMT_FIRMWARE in info['formats'] else 'no'}")
    log(f"0x9204   : {'yes' if OP_COMMIT in info['operations'] else 'no'}")
    return 0


def flash(mode: str) -> int:
    spec = IMAGES[mode]
    log(f"target: {mode} — {spec['label']}")
    payload = check_image(spec)
    log(f"image : {len(payload):,} bytes, sha8 {spec['sha8']}")

    t, info, path = current()
    if not info:
        log("device not found")
        return 1
    log(f"current: {mode_of(path)} / {info['firmware']}")
    if mode_of(path) == mode:
        log("already in this mode, nothing to do")
        return 0
    if FMT_FIRMWARE not in info["formats"] or OP_COMMIT not in info["operations"]:
        log("this firmware does not expose the wire-flash channel")
        return 2

    q = t.operation(0x1007, [STORAGE, FMT_FIRMWARE, 0], read=True)
    r = mtp.Reader(q)
    queue = [r.u32() for _ in range(r.u32())]
    if queue:
        log(f"staging queue busy: {[hex(x) for x in queue]}")
        return 3

    t.operation(0x100C, [STORAGE, 0xFFFFFFFF],
                data=mtp.object_info_data("nk.bin", len(payload), FMT_FIRMWARE, 0))
    if len(t._params) < 3:
        log("staging rejected")
        return 4
    log(f"staged: {t._params[2]:#x}")

    t0 = time.time()
    t.operation(0x100D, data=payload)
    log(f"sent  : {time.time() - t0:.1f}s")

    log("commit: device reboots")
    try:
        t.operation(OP_COMMIT)
    except Exception as exc:
        log(f"disconnect during commit (expected): {exc}")

    deadline = time.time() + 240
    while time.time() < deadline:
        time.sleep(5)
        t2, info2, path2 = current()
        if not info2:
            continue
        now = mode_of(path2)
        log(f"device back: {now} / firmware {info2['firmware']}")
        return 0 if now == mode else 6
    log("device did not return in time")
    return 5


def menu():
    log("1) Zune mode (Zune 4.8 sync + FLAC playback)")
    log("2) MTP mode  (Explorer file transfer)")
    log("3) status")
    choice = input("select: ").strip()
    if choice == "1":
        return flash("zune")
    if choice == "2":
        return flash("mtp")
    if choice == "3":
        return status()
    return 64


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else ""
    if arg in IMAGES:
        raise SystemExit(flash(arg))
    if arg == "status":
        raise SystemExit(status())
    raise SystemExit(menu())
