# 09 — Everything that did not work, and why

An honest log. Several of these cost hours; all of them are reproducible.

## A. Firmware-image experiments (before the lax bootloader)

| Attempt | Result | Lesson |
|---|---|---|
| Flip one padding byte in `EBoot.bin` | device immediately entered recovery | HAB verifies EBoot on every boot; even padding is signed data |
| Flip one padding byte inside an `nk.bin` record | progress bar completes, then recovery prompt | retail EBoot verifies the whole `nk.bin`, signature block included |
| Flip one byte inside `nk.bin`'s signature extension | "please wait" → connect to PC | same check, different reporting path |
| Byte-patch a signature-verification function to `return 1` | device formatted the 150 MB system partition | the check is enforced elsewhere / the image hash is covered |
| Build a CAB with our own nk, sign with a self-signed cert | `800B0100` / `800B0109` | both the Zune client **and** the device require a Microsoft-chained Authenticode signature |
| Serve a modified CAB through the local update server (hosts redirect) | client refuses before sending | signature is verified client-side too |
| Swap the file the Zune client is about to send (in-memory hook) | `C00D1249` | device re-verifies |

**Conclusion:** with a retail bootloader there is no software path. The only reason this
project exists is the 1.0 TEST EBoot that does not check `nk.bin`.

## B. Registry-based CJK attempts on 3.3 (all no-ops)

| Attempt | Result |
|---|---|
| `HKLM\SOFTWARE\Microsoft\FontLink\SystemLink` for the three Zegoe faces | no change |
| `HKLM\init` `Launch45` + `Depend45` to run a native `AddFontResourceW` loader | no change |
| Rewrite `Software\Microsoft\Zune\Fonts\<face>\Locator` to `file://\Hard Disk\c.ttf` | no change |
| Add `FallbackFont` entries pointing at a CJK font entry | no change |
| Swap `ZegoeUI.ttf` ↔ `ZegoeUI_SB.ttf` in the locators | no change — proves the registry is not read |
| Point the loader at a missing file | no change — proves the loader itself is irrelevant |

See `05-font-mechanism.md` for what actually happens instead.

## C. ROM-space attempts

| Attempt | Result |
|---|---|
| Compress a `.gem` and keep it at the same address | **boots fine** (this is what we ship) |
| Compress a `.gem` and *relocate* it into a hole | black screen / boot loop |
| Add one extra B000FF record at the end for relocated data | boot loop / "connect to PC" |
| Rebuild the whole container as 433 sorted 32 KB chunks | progress bar completes, then black screen + reboot |
| Use ROM holes that are *not covered by any B000FF record* | writes are silently lost — the loader never places them |
| Compress with 8 KB / 16 KB / 32 KB LZX blocks | decoder rejects; only 4096-byte blocks work |

**Rules extracted:**

1. Keep the original 110-record container layout. Do not rewrite it.
2. Only write into address ranges that are (a) free of modules/files **and**
   (b) covered by an existing record.
3. Compressing a file **in place** is safe; moving a `.gem` package is not.
4. If you must extend coverage, do it by inserting a record at its sorted position —
   appending it out of order breaks the loader.

## D. Sync failures

`C00D11CD (80004005)` after firmware surgery. Things tried, in order:

| Attempt | Result |
|---|---|
| Reset the Zune client library (`ZuneStore.sdf`) | still fails |
| Rename the device to pure ASCII | still fails |
| Patch the reported firmware string `…-00002` → `…-00435` | still fails |
| Restore the **original** `zunedb.dat` + `zunedb.BAK` + `drmStore.dat` from backup | **works** |

Lesson: after any partition rebuild, the on-device media/DRM stores must be restored from
the device's own backup, otherwise the Zune client's cached relationship no longer matches.

## E. Media transfer attempts

| Attempt | Result |
|---|---|
| Copy MP3s into `G:\Content\Music` and `G:\Music` and boot | library does not scan folders; songs never appear |
| Raw MTP `SendObjectInfo` (format 0x3009) + `SendObject` | device resets the USB session |
| Create a generic object (format 0x3000) then upload | works for the backup container, crashes for media on 3.3 |
| Windows Explorer drag-and-drop | device is not exposed as a drive on this host |

Only the Zune client's vendor protocol populates the library. Folder copy does not work on
either 1.0 TEST (PMC library) or 3.3.

## F. Dead ends worth recording

* Nezu (Zune 30 emulator) — 25 KB of ARM11 decoder skeleton, cannot boot an OS image.
* OpenZDK — targets Zune HD (Tegra/CE6); no usable path for CE5 Zune 30.
* `zune30-research`'s CJK tooling — targets 1.x (GDI + FontLink + merged font). Correct for
  1.x, irrelevant for 3.3.
* fontTools `Merger` crashes on this machine (even with tiny fonts), so a merged
  "Zegoe Latin + SimSun CJK" face was not produced. The image uses one CJK font for all
  three faces, which is why Latin text now looks serif-ish.
