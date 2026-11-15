**TL;DR** — If your SSD-swapped Zune 30 freezes while you listen to music *and* browse the
library at the same time, the SSD isn't the problem. The 2006-era PATA driver runs in DMA
mode, and a modern SSD answers thousands of times faster than the HDD it was written for.
Disabling DMA inside the firmware fixes it completely, at the cost of slower I/O.

**This only works on custom firmware.** The fix lives in the registry inside `nk.bin`.
On stock retail firmware those values are read-only.

> **Built on:** `1977899016-cell/zune30-research` — the AUTH196 builder, the CE BIN/LZX
> tooling and the registry hive editor that make a bootable custom image possible.
> Without that project none of this would exist. Search GitHub for
> **1977899016-cell/zune30-research**; links are in the comments.

---

## Step 1 — Check that this is your problem

- [ ] MP3 playback works fine
- [ ] It freezes **only under concurrent load**: music playing + scrolling the library
- [ ] The original 30 GB HDD never did this

If it freezes at random while idle, suspect the ZIF ribbon instead.

## Step 2 — Rule out the hardware first (5 minutes, free)

1. Reseat the ZIF ribbon; swap it if you have a spare.
2. Check the SSD contacts for oxidation.
3. Make sure the SSD isn't a worn unit with long internal retries.

A bad ribbon gives exactly the same "random freeze" symptom, so do this before flashing
anything.

## Step 3 — The actual cause

The driver is `pmc_atapi_mx31`. Its defaults assume a spinning disk:

```
softresettimeout     48
statuspollcycles     2000
statuspollcyclepause 400
device0\dma          1      <-- the problem
device0\lookahead    1
device0\writecache   1
```

A HDD answers a read in ~10 ms, so requests queue naturally. An SSD answers in
microseconds, the interrupt rate explodes, and the old DMA completion handling falls
behind. The driver waits forever and the device hangs.

My first attempt only raised the timeouts and disabled the write cache. **It did not
help.** Disabling DMA is what fixed it.

## Step 4 — What to change

Inside `default.fdf` in your `nk.bin`:

```
drivers\builtin\pmc_atapi_mx31
    softresettimeout      = 800
    statuspollcycles      = 6000
    statuspollcyclepause  = 2000

drivers\builtin\pmc_atapi_mx31\device0
    dma                   = 0
    lookahead             = 0
    writecache            = 0
```

Rebuild the image properly:

1. extract and decompress `default.fdf`
2. edit the six values
3. recompress into the same fixed ROM slot
4. update the ROM file table entry
5. rebuild the B000FF record list and recompute every checksum
6. **re-parse the result and verify it byte for byte**

Step 6 is not optional. Wrong checksums give you a progress bar and then a black screen.

## Step 5 — Flash and verify

```
F:\nk.bin      <- your rebuilt image
F:\EBoot.bin   <- 11d94de4... (TEST bootloader, do not touch)
```

Check the hashes before booting. Then reassemble and boot.

**Success:** boots normally, and the "music + browse" freeze is gone.

## Step 6 — The trade-off

PIO mode is slower:

- menu scrolling and list loading are noticeably slower
- library indexing takes longer
- battery may drain a bit faster, because the CPU moves the data instead of the DMA engine

For me it's an easy trade. A Zune that freezes is useless; a Zune that's 20% slower is fine.

## If you want to keep DMA

Two untested ideas: keep DMA with `lookahead` off and big timeouts, or lower
`transfermode` from `0x67` to a slower UDMA mode. Both can stop the device from booting if
the value is wrong, so keep a known-good `nk.bin` on your PC.

## Rollback

Copy your previous `nk.bin` back over `F:\nk.bin`, boot once.

**Never touch `EBoot.bin`** if you're on the TEST bootloader — a retail EBoot cannot be
reverted afterwards.

---

## Credits

This fix is standing on other people's work:

**1977899016-cell/zune30-research** — AUTH196 (the only reason a 1.0-era device can boot
3.3 at all), the strict B000FF container parser and rebuilder, the CE LZX encoder/decoder
for `default.fdf`, the ROM file-table layout, and the registry hive tooling. Everything I
changed here was done with their tools.

**ahlanchuck** — the "Firmware Swapping on Zune 30 (Keel) Models" write-up that explained
the EBoot / NOR / `nk.bin` boot chain before anyone else documented it.

**The Zune community on Baidu Tieba (around 2009)** — the people who kept this hardware
alive long enough for any of us to still be modding it.

If you contributed and I missed you, say so and I'll fix the credits.

---

If you have an SSD-modded Zune: does it freeze the same way? Did DMA-off fix it for you?
Did you find a `transfermode` value that keeps DMA stable? Post your SSD model and I'll add
it to the table.
