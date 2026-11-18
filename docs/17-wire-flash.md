# Wire flashing a Zune 30 over USB

**Status: working.** Firmware can be replaced without opening the device. Both
directions between the two working images were flashed and verified on hardware.

## Why the Zune-software path fails but this one works

Zune 4.8 updates a device by downloading a CAB from `resources.zune.net` and calling
`WinVerifyTrust` on it first. A repacked CAB carries no Microsoft signature, so the client
aborts with `C00D11CD (800B0100)` before anything reaches the device. That gate is in the
desktop software, not the device.

The device itself exposes a separate, unauthenticated firmware channel over MTP:

```
object format 0xb802   firmware staging object
0x1007                 enumerate staging queue
0x100C                 SendObjectInfo (format 0xb802) -> handle in response params
0x100D                 SendObject (the nk.bin bytes)
0x101B                 read back (normal mode: returns 0x200F, unsupported)
0x9204                 commit: installer writes F:\nk.bin and reboots
```

Both the running 3.3 firmware and the Pyxis USB-recovery environment advertise
`0xb802` + `0x9204`, which is why flashing works from either state.

## Entering recovery (only needed if a firmware will not boot)

```
1. Power off (hold power ~15 s)
2. Hold Back
3. Plug in USB
4. Release when "Connect" appears
```

The device shows the `Pyxis maintenance` menu; choose **USB recovery mode**.
Never choose *restore factory defaults*, *format data partition* or *initialize disk*.

In recovery the MTP report is:

```
firmware  : 00.00.00000.00-00.00
formats   : 0xb802, 0xb902
operations: includes 0x100c, 0x100d, 0x9204
```

and the staging handle is `0x0ff00000`.

## Tool

`tools/zunesync/switch.py` (needs the `zunesync` package next to it):

```
python switch.py            # menu: 1 = Zune mode, 2 = MTP mode, 3 = status
python switch.py zune       # 045E image: Zune 4.8 sync + FLAC playback
python switch.py mtp        # 1209 image: Explorer file transfer
python switch.py status
```

Behaviour:

1. verifies the image (B000FF magic, size, SHA-256 prefix) before sending;
2. refuses if the staging queue is not empty;
3. stages, sends, commits;
4. polls until the device re-enumerates and reports the expected USB mode.

A commit always ends with a USB disconnect (`WPD error 0x8007001F`) because the device
reboots; the tool treats that as expected and verifies by polling.

## Measured timings

```
image 13.9 MB -> staged + sent in ~11.7 s
commit -> device back in ~15 s, running the new image
```

## Safety

- Only `nk.bin` is ever sent. The bootloader (`EBoot.bin`) is never written by this path.
- A bad image leaves the device unbootable; recover by entering Pyxis USB recovery mode
  and flashing a known-good image (the channel is in the bootloader, so it stays available).
- Keep the disk image backups from the archive: if recovery mode itself fails, the 150 MB
  partition can be rewritten directly with a ZIF adapter.

## What this enables

`23C8D9B9` (Zune mode) and `6A996991` (MTP mode) can now be exchanged in about half a
minute:

```
python switch.py mtp     # drag new FLAC files in Explorer
python switch.py zune    # back to Zune software sync
```

No disassembly, no key combinations, no risk to the bootloader.
