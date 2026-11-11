# Zune 30 (Keel) — native CJK on official 3.3 firmware

**Status: working, verified on real hardware.**

> ## This project stands on someone else's shoulders
>
> The method, the tooling and the hard-won knowledge come from
> **[`1977899016-cell/zune30-research`](https://github.com/1977899016-cell/zune30-research)**:
> the AUTH196 image builder, the CE BIN/LZX toolchain, the `default.fdf` registry editor, the
> native font loader (`ZCJKBoot.exe`) and the FontLink approach itself.
>
> Our contribution is smaller than theirs:
> 1. we followed their recipe, **found three configuration mistakes that made it fail on our
>    unit**, fixed them, and documented exactly what they were;
> 2. we **unlocked the loader's hard-coded 8,206,424-byte size check**, so arbitrary font
>    sizes work (GB2312 instead of a fixed 8 MB face);
> 3. we filled in the steps they deliberately leave out — image assembly, the firmware
>    version string, and the `C00D11CD` sync repair — as reproducible scripts;
> 4. we documented the **downgrade path** (3.3 back to 1.0 TEST), what it costs, and how to
>    come back — upstream treats the same action only as an internal recovery step.
>
> If you use anything here, star their repository first.

A first-generation Zune 30 (30 GB) running **official Zune 3.3 (39)** now renders Chinese and
Japanese text natively.

| What | Before | After |
|---|---|---|
| Device name | `Zune□□□` | Chinese characters |
| Chinese title | `□□□□` | `巨大少女` |
| Japanese title | `□□□□` | `そらのおとしもの ～エターナル・イ...` |
| Artist | `□□, □□□` | `40mP, 初音ミク` |
| Latin UI | Zegoe | **still Zegoe** (FontLink only fills missing glyphs) |

| Boot | Main menu |
|---|---|
| ![boot](assets/01-boot-device-name-redacted.jpg) | ![menu](assets/02-main-menu.jpg) |

| Japanese title | Chinese title |
|---|---|
| ![jp](assets/03-now-playing-jp-redacted.jpg) | ![cn](assets/04-now-playing-cn-redacted.jpg) |

**Start here → [`docs/tutorial.md`](docs/tutorial.md)** (English) ·
**[`docs/tutorial.zh-CN.md`](docs/tutorial.zh-CN.md)** (中文教程，步骤更细)

---

## How it works, in one paragraph

Zune 3.3's shell draws text through the system GDI. GDI has **FontLink**: when the primary
face (`Zegoe UI`, `Zegoe UI Light`, `Zegoe UI Semibold` — all in ROM) lacks a glyph, it can
pull it from a second font. So we register a CJK font as the fallback, and load it before the
shell starts with a tiny native program. Latin stays Zegoe, CJK comes from our font.

The prerequisites are the interesting part:

* a **1.0 TEST bootloader** in NOR, because the retail EBoot verifies `nk.bin`;
* an **AUTH196** image, because 3.3 refuses to boot on a 1.0-era vault;
* the font must live on `\Hard Disk` — which is the **150 MB system partition**, not the big
  data partition (we got this wrong for hours);
* the registry value must use the font's **exact internal family name**;
* the loader checks `GetFileSize` against a hard-coded constant, which has to be patched to
  match your font.

A different, ROM-level approach (replace the three `ZegoeUI*.ttf` files instead) also works
and is documented in [`docs/06-rom-space.md`](docs/06-rom-space.md) — it is the only option if
you cannot run a startup program, but it costs you the original Latin face.

---

## Repository layout

```
README.md / README.zh-CN.md     overview (this file)
NOTICE.md                       legal scope, de-identification, credits
docs/
  tutorial.md / tutorial.zh-CN.md   ★ step-by-step, start here
  01-background.md              hardware, boot chain, protection layers
  02-lax-bootloader.md          the 1.0 TEST bootloader and why it matters
  03-nor-vault-backup.md        dumping NOR/vault without desoldering
  04-auth196.md                 bootable 3.3 on a legacy vault
  05-font-mechanism.md          how text/fonts work on 3.3 (with a correction notice)
  06-rom-space.md               the ROM-replacement alternative
  07-sync-fix.md                fixing C00D11CD after firmware surgery
  08-reproduction.md            condensed reproduction checklist
  09-lessons-learned.md         everything that did NOT work, and the wrong conclusion we drew
  10-publishing-checklist.md    de-identification / publication checklist
  11-downgrade.md               3.3 → 1.0 TEST downgrade, and what it costs
  12-mtpz-protocol.md           MTPZ protocol as observed (opcodes, handshake, replay result)
  13-field-notes.md             field notes: hardware, firmware, tooling, methodology
  ACKNOWLEDGEMENTS.md           itemised credits (EN + 中文)
scripts/
  build_cjk_font.py             subset + strip hints + rename + CE-LZX size check
  patch_loader.py               rewrite the loader's font-size constant
  build_image.py                FontLink registry + version string + in-place FDF + container
  write_device.ps1              safe writer for the 150 MB system partition
assets/                         redacted screenshots
```

## Quick start

```powershell
# 0. back up F:\, G:\zunedb.dat, G:\zunedb.BAK, G:\drmStore.dat, and dump NOR/vault
# 1. install the 1.0 TEST bootloader (irreversible, see docs/02)

# 2. AUTH196
python <research>\tools\upgrade\build_upgrade.py --stock-nk ... --legacy-vault ...

# 3. font
python scripts\build_cjk_font.py --font your.ttf --charset charset.txt ^
    --limit 4000000 --family "Zune UI CJK" --out font.ttf --out-packed font.packed.bin

# 4. loader
python scripts\patch_loader.py --in <research>\artifacts\ZCJKBoot.exe ^
    --size <font bytes> --out ZCJKBoot.exe

# 5. image
python scripts\build_image.py --research-dir <research> ^
    --base nk.AUTH196.bin --fdf-in default.fdf --out nk.CJK.bin

# 6. write
powershell -ExecutionPolicy Bypass -File scripts\write_device.ps1 -Image nk.CJK.bin
```

Detailed steps, verification points and troubleshooting: `docs/tutorial.md`.

## What is verified vs. not

| Claim | Status |
|---|---|
| CJK renders on official 3.3, Latin stays Zegoe | ✅ verified on hardware |
| GB2312 subset (8,011 glyphs, 1.9 MB) loads and renders | ✅ verified |
| Zune 4.8 sync works after the modification | ✅ verified (after restoring `zunedb.dat` / `drmStore.dat`) |
| WMA sync on Windows 11 (all WMA failed with `C00D11CD / 80004002`) | ✅ fixed by restoring the WMDRM DLLs Windows no longer ships — see `docs/07-sync-fix.md` |
| Booting AUTH196 + 3.3 on a 1.0-TEST-era vault | ✅ verified |
| GBK / full font (14 MB+) | ⚠️ untested — memory limits unknown |
| Menu translation | ❌ not attempted |
| FLAC playback | ❌ not attempted (upstream claims a decoder DLL, not distributed) |
| Adding songs without the Zune client | ❌ tested and rejected by the device's MTP implementation |

## Caveats

* **Device-specific artifacts.** AUTH196 embeds your encrypted vault. Never publish it.
* **Font licensing.** Build your own subset from a font you own. Nothing here ships font data.
* **Irreversible bootloader step.** Keep `F:\EBoot.bin` (the TEST loader) safe, and never let
  the Zune software "restore" the device.
* **Sync can break — and it is preventable.** Before flashing, copy `G:\zunedb.dat`,
  `G:\zunedb.BAK` and `G:\drmStore.dat` to your PC. Details: `docs/07-sync-fix.md`.
* GB2312 coverage only; rare characters box out.
* No Microsoft firmware, fonts, keys or device-specific files are distributed here.

## Credits

Full itemised list: **[docs/ACKNOWLEDGEMENTS.md](docs/ACKNOWLEDGEMENTS.md)**.

`1977899016-cell/zune30-research` (AUTH196, CE tooling, loader) · **ahlanchuck** (firmware
swapping document) · the 2009 Baidu Tieba `zune吧` community (CJK was possible at all) ·
**正直RM** (firmware history, software archive) · archive.org preservation uploaders ·
ZuneDev / Project Lyra · libmtp / kbhome · fontTools, keystone, comtypes, mutagen.

## Privacy

Screenshots are redacted (device nickname and album art blurred); no serial numbers, local
paths or personal data appear anywhere. Checklist: `docs/10-publishing-checklist.md`.

## License

Documentation and scripts: MIT. No Microsoft binaries, no fonts, no device-specific output.
