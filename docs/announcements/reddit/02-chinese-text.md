# Post 2 — Chinese / Japanese text on a Zune 30

**Suggested title:**
Chinese and Japanese text on a Zune 30 — yes, 3.3 *does* support FontLink (here's the full method)

**Flair:** Modding / Guide

---

**TL;DR** — The claim that "Zune 3.3 ignores FontLink, so CJK is impossible" is wrong.
3.3 uses GDI, and GDI processes FontLink. It fails for much more boring reasons: the font
must live on the **system** partition (`F:`), the family name must match, the loader's
size constant must match the font, and stripping hinting makes small text fuzzy.
This guide covers the whole pipeline.

---

## Why it looks impossible at first

Search any Zune forum and you'll find "the Zune can't display Chinese". The usual advice is
"put a font in `F:\Fonts` and add FontLink entries" — and people try it, it doesn't work,
and they conclude the firmware ignores FontLink.

In my case, three mistakes made it look like that:

| # | Mistake | What you see |
|---|---|---|
| 1 | Font placed on `G:` (data partition) | FontLink can't resolve the path |
| 2 | Wrong family name in the registry | Font loads, never used |
| 3 | Loader built with the wrong size constant | Loader exits silently |

`\Hard Disk` is the **system** partition — the 150 MB one, `F:`. **Not** `G:`, the ~57 GB
data partition. That alone wasted a day.

## How the mechanism works

Three pieces:

1. **A TTF on the system partition** — e.g. `F:\Fonts\ZuneCJK_UI_20261027.ttf`
2. **FontLink registry entries in the firmware**, so GDI knows to fall back to it
3. **A tiny loader** that calls `AddFontResourceW` at boot, because the font isn't in ROM

The registry lives inside `nk.bin` (in `default.fdf`), so this requires a custom image.
If you're on stock firmware, this isn't for you (yet).

## Step 1 — build the font subset

A full CJK font is huge and pointless. Subset it to the glyphs your library actually uses,
plus GB2312 if you want general coverage.

Upstream script (`build_cjk_font.py`):

```powershell
python scripts\build_cjk_font.py --font simsun.ttf --charset charset.txt `
  --keep-hinting --family "Zune UI CJK" `
  --out out\font.ttf --out-packed out\font.packed.bin
```

Measured on my device:

| Charset | Glyphs | Size | Hinting |
|---|---|---|---|
| library + kana + ASCII | 1,819 | 379 KB | off |
| GB2312 + library + kana | 8,011 | 1.9 MB | off |
| **GB2312 + library + kana** | **8,011** | **3.2 MB** | **on** ← use this |

**Keep hinting.** Without it, small characters look fuzzy; with it, text looks like the
1.0 TEST firmware — which is what people remember as "the good font". On the FontLink path
the font lives on disk, so size is cheap.

Pick a font you're licensed to use. I used a GB2312 subset of SimSun.

## Step 2 — the loader

The device needs `AddFontResourceW` called at boot. A ~2 KB ARM executable does that:

```c
h = GetFileSize(L"\\Hard Disk\\Fonts\\ZuneCJK_UI_20261027.ttf");
if (h != EXPECTED_SIZE) return;          // sanity check baked into the binary
AddFontResourceW(L"\\Hard Disk\\Fonts\\ZuneCJK_UI_20261027.ttf");
SignalStarted();
```

The `EXPECTED_SIZE` constant is compiled in. If your font is 3,359,056 bytes, the loader
must contain that number — otherwise it refuses to load and you get boxes.

Patch it with `build_font_loader.py`:

```powershell
python build_font_loader.py --font-size 3359056 --out ZCJKBoot.exe
```

Copy to `F:\Fonts\ZCJKBoot.exe`.

## Step 3 — registry edits

In `default.fdf`:

```
[HKLM\Software\Microsoft\FontLink\SystemLink]
"Zegoe UI"          = "\Hard Disk\Fonts\ZuneCJK_UI_20261027.ttf,Zune UI CJK"
"Zegoe UI Light"    = "\Hard Disk\Fonts\ZuneCJK_UI_20261027.ttf,Zune UI CJK"
"Zegoe UI Semibold" = "\Hard Disk\Fonts\ZuneCJK_UI_20261027.ttf,Zune UI CJK"
```

Make the loader run at boot:

```
[HKLM\Init]
"Launch45" = "\Hard Disk\Fonts\ZCJKBoot.exe"
"Depend45" = "30"          ; wait for the filesystem
"Depend60" = "20,45"       ; something that needs the font
```

The `Depend` numbers matter. If the loader runs before the storage stack is ready, it fails
silently and you get boxes.

## Step 4 — rebuild the image

One pass, in this order:

1. decompress `default.fdf` from the image
2. insert the FontLink keys and the `Init` entries
3. recompress into the **same fixed ROM slot** (38,949 bytes in my build)
4. patch the version string so the Zune software doesn't offer an update
5. rebuild B000FF records and recompute checksums
6. re-parse the result and verify every byte

Step 6 is not optional. With wrong record checksums you get a progress bar and then a black
screen. With a wrong vault you get a black screen immediately.

## Step 5 — flash and verify

On the adapter:

```
F:\nk.bin      <- your custom image
F:\EBoot.bin   <- TEST bootloader (11d94de4..., do not touch)
F:\Fonts\ZuneCJK_UI_20261027.ttf
F:\Fonts\ZCJKBoot.exe
```

```powershell
Get-FileHash F:\nk.bin    -Algorithm SHA256
Get-FileHash F:\EBoot.bin -Algorithm SHA256   # must start with 11D94DE4
```

Boot. If you see 3.3 with real characters instead of boxes, you're done.

## The prerequisite nobody mentions

This all requires a modified firmware image, which requires the 1.0 TEST bootloader, which
requires opening the device. On stock retail firmware the registry is read-only and you
cannot apply any of this.

There's also the AUTH196 patch: official 3.3 won't boot on an early device because 3.3
expects a new-format KeyVault, and the patch performs a RAM-only re-wrap of your own vault
at boot. That image is **per-device** — flashing someone else's image will black-screen
your unit.

## Maybe skip 3.3 entirely

If your only goal is Chinese text, you can stay on 1.0 TEST:
1.0 TEST already has a working font stack and doesn't need any of this. You lose the 3.3 UI.

That's a perfectly reasonable choice, and much less work.

## Troubleshooting

| Symptom | Cause |
|---|---|
| Boxes instead of characters | font path wrong, family name wrong, or loader didn't run |
| Font appears but only in menus | FontLink entries missing for the other faces |
| Loader seems not to run | `Init` Depend numbers |
| Fuzzy small text | hinting stripped at build time |
| Black screen | image problem, not font — check B000FF records |

---

If you try this, post your font size and loader constant — the two numbers must match, and
that's the most common silent failure.
