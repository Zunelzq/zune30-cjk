# Post 1 — SSD freeze fix

**Suggested title:**
Zune 30 SSD mod keeps freezing while playing music? It's the PATA driver's DMA mode — here's the fix

**Flair:** Modding / PSA

---

**TL;DR** — If your SSD-swapped Zune 30 freezes when you listen to music *and* browse the
library, the problem is not your SSD and not "old firmware". It's the 2006-era PATA driver
running in DMA mode against a drive that answers thousands of times faster than the HDD it
was designed for. Disabling DMA inside the firmware registry fixes it, at the cost of slower I/O.

---

## The symptom

- Small chance of a freeze when switching menus
- **High chance of a freeze while listening to music and scrolling the song list**
- The device hangs (frozen frame or black screen) — it does *not* reboot
- With the original 30 GB HDD, it never happens

This comes up a lot in SSD-mod threads, and the usual answers are "your SSD is
incompatible" or "the ribbon is loose". Both can be true. In my case neither was.

The drive is a **Samsung MCCOE64GEMPP-01A** (1.8" ZIF, 2008, the MacBook Air gen-1 part).
512-byte logical and physical sectors, healthy, MBR intact, normal TFAT clusters.

## What the device itself said

`G:\DumpFiles` keeps kernel dumps. Mine had seven:

```
exception code : 0xC0000005 (access violation)
modules listed : ddraw_ipu_sdc.dll, pmicsdk_atlas.dll, battdrvr_atlas.dll
cedevice.log   : FreeStore = 139,208  (≈136 KB free)
```

The important detail: **the number of dumps never increased** while I was reproducing the
freezes. So the everyday freezes are *hangs*, not crashes. That points at I/O stalling.

## The cause

The disk driver is `pmc_atapi_mx31`, written for a spinning disk. Its defaults:

| Registry value | Default |
|---|---|
| `drivers\builtin\pmc_atapi_mx31\softresettimeout` | 48 |
| `...\statuspollcycles` | 2000 |
| `...\statuspollcyclepause` | 400 |
| `...\device0\dma` | **1** |
| `...\device0\lookahead` | 1 |
| `...\device0\writecache` | 1 |
| `...\device0\transfermode` | 0x67 |

A HDD answers a read in ~10 ms, so requests queue naturally. An SSD answers in
microseconds, the interrupt rate explodes, and the old DMA completion handling falls
behind — the driver waits forever, and the whole system hangs.

## What I tried

| Change | Result |
|---|---|
| `softresettimeout` 48 → 200, `writecache` 1 → 0 | Still freezes |
| Longer timeouts (500/4000), `lookahead` = 0 | Untested |
| **`dma` = 0 (PIO)**, `lookahead` = 0, `writecache` = 0, timeouts 800/6000/2000 | **No more freezes** |

So the timeouts were a red herring. The DMA path itself is the problem.

## The fix

This needs a modified `nk.bin`, because the registry is compiled into the firmware image.
On stock 3.3 you cannot change these values — which is probably why the community never
had a fix.

Assuming you already flash a custom 3.3 image (AUTH196-patched, TEST bootloader), the values
live in `default.fdf` inside `nk.bin`:

```
drivers\builtin\pmc_atapi_mx31
    softresettimeout      = 800
    statuspollcycles      = 6000
    statuspollcyclepause  = 2000

drivers\builtin\pmc_atapi_mx31\device0
    dma                   = 0      <-- the one that matters
    lookahead             = 0
    writecache            = 0
```

Rebuild the image, flash it, done. No freezes on my unit since.

## The trade-off

PIO mode is slower. Menu scrolling and library indexing are noticeably slower, and battery
life may be slightly worse (the CPU moves data instead of the DMA engine).

For me it's an easy trade: a Zune that freezes is useless; a Zune that's 20% slower in the
menus is fine.

## If you want to keep DMA

Two ideas I haven't verified for stability:

1. Keep DMA, disable lookahead, raise the timeouts — may be enough for some drives.
2. Lower `transfermode` from `0x67` to a slower UDMA mode — keeps DMA, reduces the chance
   of the descriptor handling falling behind.

Both require flashing, and a bad value can stop the device from booting. Always keep a
known-good `nk.bin` on your PC.

## Check the hardware too

Even with the fix, do these first — they're free and they explain a lot of "random" freezes:

- Reseat or replace the ZIF ribbon (most common physical cause)
- Clean the SSD contacts
- Make sure the SSD isn't an old worn unit with long internal retries

## Rollback

Keep your previous `nk.bin`. To revert, copy it back over `F:\nk.bin` and boot once.

**Do not touch `EBoot.bin`** if you're on the TEST bootloader — a retail EBoot cannot be
reverted afterwards.

---

If you have an SSD-modded Zune: does it freeze the same way? Does DMA-off fix it for you?
Did you find a `transfermode` value that keeps DMA stable? I'd love to compare parameter sets.
