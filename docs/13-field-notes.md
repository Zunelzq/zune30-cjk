# 13 — Field notes: what this project actually taught us

> Hard-won, mostly non-obvious. Written so the next person does not repeat the expensive
> mistakes. Anything marked **✗** is a conclusion we initially got wrong.

## 1. Hardware

* **`\Hard Disk` is the 150 MB system partition (`F:` in Windows), not the big data partition.**
  We copied a font to `G:\Fonts` and spent hours wondering why the loader did nothing.
* The ZIF→USB adapter drops the connection mid-write regularly. Every write script must:
  wait for the volume, retry, and verify by hash afterwards.
* A failed boot makes the device **format the system partition**. Files like `EBoot.bin` and
  `recovery.bin` disappear; keep copies on the PC and restore them.
* The device enumerates on a different root hub depending on which port you use; after
  replugging, the `Hub_#` number can change. Do not hard-code it in capture scripts.

## 2. Firmware format

* `nk.bin` is a **B000FF** container: 15-byte header (`B000FF\n`, base, span, entry), then
  records `(address, length, checksum, data)`, terminated by `(0, entry, 0)`; the checksum is
  the byte sum of the payload.
* **The record list must not be re-chunked.** Rebuilding it as sorted 32 KB chunks produced a
  progress bar and then a black screen. Keep the original records and patch inside them.
* The CE ROM file table entries are 28 bytes: `flags`, `?`, `?`, `size`, `compressed`, `name VA`,
  `data VA`. `flags & 0x800` means "stored compressed" — the filesystem decompresses it
  transparently on read.
* CE LZX compressed streams **only decode with 4,096-byte blocks** here. 8/16/32 KB blocks are
  rejected by the device's decoder.
* **Compressing a file in place is safe; relocating it is not.** Moving a `.gem` package (even
  with a correct new file-table entry) black-screens the device.
* Writing into ROM holes that are **not covered by any B000FF record** silently does nothing —
  the loader never maps them.
* The firmware version string is produced by a format string in `nk.bin`:
  `%02d.%02d.%05d.%02d-%05d` at `0x7cda6c` (UTF-16LE). The last field is the bootloader version,
  so a TEST loader makes the device report `…-00002` and the client thinks it is outdated.

## 3. Registry (`default.fdf`)

* It is a CE hive, compressed (flag `0x800`), and lives in a **fixed 38,949-byte slot**.
  It fits our FontLink edits with 22 bytes to spare — but there is no room to add much else.
* Editing it means rewriting records in place; the upstream `prepare_registry.py` does this
  correctly and preserves unrelated values.
* We verified that our final image loses **zero** registry keys compared with stock 3.3
  (1,900 keys before, 1,900 after, 1 added). This is the check to run whenever you touch the hive.

## 4. Text and fonts

* The 3.3 shell draws text through **GDI**, and GDI **does** honour FontLink. **✗** We first
  concluded the opposite because our setup had three separate mistakes:
  1. font on the wrong partition (`G:` instead of `F:`);
  2. family name in the registry not matching the font's internal name;
  3. a loader whose hard-coded size check silently refused our font.
* A loader must exist because FontLink maps to a **loaded** font; a file on disk alone is not
  enough. It runs at `Launch45` after `gwes.exe` (`Depend45 = 30`), and `Depend60` must include 45.
* The upstream loader checks `GetFileSize == 8,206,424` — a plain 32-bit literal in its pool
  (offset `0x2ec`). Patching it makes any font size work; that single change is what allowed a
  1.9 MB GB2312 subset instead of one fixed 8 MB face.
* Removing hinting halves the size but makes small CJK text fuzzy; keep it if you have room.
* **Alternative path:** replacing the three `ZegoeUI*.ttf` files in ROM also works and needs no
  loader — but it replaces the Latin glyphs too (the UI turns serif), and it costs ROM space.

## 5. Sync and DRM

* `C00D11CD (80004005)` after firmware surgery is a **device-state** problem: restore the
  device's own `zunedb.dat`, `zunedb.BAK`, `drmStore.dat`. Those three files are the difference
  between "sync works" and "sync is permanently broken".
* `C00D11CD (80004002)` (`E_NOINTERFACE`) with **all WMA failing and MP3 fine** is a **PC-side**
  problem: Windows 11 replaced WMDRM with a stub. See `07-sync-fix.md`. FFmpeg-based transcoding
  is not the issue; Zune needs WMDRM to encrypt WMA for the device.
* Changing the sync relationship treats the device as a new one and **resets its library**.
  Do not do it casually.
* `guest` relationship still copies files, but they are temporary and can disappear later.

## 6. Tooling

* **USBPcap** — see `12-mtpz-protocol.md`; the two traps are "pcap not pcapng" and the
  pseudo-header offsets.
* **`dism /RestoreHealth`** on a trimmed Windows can crawl (0.1 % per ten minutes) because it
  waits on Windows Update; and if the component is genuinely absent from the image, it will
  never restore it.
* **wimlib** (`wimlib-imagex.exe`) reads WIM/ESD without administrator rights and is the fastest
  way to check whether a system file even exists in a given build.
* `regsvr32 /s` returns 0 even when it registered nothing — verify by querying the registry
  instead of trusting the exit code.

## 7. Methodology (the most reusable part)

**"The value did not change" is not the same as "the mechanism is not used."**
We wrote down "3.3 ignores FontLink" based on a misconfigured experiment, published that
conclusion internally, and had to correct it later. The correction is now part of `05-…`.

**Capture from the beginning.** Our first USB capture started mid-session (first transaction
id was 2970), which hid the entire `0x9212` handshake and produced a confident, wrong conclusion
that survived two rounds of review.

**When an error code is a COM HRESULT, it is the PC talking.** `0x80004002` can never come from
the device; it is an interface lookup on the host. That single fact would have saved hours.

**Check what changed, not what you suspect.** The user's "it synced before the project" was true
for MP3; comparing the registry proved the firmware was untouched. The failure had been there
all along, hidden behind a smaller library.

**Prefer a minimal-change image.** Our final firmware changes exactly two things: the registry
(FontLink + Init) and the version string. When something breaks, that is easy to reason about.

## 8. Publishing

* Keep all binaries out of the repository (`*.bin`, `*.cab`, `*.ttf`, `*.PRIVATE.bin`).
* AUTH196 embeds the device's encrypted vault — never publish an image built with it.
* Screenshots need redaction: device name, album art, anything identifying.
* Credit the upstream project prominently; most of the method is not ours.
* Frame it as interoperability research, not as a bypass tool.
