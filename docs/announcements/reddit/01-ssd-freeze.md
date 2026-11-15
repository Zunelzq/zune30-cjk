# Post 1 — SSD freeze fix

**Title:** Zune 30 SSD mod keeps freezing while playing music? It's the PATA driver's DMA mode — here's the fix

**Flair:** Mods/Hacks

---

**TL;DR** — If your SSD-swapped Zune 30 freezes when you listen to music *and* browse the
library, the problem isn't the SSD. It's the 2006-era PATA driver running in DMA mode
against a drive that answers thousands of times faster than the HDD it was designed for.
Disabling DMA inside the firmware fixes it, at the cost of slower I/O.

> **Prerequisite:** this needs a bootable custom image. The tooling that makes one —
> AUTH196, the CE BIN/LZX parsers, the registry hive editor — comes from
> **https://github.com/1977899016-cell/zune30-research**. Start there first.

---

## What you need

| Item | Where |
|---|---|
| A Zune 30 already running custom firmware | see note below |
| ZIF→USB adapter + the usual tools to open the device | — |
| Python 3 + this repo's scripts | https://github.com/Zunelzq/zune30-cjk |
| A known-good `nk.bin` to fall back to | back it up first |

> **Note:** this requires a modified `nk.bin`. On stock retail firmware the registry is
> read-only and none of this is possible. If you haven't done the TEST bootloader +
> AUTH196 path yet, this guide won't help you — sorry.

---

## Step 1 — Confirm it's this problem

Check these three:

- [ ] MP3 playback works fine
- [ ] Freeze happens **only under concurrent load**: music playing + scrolling the library
- [ ] The original HDD never does this

If yes, continue. If it freezes at random even when idle, suspect the ribbon instead.

## Step 2 — Rule out the hardware (5 minutes)

Do this before flashing anything:

1. Reseat the ZIF ribbon; if you have a spare, swap it.
2. Check the SSD contacts for oxidation.
3. Make sure the SSD isn't a worn unit with long internal retries.

A bad ribbon produces exactly the same "random freeze" symptom.

## Step 3 — Understand what you're changing

The driver is `pmc_atapi_mx31`. Its defaults assume a spinning disk:

| Registry value | Default | Change to |
|---|---|---|
| `drivers\builtin\pmc_atapi_mx31\softresettimeout` | 48 | **800** |
| `...\statuspollcycles` | 2000 | **6000** |
| `...\statuspollcyclepause` | 400 | **2000** |
| `...\device0\dma` | 1 | **0** ← the one that matters |
| `...\device0\lookahead` | 1 | **0** |
| `...\device0\writecache` | 1 | **0** |

The first attempt I made only raised the timeouts and turned off the write cache — it
**did not help**. Disabling DMA did.

## Step 4 — Edit the registry inside `default.fdf`

The registry lives inside `nk.bin`, in the CE hive `default.fdf`:

1. Extract `default.fdf` from your image (decompress it — it's CE LZX).
2. Add/replace the six values above.
3. Recompress it back into the **same fixed ROM slot**.
4. Update the ROM file table entry (size, compressed size, flags).
5. Rebuild the B000FF record list and recompute every checksum.
6. **Re-parse the result and verify it byte-for-byte.**

Step 6 is not optional. Wrong checksums give you a progress bar and then a black screen.

The scripts in the repo do all of this; do not hand-edit a container.

## Step 5 — Flash and verify

With the drive on the adapter:

```
F:\nk.bin      <- your rebuilt image
F:\EBoot.bin   <- 11d94de4... (TEST bootloader — do not touch)
```

```powershell
Get-FileHash F:\nk.bin -Algorithm SHA256      # must match what you built
Get-FileHash F:\EBoot.bin -Algorithm SHA256   # must start with 11D94DE4
```

Reassemble and boot.

**Success:** device boots normally, and the "music + browse" freeze is gone.

## Step 6 — Live with the trade-off

PIO mode is slower:

- menu scrolling and list loading are noticeably slower
- library indexing takes longer
- battery may drain slightly faster (CPU moves data instead of the DMA engine)

For me it's an easy trade. A Zune that freezes is useless; a Zune that's 20% slower is fine.

## If you want to keep DMA

Two untested ideas:

1. Keep DMA, disable lookahead, raise timeouts.
2. Lower `transfermode` from `0x67` to a slower UDMA mode.

Both can prevent boot if the value is wrong. Keep a known-good `nk.bin` on your PC at all
times.

## Rollback

Copy your previous `nk.bin` back over `F:\nk.bin`, boot once.

**Never touch `EBoot.bin`** if you're on the TEST bootloader — a retail EBoot cannot be
reverted afterwards.

---

## Links

**The project this is built on:**

- **https://github.com/1977899016-cell/zune30-research** — AUTH196 builder, CE BIN/LZX
  tooling, registry hive tooling. Start here if you don't have a custom image yet.

**Everything else:**

- This write-up and the image scripts: https://github.com/Zunelzq/zune30-cjk
- 7-Zip (for the firmware cab): https://www.7-zip.org/

---

If you have an SSD-modded Zune: does it freeze the same way? Did DMA-off fix it? Did you
find a `transfermode` value that keeps DMA stable? Post your SSD model and I'll add it to
the table.
