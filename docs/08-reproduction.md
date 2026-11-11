# 08 — Full reproduction

This is the exact sequence that produced a working device. Read `09-lessons-learned.md`
first if you plan to deviate — most alternative approaches fail.

## 0. Requirements

| Item | Notes |
|---|---|
| Zune 30 (Keel, 30 GB) | any generation-1 device |
| ZIF→USB adapter | 1.8" drive adapter; unstable adapters cause write failures |
| Windows PC | PowerShell; Python 3.10+ for the scripts; `makecab.exe` from Windows |
| Official 3.3 `KeelBaseline.cab` | from **your own** Zune 4.8 installation package |
| A CJK TTF you are licensed to use | e.g. a font you purchased; subset it yourself |
| A 1.0 TEST device, or a unit whose NOR already has the TEST EBoot | see `02-lax-bootloader.md` |

Install the Python deps used by the scripts:

```powershell
py -m pip install fonttools mutagen keystone-engine
```

## 1. Back up the device (do this first, always)

Follow `03-nor-vault-backup.md`. You must obtain:

```
nk.original.bin            the current OS image
nor.original.bin           2 MiB NOR dump
vault.legacy.bin           64 KiB vault (offset 0x70000 in NOR)
disk-prefix.bin            first 1 MiB of the drive
```

Plus a file-level copy of both partitions:

```
F:\  →  150 MB system partition (EBoot.bin, nk.bin, recovery.bin, zconfig.dat, ...)
G:\  →  data partition (zunedb.dat, drmStore.dat, Content\, ...)
```

Keep `EBoot.bin` from your own device. **Never lose it.**

> ### ⚠️ Mandatory before the first flash — copy these three `G:\` files
>
> ```
> G:\zunedb.dat      4 MB   SQL CE media library
> G:\zunedb.BAK      4 MB
> G:\drmStore.dat    ~54 MB DRM store
> ```
>
> They are the difference between "sync still works afterwards" and "sync is permanently
> broken". A failed boot formats `F:`; running the 1.0 TEST firmware rewrites the data
> partition's library; the AUTH196 vault re-wrap cannot persist security state. Once those
> files are gone you cannot recreate a matching relationship — see `07-sync-fix.md`.

## 2. Install the 1.0 TEST bootloader

1. Copy the 1.0 TEST `EBoot.bin` (sha256 `11D94DE4…`) to `F:\EBoot.bin`.
2. Also copy `recovery.bin`, `zconfig.dat`, `pmcver.dat` from the same TEST package.
3. Boot the device once. The device flashes `EBoot.bin` from disk into NOR at boot.
4. The splash screen must show `Bootloader 2`.

From this point the device boots any `nk.bin`.

## 3. Build the AUTH196 image (3.3 on a legacy vault)

Use the public `zune30-research` tooling with **your own** inputs:

```powershell
python tools\upgrade\build_upgrade.py `
  --stock-nk      path\to\official-3.3-nk.bin `
  --legacy-vault  path\to\vault.legacy.bin `
  --vault-sha256  <sha256 of vault.legacy.bin> `
  --decompressor-dir path\to\zune30-research\app\vendor `
  --output-dir    out\auth196
```

Verify the output boots before continuing (write it to `F:\nk.bin`, boot, confirm 3.3).

## 4. Build the CJK font

```powershell
python scripts\build_cjk_font.py `
  --font        path\to\your-cjk.ttf `
  --charset     charset.txt `
  --limit       180600 `
  --family      "Zegoe UI Semibold" `
  --out         out\font.ttf `
  --out-packed  out\font.packed.bin
```

`charset.txt` should contain ASCII, kana, and the Han characters you care about.
The script strips hinting (required to hit the size limit), renames the face, compresses
with CE-LZX (4096-byte blocks) and refuses to emit anything larger than `--limit`.

Practical limits measured on hardware:

| Contiguous space available | Hint-free Han characters that fit |
|---|---|
| 112,948 B (three Zegoe slots only) | ~650 |
| 163,325 B (+ skin tail + Acs slot) | ~950 |
| 180,776 B (+ two zdkscenes slots) | ~1,050 |

## 5. Assemble the image

```powershell
python scripts\patch_nk.py `
  --base   out\auth196\nk.AUTH196.bin `
  --font   out\font.packed.bin `
  --font-unpacked out\font.ttf `
  --out    out\nk.CJK.bin `
  --version-string "03.30.00039.00-00435" `
  --skin-compress
```

What it does, in order:

1. patch the firmware version format string (`%02d.%02d.%05d.%02d-%05d` →
   the literal you pass) so the Zune client stops thinking the firmware is outdated;
2. compress `skin_default.gem` in place (flags |= 0x800);
3. place the compressed font right after the compressed skin (aligned to 4);
4. point `ZegoeUI.ttf`, `ZegoeUI_L.ttf`, `ZegoeUI_SB.ttf` at it, flags |= 0x800;
5. rebuild the B000FF container **keeping the original record list**, and assert that
   re-parsing reproduces the intended bytes.

## 6. Write it to the device

```powershell
powershell -ExecutionPolicy Bypass -File scripts\write_device.ps1 `
  -Image out\nk.CJK.bin
```

The script waits for `F:\`, backs up the current `nk.bin`, writes with retries and hash
verification (ZIF adapters drop connections), and restores the standard files if the
partition was formatted by a failed boot.

## 7. Boot and verify

Expected:

* splash: device name in Chinese/Japanese, `Version 3.30 (39)`, `Bootloader 2`;
* main menu: Latin text now uses your font (serif if you used SimSun);
* now playing: song titles in Chinese/Japanese.

## 8. Restore sync (if the Zune client refuses)

See `07-sync-fix.md`. Short version: put the device's **own** original
`zunedb.dat`, `zunedb.BAK` and `drmStore.dat` back on `G:\`.

## Rollback

```powershell
# back to plain 3.3
Copy-Item out\auth196\nk.AUTH196.bin F:\nk.bin -Force
# back to 1.0 TEST
Copy-Item backup\nk.original.bin F:\nk.bin -Force
```

The bootloader stays; a bad `nk.bin` never bricks the device, it only fails to boot.
