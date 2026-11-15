**TL;DR** — "Zune 3.3 ignores FontLink, so CJK is impossible" is wrong. 3.3 uses GDI, and
GDI processes FontLink. It fails for boring reasons: the font must be on the **system**
partition (`F:`), the family name must match, the loader's size constant must match the
font, and stripping hinting makes small text blurry. Here's the whole pipeline.

> **This guide is built on top of other people's work.**
> The custom-firmware tooling — AUTH196, the CE BIN/LZX parsers, the registry hive
> tooling and the original ARM font-loader design — comes from
> **github.com/1977899016-cell/zune30-research (search for it; link in comments)**.
> If you have not got a bootable custom image yet, **start there, not here.**

---

## What you need

| Item | Where |
|---|---|
| A Zune 30 on custom firmware (TEST bootloader + AUTH196) | see repo |
| **Upstream firmware tooling — AUTH196, CE BIN/LZX, registry, font loader** | **github.com/1977899016-cell/zune30-research (search for it; link in comments)** |
| Python 3 | python.org |
| fontTools (font subsetting) | fontTools on GitHub |
| A CJK font you're licensed to use | e.g. Noto Sans CJK (OFL): Noto Sans CJK on GitHub |
| Repo scripts (`build_cjk_font.py`, `build_font_loader.py`, image tools) | github.com/Zunelzq/zune30-cjk (link in comments) |
| ZIF→USB adapter | — |

> On stock firmware the registry is read-only — this needs a custom image.

---

## Step 1 — Understand the three pieces

```
F:\Fonts\YourFont.ttf          the font, on the SYSTEM partition
        ↓
HKLM\Software\Microsoft\FontLink\SystemLink    tells GDI to fall back to it
        ↓
F:\Fonts\ZCJKBoot.exe          calls AddFontResourceW at boot
```

`\Hard Disk` in the registry is the **system** partition — that's `F:` (150 MB), **not**
`G:` (the ~57 GB data partition). Putting the font on `G:` is the #1 reason this "doesn't
work".

## Step 2 — Build the font subset

Don't ship a full CJK font. Subset it to the glyphs your library uses, plus GB2312 for
general coverage.

```powershell
python scripts\build_cjk_font.py --font NotoSansCJKsc-Regular.otf --charset charset.txt `
  --keep-hinting --family "Zune UI CJK" `
  --out out\font.ttf --out-packed out\font.packed.bin
```

Measured on my device:

| Charset | Glyphs | Size | Hinting |
|---|---|---|---|
| library + kana + ASCII | 1,819 | 379 KB | off |
| GB2312 + library + kana | 8,011 | 1.9 MB | off |
| **GB2312 + library + kana** | **8,011** | **3.2 MB** | **on** ← use this |

**Keep hinting.** Without it small characters look fuzzy; with it, text looks like the
1.0 TEST firmware, which is what people remember as "the good font". The font lives on
disk, so size is cheap.

**Record the exact byte size** of the resulting `.ttf` — you need it in the next step.

## Step 3 — Build the loader

The loader must contain the font's byte size as a constant; otherwise it silently refuses
to load and you get boxes.

```powershell
python scripts\build_font_loader.py --font-size 3359056 --out out\ZCJKBoot.exe
```

(Replace `3359056` with **your** font size.)

**Success check:** `ZCJKBoot.exe` is about 2 KB and the size constant appears in its data
section (the script handles the patching).

## Step 4 — Add the registry entries

Inside `default.fdf` in `nk.bin`:

```
[HKLM\Software\Microsoft\FontLink\SystemLink]
"Zegoe UI"          = "\Hard Disk\Fonts\ZuneCJK_UI_20261027.ttf,Zune UI CJK"
"Zegoe UI Light"    = "\Hard Disk\Fonts\ZuneCJK_UI_20261027.ttf,Zune UI CJK"
"Zegoe UI Semibold" = "\Hard Disk\Fonts\ZuneCJK_UI_20261027.ttf,Zune UI CJK"

[HKLM\Init]
"Launch45"  = "\Hard Disk\Fonts\ZCJKBoot.exe"
"Depend45"  = "30"        ; wait for the filesystem
"Depend60"  = "20,45"     ; something that needs the font
```

The `Depend` numbers matter: if the loader runs before storage is ready, it fails silently.

## Step 5 — Rebuild the image

1. Decompress `default.fdf` from your image.
2. Insert the FontLink keys and the `Init` entries.
3. Recompress into the **same fixed ROM slot**.
4. Update the ROM file table entry.
5. Patch the version string so the Zune software doesn't offer an update.
6. Rebuild B000FF records, recompute checksums.
7. **Re-parse and verify the result.**

Skip step 7 and you'll be staring at a black screen wondering why.

## Step 6 — Copy the files to the device

With the drive on the adapter:

```
F:\Fonts\ZuneCJK_UI_20261027.ttf     <- your subset
F:\Fonts\ZCJKBoot.exe                <- loader with the matching size
F:\nk.bin                            <- rebuilt image
F:\EBoot.bin                         <- TEST bootloader (11d94de4...)
```

```powershell
Get-FileHash F:\nk.bin -Algorithm SHA256
```

**Success:** boot → menus and song titles render characters instead of boxes.

## Troubleshooting

| Symptom | Cause |
|---|---|
| Boxes instead of characters | font path wrong, family name wrong, or loader didn't run |
| Works in menus only | FontLink entries missing for the other faces |
| Loader seems not to run | `Init` Depend numbers |
| Fuzzy small text | hinting was stripped at build time |
| Black screen | image problem (checksums / vault), not the font |

## Cheaper alternative: stay on 1.0 TEST

If your only goal is reading Chinese/Japanese, **1.0 TEST already has a working font
stack**. You skip AUTH196 entirely and lose the 3.3 UI. Much less work, and a perfectly
reasonable choice.

---

## Credits — this is not my discovery

None of this would exist without other people's work. Specifically:

**`1977899016-cell/zune30-research`** — the single largest contribution.
Their repository contains the AUTH196 builder (which is the *only* reason a 1.0-era device
can boot 3.3 at all), the strict B000FF container parser/rebuilder, the CE LZX encoder and
decoder for `default.fdf`, the ROM file-table layout, the registry hive tooling, and
`build_font_loader.py` — the native CE ARM loader design I used here. Without that
tooling there is no custom image and no CJK work. Their README also states plainly that
the 3.3 compatibility image does **not** include Chinese, which is what told me this was
still unsolved and worth attempting.

**The Zune community on Baidu Tieba (around 2009)** — the first people to show that CJK
rendering on these devices was possible at all. That thread is the reason the idea
survived.

**ahlanchuck** — "Firmware Swapping on Zune 30 (Keel) Models", the write-up that explained
the EBoot/NOR/`nk.bin` boot chain before anyone else documented it.

**fontTools** — the subsetting toolchain that makes a usable font size possible.

If you contributed and I missed you, tell me and I'll fix the credits.

---

## Links

**The project this is built on:**

- **github.com/1977899016-cell/zune30-research (search for it; link in comments)** — AUTH196, CE BIN/LZX tooling,
  registry hive tooling, the original ARM font-loader design. Start here.

**Everything else:**

- This write-up and the font scripts: github.com/Zunelzq/zune30-cjk (link in comments)
- Noto Sans CJK (open font, OFL): Noto Sans CJK on GitHub
- fontTools: fontTools on GitHub
- Python: python.org

---

If you try this, post **your font size and loader constant** — those two numbers must
match, and that's the most common silent failure.