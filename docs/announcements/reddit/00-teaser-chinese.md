# Teaser post — Chinese text on Zune 30 (no links, image-friendly)

**Title:** Chinese and Japanese text on a Zune 30 — it finally works

**Flair:** Mods/Hacks (or Show Room/Hauls if it's mostly photos)

**Attach:** 1–2 photos of the device showing Chinese menus / song titles.

---

## Body

Finally got CJK text rendering on my Zune 30 (official 3.3 firmware, custom image),
and I want to write it up properly — but first, the short version, because the
"it's impossible" answer that shows up in every thread is wrong.

3.3 runs GDI, and GDI *does* process FontLink. It just fails for boring reasons:

- the font has to live on the **system** partition (`F:`), not the 57 GB data partition (`G:`)
- the family name in the registry has to match the font's family name exactly
- the tiny loader that calls `AddFontResourceW` has the font's byte size compiled in, and
  if that number is wrong it silently does nothing
- if you strip hinting to save space, small characters look blurry

My build: GB2312 + library glyphs, 8,011 glyphs, 3.2 MB, hinting kept. Menus, artist
names and song titles all render. Text looks like the 1.0 TEST firmware, which is what
I was chasing in the first place.

None of this is my discovery. The custom-firmware tooling — AUTH196, the CE BIN/LZX
parsers, the registry hive tooling and the original ARM font-loader design — comes from
**1977899016-cell/zune30-research**. The "CJK might be possible at all" idea comes from
the old Baidu Tieba Zune community, and the boot-chain documentation that made any of it
tractable is from **ahlanchuck**'s firmware-swapping write-up.

Would people want the full step-by-step (font subsetting, loader, registry entries,
image rebuild)? If there's interest I'll post it as a proper guide with all the numbers.
Happy to answer questions in the meantime.
