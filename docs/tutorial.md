# Tutorial: native Chinese/Japanese text on an official 3.3 Zune 30

> ## Attribution — this builds on someone else's work
>
> **The core method comes from [`1977899016-cell/zune30-research`](https://github.com/1977899016-cell/zune30-research)**:
> the AUTH196 image builder, the CE BIN/LZX tooling, the `default.fdf` registry editor, the
> native font loader (`ZCJKBoot.exe`) and the FontLink approach are all theirs.
>
> What this repository adds:
> 1. correcting **three configuration mistakes** that made their recipe fail on our unit
>    (font on the wrong partition, wrong font family, wrong loader);
> 2. unlocking the loader's hard-coded 8,206,424-byte check so **any font size** works;
> 3. the missing packaging steps — image assembly, firmware version string, and the
>    `C00D11CD` sync fix — written as reproducible scripts.
>
> Without their work this tutorial would not exist.

---

## What you get

A first-generation Zune 30 (30 GB) running **official 3.3 (39)** with:

* Chinese and Japanese song titles, artist names and device name rendered natively;
* the **original Zegoe Latin** UI face preserved (FontLink only supplies missing glyphs);
* working Zune software sync;
* a customisable character set (GB2312, ~8,000 glyphs, in this guide).

## Prerequisites

| Item | Notes |
|---|---|
| Zune 30 (Keel, 30 GB) | i.MX31 |
| ZIF→USB adapter | flaky by nature; prefer a rear USB port |
| Windows PC | PowerShell + Python 3.10+ |
| Official 3.3 firmware | your own `KeelBaseline.cab` |
| **1.0 TEST bootloader** | `EBoot.bin`, sha256 prefix `11D94DE4` |
| A CJK TTF you are licensed to use | |
| `1977899016-cell/zune30-research` | cloned locally; this guide calls its tools |
| `ZZAudio-Zune30-Assistant` (optional) | upstream tool for NOR/vault backup without desoldering |

```powershell
py -m pip install fonttools
```

## 1. Back up first (mandatory)

Copy both partitions:

```
F:\  -> 150 MB system partition (EBoot.bin, nk.bin, recovery.bin, zconfig.dat, ...)
G:\  -> data partition, MUST include:
        zunedb.dat   (~4 MB)
        zunedb.BAK   (~4 MB)
        drmStore.dat (~54 MB)
```

Then dump NOR and the vault with the upstream assistant (device must be running 1.0 TEST):
`nor.original.bin` (2 MB), `vault.legacy.bin` (64 KB), `nk.original.bin`.

> These embed your device identity. Never publish or share them.

## 2. Install the 1.0 TEST bootloader

1. copy the 1.0 TEST `EBoot.bin` to `F:\EBoot.bin`;
2. copy `recovery.bin`, `zconfig.dat`, `pmcver.dat` from the same package;
3. boot once — the device flashes `EBoot.bin` into NOR;
4. the splash must read `Bootloader 2`.

> Irreversible step. Afterwards **never** let the Zune software "restore/repair" the device
> and never apply a firmware CAB: that reinstalls the retail loader, which verifies `nk.bin`
> and cannot be replaced again (HAB).

## 3. Build AUTH196 (3.3 on the legacy vault)

```powershell
python <research>\tools\upgrade\build_upgrade.py `
  --stock-nk <official-3.3-nk.bin> --legacy-vault <vault.legacy.bin> `
  --vault-sha256 <sha256> --decompressor-dir <research>\app\vendor `
  --output-dir out\auth196
```

Write the result to `F:\nk.bin` and confirm the device reaches the 3.3 shell **before**
continuing.

## 4. Prepare the font

Extract and decompress `default.fdf` from the AUTH196 image (upstream `ce_bin.py` +
`ce_lzx.py`), then:

```powershell
python scripts\build_cjk_font.py --font <your-font.ttf> --charset charset.txt `
  --limit 4000000 --family "Zune UI CJK" --keep-hinting `
  --out out\font.ttf --out-packed out\font.packed.bin
```

Measured configurations:

| Character set | Glyphs | Size | Hinting |
|---|---|---|---|
| library + kana + ASCII | 1,819 | 379 KB | off |
| **GB2312 + library + kana** | **8,011** | **1.9 MB** | off |
| **GB2312 + library + kana** | **8,011** | **3.2 MB** | **on** (recommended: much sharper small text) |

> On the FontLink path the font lives on the data volume, so size is cheap — keep hinting.
> Strip it only when you are squeezing the font into ROM (`06-rom-space.md`).

Copy the result to the device as `F:\Fonts\ZuneCJK_UI_20261027.ttf`
(`\Hard Disk` is the **system** partition, i.e. `F:`).

## 5. Patch the loader size constant

```powershell
python scripts\patch_loader.py --in <research>\artifacts\ZCJKBoot.exe `
  --size <font size in bytes> --out out\ZCJKBoot.exe
```

Copy it to `F:\Fonts\ZCJKBoot.exe`.

## 6. Build the image

```powershell
python scripts\build_image.py --research-dir <research> `
  --base out\auth196\nk.AUTH196.PRIVATE.bin --fdf-in out\default.fdf --out out\nk.CJK.bin
```

It adds FontLink + `Launch45`, compresses the registry (CE LZX, 4096-byte blocks) **in place**
into the existing `default.fdf` slot, patches the firmware version string, and rebuilds the
container **keeping the original record list**.

Expected output:

```
registry: 186,629 bytes, launch order [20, 30, 45, 60]
registry compressed: 38,927 bytes
default.fdf: 186,629 -> 38,927 (slot 38,949)
version string patched at 0x7cda6c -> 03.30.00039.00-00435
```

## 7. Write it

```powershell
powershell -ExecutionPolicy Bypass -File scripts\write_device.ps1 -Image out\nk.CJK.bin
```

Waits for `F:`, backs up the current `nk.bin`, writes with retries and hash verification, and
warns if `F:\EBoot.bin` is not the TEST loader.

## 8. Verify

| Check | Expected |
|---|---|
| splash | `Version 3.30 (39)`, `Bootloader 2` |
| main menu | Latin still looks like Zegoe |
| Chinese titles | rendered, not `□□□` |
| device name | Chinese renders |

## 9. Fix sync if it broke

`C00D11CD (80004005)` after firmware surgery: restore your own `G:\zunedb.dat`,
`G:\zunedb.BAK`, `G:\drmStore.dat`. See `07-sync-fix.md`.

## 10. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| black screen / reboot | AUTH196 does not match this unit's vault | redo step 3 |
| boxes instead of CJK | font path / family / loader mismatch | see the three checks below |
| text disappears | font too large or corrupt | try a 1–2 MB subset |
| Latin became serif | you used the ROM-replacement path (`06`) | expected there |
| `please wait` then "connect to PC" | the container was re-chunked | rebuild with the scripts |

The three FontLink checks:

1. is the font really in `F:\Fonts` (not `G:\Fonts`)?
2. does the font's internal family name match the string after the comma exactly?
3. does the loader's size constant equal the font's real byte size?

## 11. Limits

* GB2312 only; GBK-extension characters still box out.
* menus stay English (`strings.gem` is not touched).
* the bootloader swap is irreversible; backup is not optional.
* no Microsoft firmware, fonts or device-specific files are distributed here.

---

## Rolling back

If you want to return to 1.0 TEST, see [11-downgrade.md](11-downgrade.md): procedure, expected behaviour, and what data it breaks.
