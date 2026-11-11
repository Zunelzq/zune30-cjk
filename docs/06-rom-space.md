# 06 — Freeing contiguous ROM space safely

The ROM file system lives inside the B000FF image between `base` (`0x88200000`) and
`ram_start` (`0x88f90000`). On our AUTH196 image the numbers are:

```
image span        14,184,816 B
free tail            36,496 B
ram_start         0x88f90000
```

A 1,000-character hint-free CJK font compresses to ~177 KB, so the tail alone is nowhere
near enough. Space has to be manufactured.

## What can be compressed in place

Any file whose file-table entry carries `flags |= 0x800` is transparently decompressed by
the CE ROM file system when read. Measured on hardware:

| File | Original | CE-LZX | Savings |
|---|---|---|---|
| `skin_default.gem` | 464,259 | 333,565 | 130,694 |
| `scenes.gem` | 179,444 | 50,153 | 129,291 |
| `scenes_tv.gem` | 175,574 | 48,696 | 126,878 |
| `strings.gem` | 91,027 | 23,674 | 67,353 |
| `wince.nls` | 134,378 | not needed | — |

`skin_default.gem` is the useful one: its 130 KB tail is **contiguous** with the files that
follow, so it can be extended:

```
skin_default.gem slot (compressed)  ── tail 130,694 B ──┐
Acs_045E_081C_3_90_ClutchFW.hex       32,631 B          ├─ one contiguous block
zdkscenes.gem                         11,658 B          │  (163 KB … 180 KB)
zdkscenes_tv.gem                       5,789 B          │
zuneroots.p7b (must stay intact)       6,764 B  ────────┘  ← hard stop
```

Used layouts:

| Layout | Space | Han chars that fit |
|---|---|---|
| three Zegoe slots only | 112,948 B | ~650 |
| + skin tail + Acs slot | 163,325 B | ~950 |
| + two `zdkscenes*` slots | 180,776 B | ~1,050 |

`Acs_*.hex` is the FM-radio firmware blob and the two `zdkscenes*.gem` files are ZDK sample
scenes; none of them are used by the retail shell, so overwriting them is acceptable.

## Hard rules (learned the hard way)

1. **Never rewrite the container.** Keep the original 110 records exactly as they are.
   A rebuild with different chunking boots the loader but crashes the OS.
2. **Never append an out-of-order record.** The loader rejects the image.
3. **Only write into space that is both free and covered by a record.** Holes between
   records are never loaded — writes there silently vanish.
4. **Do not move `.gem` packages.** Compressing them in place works; relocating them
   breaks the shell (they are addressed by their ROM location).
5. Block size for CE-LZX must stay **4096**.

## Procedure used by `scripts/patch_nk.py`

```
flat = parse(base_nk).flatten()          # bytearray
E    = file table entries (name → entry)

# 1. version string (see 07)
patch 0x7cda6c

# 2. compress skin in place
skin  = flat[E["skin_default.gem"]]
skp   = ce_lzx_encode(skin)              # verify decode(skp) == skin
write skp at the same offset, zero the rest of the slot
entry.size = len(skin); entry.compressed = len(skp); entry.flags |= 0x800

# 3. place the font at the first 4-aligned offset after the compressed skin
font_va = align4(skin_offset + len(skp))
assert font_va + len(font_packed) <= LIMIT     # zuneroots.p7z or TOC start
write font_packed

# 4. point all three Zegoe entries at it
for name in ("ZegoeUI.ttf", "ZegoeUI_L.ttf", "ZegoeUI_SB.ttf"):
    entry.address      = BASE + font_va
    entry.size         = len(font_unpacked)
    entry.compressed   = len(font_packed)
    entry.flags       |= 0x800

# 5. rebuild the container from the ORIGINAL record list
for each original record: payload = flat[record.addr-BASE : ...]
                          checksum = sum(payload) & 0xFFFFFFFF
terminator (0, entry_point, 0)

# 6. self-check: parse(result).flatten() == flat
```
