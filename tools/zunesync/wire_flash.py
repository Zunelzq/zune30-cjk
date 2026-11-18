"""Wire-flash a Zune 30 over USB (MTP firmware staging, format 0xb802).

Works in two device states:
  * normal firmware (3.3)  -> stage + send + commit, device reboots into the image
  * Pyxis USB recovery     -> same operations, recovery handle 0x0FF00000

Verified on hardware: a 13,956,899-byte nk.bin transfers and installs, and the
device comes back running the flashed image.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, r"E:\DSH\workblock\zune\PROJECT\zune-sync")
from zunesync import mtp

STORAGE = 0x10001
FMT_FIRMWARE = 0xB802
OP_COMMIT = 0x9204
RECOVERY_VERSION = "00.00.00000.00-00.00"


def log(*a):
    print(*a, flush=True)


def device_info():
    paths = mtp.discover()
    if not paths:
        raise SystemExit("no device found")
    t = mtp.Transport(paths[0])
    return t, t.device_info()


def flash(image_path: str, timeout_poll: int = 180) -> int:
    payload = Path(image_path).read_bytes()
    log(f"image: {image_path}  {len(payload):,} bytes")

    t, info = device_info()
    recovery = info["firmware"] == RECOVERY_VERSION
    log(f"firmware: {info['firmware']}  ({'recovery' if recovery else 'normal'})")
    if FMT_FIRMWARE not in info["formats"] or OP_COMMIT not in info["operations"]:
        log("device does not support firmware staging")
        return 2

    q = t.operation(0x1007, [STORAGE, FMT_FIRMWARE, 0], read=True)
    r = mtp.Reader(q)
    queue = [r.u32() for _ in range(r.u32())]
    if queue:
        log(f"staging queue not empty: {[hex(x) for x in queue]}")
        return 3

    t.operation(0x100C, [STORAGE, 0xFFFFFFFF],
                data=mtp.object_info_data("nk.bin", len(payload), FMT_FIRMWARE, 0))
    params = t._params
    if len(params) < 3:
        log("staging rejected")
        return 4
    handle = params[2]
    log(f"staged handle: {handle:#x}")

    log("sending payload...")
    t0 = time.time()
    t.operation(0x100D, data=payload)
    log(f"payload sent in {time.time() - t0:.1f}s")

    log("committing (device will reboot)...")
    try:
        t.operation(OP_COMMIT)
        log("commit acknowledged")
    except Exception as exc:
        log(f"commit returned (expected on reboot): {exc}")

    log("waiting for device...")
    deadline = time.time() + timeout_poll
    while time.time() < deadline:
        time.sleep(5)
        try:
            t2, info2 = device_info()
        except SystemExit:
            continue
        log(f"back online: firmware {info2['firmware']}")
        return 0
    log("device did not come back in time")
    return 5


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: wire_flash.py <nk.bin>")
        raise SystemExit(64)
    raise SystemExit(flash(sys.argv[1]))
