# Reddit post — SSD freeze fix (r/Zune)

## Title options

1. **Fixing the "SSD mod freezes" problem on Zune 30 — root cause found (DMA timing), with a working fix**
2. **Zune 30 + SSD keeps freezing while playing music and browsing? It's the PATA driver's DMA mode. Here's the fix.**
3. **PSA: your Zune 30 SSD mod freezes because of DMA, not the SSD itself — parameters inside the fix**

---

## Body

**TL;DR** — Zune 30s with an SSD swap freeze when the drive is under concurrent load
(music playing + browsing the library). The cause is not the SSD and not "old firmware".
It's the 2006-era PATA driver using DMA with timing assumptions that a modern SSD breaks.
Disabling DMA (and a few related settings) inside the firmware registry fixes it completely,
at the cost of slower I/O.

---

### The symptom

- Small chance of a freeze when switching menus
- **High chance of a freeze when listening to music *and* browsing the song list**
- The device just hangs (frozen frame or black screen) — it does not reboot
- The original 30 GB HDD never does this

This seems to be common in the SSD-mod community, and the usual answer is
"your SSD is incompatible" or "the ribbon is loose". Both can be true, but in my case
neither was: the drive is a Samsung MCCOE64GEMPP-01A (1.8" ZIF, 2008), 512-byte sectors,
healthy, MBR intact, TFAT clusters normal.

### What the device told me

`G:\DumpFiles` keeps kernel dumps. Mine had 7 of them:

```
exception code: 0xC0000005 (access violation)
modules listed: ddraw_ipu_sdc.dll, pmicsdk_atlas.dll, battdrvr_atlas.dll
cedevice.log:   FreeStore = 139,208 (≈136 KB free)
```

But the number of dumps **never increased** while I was reproducing the freezes —
so the everyday freezes are *hangs*, not crashes. That points at I/O stalling,
not at a UI bug.

### The actual cause

The disk driver is `pmc_atapi_mx31` — a PATA driver written for a spinning disk.
Its defaults assume a slow device:

| Registry value | Default |
|---|---|
| `drivers\builtin\pmc_atapi_mx31\softresettimeout` | 48 |
| `...\statuspollcycles` | 2000 |
| `...\statuspollcyclepause` | 400 |
| `...\device0\dma` | **1** |
| `...\device0\lookahead` | 1 |
| `...\device0\writecache` | 1 |

A HDD answers a read in ~10 ms, so requests naturally queue.
An SSD answers in microseconds, so the interrupt rate explodes and the old DMA
handling can miss completion — the driver waits forever and the whole system hangs.

### What I tried (and what didn't work)

| Change | Result |
|---|---|
| `softresettimeout` 48 → 200, `writecache` 1 → 0 | Still freezes |
| Longer timeouts (500/4000), `lookahead` = 0 | Untested |
| **`dma` = 0 (PIO mode)**, `lookahead` = 0, `writecache` = 0, timeouts 800/6000/2000 | **No more freezes** |

So the timeouts were a red herring. The DMA path itself is the problem.

### The fix (only applies if you already run custom firmware)

This needs a modified `nk.bin`, because the registry is compiled into the image.
If you're on the stock 3.3 image you cannot change these values — that's why the
community never had a fix: on retail firmware they're read-only.

Assuming you already flash a custom 3.3 image (AUTH196-patched, TEST bootloader),
the values live in `default.fdf` inside `nk.bin`:

```
drivers\builtin\pmc_atapi_mx31
    softresettimeout      = 800
    statuspollcycles      = 6000
    statuspollcyclepause  = 2000

drivers\builtin\pmc_atapi_mx31\device0
    dma                   = 0     <-- the important one
    lookahead             = 0
    writecache            = 0
```

Rebuild the image, flash it, done.

### The trade-off

PIO mode is slower. You will notice it when scrolling long lists and when the
device indexes new music. Battery life may be slightly worse because the CPU does
the copying instead of the DMA engine.

For me it's a clear win: a Zune that freezes is useless; a Zune that is 20% slower
in menus is fine.

### If you want to keep DMA

Two things worth trying (I haven't verified stability):

1. Keep DMA on but disable lookahead and raise timeouts (may be enough for some drives)
2. Lower `transfermode` from `0x67` to a slower UDMA mode — keeps DMA, reduces the
   chance of the descriptor handling falling behind

Both need flashing, and a bad value can stop the device from booting.
Keep a known-good `nk.bin` on your PC at all times.

### Before you blame firmware: check the hardware

Even with the fix, do these first — they're free and they explain a lot of "random" freezes:

- Reseat / replace the ZIF ribbon (most common physical cause)
- Check the SSD's contacts for oxidation
- Make sure the SSD is not an old worn-out unit with long internal retries

### Rollback

Keep your previous `nk.bin`. To revert, copy it back over `F:\nk.bin`, boot once.
Do **not** touch `EBoot.bin` if you're on the TEST bootloader — a retail EBoot
cannot be reverted afterwards.

### Discussion

If you have an SSD-modded Zune, I'd like to know:

- Does it freeze the same way (music + browsing)?
- Does the DMA-off change fix it for you?
- Did you try keeping DMA but lowering the transfer mode?

I'll happily compare parameter sets — especially the `transfermode` value, since
that's the one that could give us stability *and* speed.
