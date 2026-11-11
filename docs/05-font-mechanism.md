# 05 — How the Zune 3.3 shell loads fonts

This is the core discovery of the project. If you understand this, everything else follows.

## The wrong assumptions (all tested and disproved on hardware)

Zune 3.3 is Windows CE 5. GDI on CE supports **FontLink**: a registry mapping
`HKLM\SOFTWARE\Microsoft\FontLink\SystemLink` that makes a font fall back to another font
for missing glyphs. 1.x firmware uses exactly this (its `default.fdf` even ships with
`convection ui → \Hard Disk\Fonts\{msgothic,gulim,simsun}.ttc` baked in).

On 3.3 that mechanism does nothing:

| Attempt | Result |
|---|---|
| Add `FontLink\SystemLink` entries for `Zegoe UI*` → CJK font on `\Hard Disk` | no change |
| Register the font at boot with a native loader (`AddFontResourceW`) via `HKLM\init` | no change |
| Change `Software\Microsoft\Zune\Fonts\<face>\Locator` to point at a disk TTF | no change |
| Add `FallbackFont` values to the font entries | no change |
| Swap the two ROM fonts between the entries (locator sanity check) | no change |

The swap test is the decisive one: pointing `zegoe ui semibold` at `ZegoeUI.ttf` (regular)
instead of `ZegoeUI_SB.ttf` produced **no visible difference**. So the registry values are
simply not consulted for the UI fonts.

## What actually happens

`gemstone.exe` (the Zune shell) carries its own text stack ("XUI"). It loads its fonts from
three ROM files by name and rasterises glyphs itself:

```
\Windows\ZegoeUI.ttf       → face "Zegoe UI"          (regular)
\Windows\ZegoeUI_L.ttf     → face "Zegoe UI Light"
\Windows\ZegoeUI_SB.ttf    → face "Zegoe UI Semibold"  (marked Default=1)
```

Proof: replacing the *contents* of those three ROM files with a completely different
typeface changed the UI instantly — while every registry-based attempt had been ignored.

### Evidence trail

* Strings `Software\Microsoft\Zune\Fonts`, `Locator`, `Default`, `FallbackFont` live inside
  `gemstone.exe`'s data, not in the registry seed.
* The 3.3 `default.fdf` contains **no** `FontLink` values at all (1.0 TEST has them).
* XUI resource loader exports visible in ROM: `XuiResourceLocatorIsFile`,
  `XuiResourceOpen`, `XuiResourceComposeLocator`, and format strings
  `file://\Windows\%s#%s`, `file://\Release\%s#%s`.
* `skin_default.gem`, `scenes.gem`, `strings.gem` contain no font data (no `Zegoe`
  string, no TTF tables), so fonts are not baked into the skin.

## Consequences

1. **Font replacement must happen in ROM.** There is no runtime hook available.
2. The three files are read through the CE ROM filesystem, which **transparently
   decompresses** files whose file-table flags have `0x800` set. So the font may be stored
   LZX-compressed — which is what makes it fit at all.
3. Because the file is read via the filesystem, a compressed TTF is fine; but the
   **`.gem` scene packages must not be relocated** (see `09-lessons-learned.md`).

## Minimal recipe

```
1. take a CJK TTF you are licensed to use
2. subset it to ASCII + kana + the Han characters you need
3. strip hinting  (opts.hinting = False, drop cvt/fpgm/prep/gasp)
4. rename the family to "Zegoe UI Semibold"
5. CE-LZX compress with 4096-byte blocks, verify round-trip with the CE decoder
6. write the compressed stream into ROM, point all three Zegoe file-table entries at it,
   set flags |= 0x800 and update (uncompressed, compressed) sizes
7. keep the B000FF record layout intact (see 06)
```

Step 5 detail: the CE LZX container is a 3-byte-per-entry offset table followed by
4 KB blocks, each prefixed with `struct('<4I', 15, block_len, payload_len, block_len)`.
Blocks larger than 4096 do **not** decode on this device.
