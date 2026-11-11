# 05 — How text and fonts actually work on Zune 3.3

> **Correction notice.** An earlier version of this document claimed that the 3.3 shell
> does not use GDI text fallback and that FontLink "does nothing" on 3.3. **That was
> wrong.** It was based on failed experiments that had three configuration mistakes
> (font on the wrong partition, wrong font family, wrong loader). After fixing those, a
> FontLink setup works on 3.3 and is now the recommended method.
> The incorrect conclusion and how it was found are documented in `09-lessons-learned.md`.

## The stack

```
gemstone.exe (Zune shell)
   └── text drawn through the system GDI (gwes.exe)
          └── font requested by face name ("Zegoe UI", "Zegoe UI Light", "Zegoe UI Semibold")
                 ├── glyph present in that face?  -> draw it
                 └── glyph missing?               -> FontLink fallback font
```

Two things follow from this:

1. The UI faces themselves live in ROM as `\Windows\ZegoeUI.ttf`, `ZegoeUI_L.ttf`,
   `ZegoeUI_SB.ttf`. Replacing their content changes the UI font — that is the
   **ROM replacement** path, kept as an alternative in `06-rom-space.md`. It works, but it
   also replaces the Latin glyphs (the UI becomes serif if you use a serif CJK face).
2. **FontLink is available.** If the primary face lacks a glyph, GDI can pull it from a
   second font that you supply on disk. Latin stays Zegoe, CJK comes from your font.
   This is the **recommended** path and the one this tutorial builds.

## What FontLink needs to work

| Requirement | Why |
|---|---|
| `HKLM\SOFTWARE\Microsoft\FontLink\SystemLink` values for the UI faces | tells GDI where to look for missing glyphs |
| the fallback font must be **registered with GDI** | FontLink maps *to a loaded font*; a file on disk is not enough |
| a startup program that calls `AddFontResourceW` | loads the font before the shell draws anything |
| the font must be reachable at the path in the registry value | on this device `\Hard Disk` is the **150 MB system partition (drive letter F: in Windows)**, not the big data partition |
| the family name in the registry value must match the font's internal family name exactly | otherwise GDI cannot resolve it |

## The exact values

FontLink value format is `path,Family`:

```
HKLM\SOFTWARE\Microsoft\FontLink\SystemLink
    Zegoe UI            = \Hard Disk\Fonts\ZuneCJK_UI_20261027.ttf,Zune UI CJK
    Zegoe UI Light      = \Hard Disk\Fonts\ZuneCJK_UI_20261027.ttf,Zune UI CJK
    Zegoe UI Semibold   = \Hard Disk\Fonts\ZuneCJK_UI_20261027.ttf,Zune UI CJK
```

Startup entry (run after `gwes.exe`, i.e. after slot 30):

```
HKLM\init
    Launch45 = \Hard Disk\Fonts\ZCJKBoot.exe
    Depend45 = 30
    Depend60 = 20,45          (must include 45)
```

`ZCJKBoot.exe` is a 2 KB ARM CE program that opens the font file, checks its size, calls
`AddFontResourceW`, and signals its init event. The upstream build hard-codes
`GetFileSize == 8,206,424`; `scripts/patch_loader.py` rewrites that constant so any font
size works.

## Why our first attempts failed (the three mistakes)

| Mistake | Symptom | Fix |
|---|---|---|
| font copied to `G:\Fonts` (data partition) | loader could not find the file; no fallback | put it on `F:\Fonts` — `\Hard Disk` is the system partition |
| font family `SimSun` while the registry said something else | GDI could not resolve the linked family | rename the face to `Zune UI CJK` and use that name in the registry |
| arbitrary loader with its own hard-coded path/size | loader silently did nothing | use the upstream loader, patched to your font size |

With those three fixed, Chinese appears with the original Zegoe Latin.

## How to tell whether FontLink is active

* Latin text still looks like Zegoe (rounded, geometric) — **good**, FontLink is only used
  for missing glyphs.
* Missing characters render in the CJK face instead of `□` — FontLink is working.
* If everything renders in the CJK face (serif), you are on the ROM-replacement path, not
  FontLink.

## Limits

* GDI keeps loaded fonts in memory; very large faces (14 MB+) may be slow to load or may
  fail on a 64 MB device. 2–4 MB subsets are comfortable.
* FontLink only helps for glyphs missing from the primary face; it does not change line
  breaking or text shaping.
* Menu labels are English strings in `strings.gem`; FontLink does not translate them.
