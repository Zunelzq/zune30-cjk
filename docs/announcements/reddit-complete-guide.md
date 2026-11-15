# Reddit guide — Zune 30: Chinese text, custom firmware, SSD freezes, PC sync

> Full write-up of everything I did to a Zune 30 (30 GB, first gen, "Keel"):
> native Chinese/Japanese text, a 64 GB SSD swap, and syncing from a modern Windows PC.
>
> Everything below was done on real hardware. Where something is unverified, I say so.

---

## 0. What this guide covers

| Part | What you get | Difficulty |
|---|---|---|
| 1 | Test bootloader (required for anything custom) | Medium, irreversible |
| 2 | Custom 3.3 image that boots on a 1.0-era device (AUTH196) | Hard |
| 3 | **Chinese / Japanese text on the device** | Hard |
| 4 | Flashing and verifying | Easy |
| 5 | **SSD swap freezes — the DMA fix** | Medium |
| 6 | **PC sync on Windows 10/11 (WMDRM fix)** | Easy |
| 7 | Rollback and troubleshooting | — |

**Read section 1 first.** If you are not willing to risk the device, stop there.

---

## 1. Before anything: understand the boot chain

```
Boot ROM (HAB)
   └─> EBoot in NOR  (verifies nk.bin)
          └─> nk.bin from disk (F:\nk.bin)
```

Two facts drive everything else:

1. **The retail EBoot refuses unsigned `nk.bin`.** You cannot run a custom image on it.
2. **The 1.0 TEST EBoot does not check signatures.** It boots whatever `nk.bin` is on disk.

So the entry ticket for custom firmware is the **1.0 TEST bootloader**.

### 1.1 Installing the TEST bootloader

You need the 1.0 TEST firmware package (`Zune01050485(1.0test).cab` — commonly
circulated in the Zune modding community).

Take these five files from it:

```
EBoot.bin        (≈262,339 bytes, sha256 starts with 11d94de4)
recovery.bin
zconfig.dat
pmcver.dat
pmcstore.edb
```

Procedure:

1. Open the device, take the 1.8" drive out, connect it via a ZIF→USB adapter.
2. Back up the whole `F:\` partition first.
3. Copy the five files to `F:\` (overwrite).
4. Reassemble, boot once. The device flashes `EBoot.bin` into NOR itself.
5. The boot screen should now say **Bootloader 2** (some units show a TEST watermark).

Verify with the drive connected to a PC:

```powershell
Get-FileHash F:\EBoot.bin -Algorithm SHA256
# first 8 chars must be 11D94DE4
```

### 1.2 ⚠️ This is a one-way door

Once the TEST EBoot is in NOR:

- **Never** let the Zune software "update device" or "restore device" — it will flash a
  retail EBoot back.
- **Never** install an official firmware `.cab`.
- A retail EBoot cannot be replaced again (the boot ROM checks the signature with an
  eFuse key).

If you are not comfortable with that, stop reading.

---

## 2. AUTH196: why official 3.3 won't boot on an early device

Putting the official 3.3 `nk.bin` behind a TEST bootloader gives you a **black screen**.
The bootloader accepts the image, then 3.3's security stack refuses to start.

Reason: 3.3 expects a **new-format KeyVault**. A 1.0-era device only has the old format,
so 3.3 cannot decode the encrypted credential fields.

### 2.1 What AUTH196 does

A community patch ("AUTH196") makes 3.3 boot by performing a **RAM-only vault re-wrap**:

1. It verifies the stock 3.3 `nk.bin` hash.
2. It injects a small ARM routine into unused executable space at the end of the image.
3. It redirects the KeyVault integrity call to that routine.
4. It adds **your device's own old vault**, compressed, as a private ROM file
   (`\Windows\ZV194.dat`), using an existing data-file slot.
5. It disables the permanent security-area migration path.
6. It rebuilds the ROM file table, lengths and B000FF checksums, then verifies every byte.

At boot the routine: backs up the RAM vault → swaps in your pinned vault → verifies its
digest → converts each field from the old software-decrypt format to the new hardware-
backed format (round-tripping every field) → rebuilds the header → calls the original
validator. On a handled failure it restores the incoming buffer.

### 2.2 Two things that matter

- **The image is per-device.** The pinned vault is *yours*. Flashing your image onto
  another Zune will black-screen it.
- **You need your own vault.** Dump it from your device while it runs 1.0 TEST
  (or read it from a NOR backup).

Upstream tooling: `ZuneDev/Zune30-Research` (build_upgrade.py, rewrap_runtime.asm).
Do not use someone else's vault.

> If your Zune already runs 1.0 TEST and you only want Chinese text, you can skip
> AUTH196 entirely and stay on 1.0 TEST. This guide assumes you want 3.3.

---

## 3. Chinese / Japanese text (the main event)

### 3.1 The misconception

The widespread claim is *"the Zune 3.3 font engine ignores FontLink, so CJK is
impossible"*. That is **wrong**. 3.3 uses GDI, and GDI does process FontLink.

The real problems are much more boring:

| # | Mistake | Symptom |
|---|---|---|
| 1 | Putting the font on `G:` (data partition) | FontLink can't find it |
| 2 | Registering the wrong family name | Font never gets used |
| 3 | Building a loader with the wrong size constant | Loader fails silently |
| 4 | Stripping hinting | Text looks blurry at small sizes |

`\Hard Disk` is the **system** partition — that's `F:`, the 150 MB one, **not** `G:`.

### 3.2 How the mechanism works

Three pieces:

1. **A TTF on the system partition**, e.g. `F:\Fonts\ZuneCJK_UI_20261027.ttf`.
2. **FontLink registry entries** in the firmware, so GDI knows to fall back to it.
3. **A tiny loader** that calls `AddFontResourceW` at boot, because the font is not in ROM.

The registry lives inside `nk.bin` (in `default.fdf`), so this requires a custom image.

### 3.3 Font: build a subset, keep hinting

A full CJK font won't fit any budget, and you don't want one — you want the glyphs your
library actually contains, plus GB2312 if you want general coverage.

Using the upstream `build_cjk_font.py` (or any subsetter):

```powershell
python scripts\build_cjk_font.py --font simsun.ttf --charset charset.txt `
  --keep-hinting --family "Zune UI CJK" `
  --out out\font.ttf --out-packed out\font.packed.bin
```

Measured configurations on my device:

| Charset | Glyphs | Size | Hinting |
|---|---|---|---|
| library + kana + ASCII | 1,819 | 379 KB | off |
| GB2312 + library + kana | 8,011 | 1.9 MB | off |
| **GB2312 + library + kana** | **8,011** | **3.2 MB** | **on** ← recommended |

**Keep hinting.** Without it, small characters look fuzzy; with it, text looks like the
1.0 TEST firmware (which is what people remember as "the good font"). On the FontLink
path the font lives on disk, so size is cheap.

Pick a font you are licensed to use. I used a GB2312 subset of SimSun.

### 3.4 The loader

The device needs `AddFontResourceW` called at boot. A ~2 KB ARM executable does it:

```c
// pseudo-code of what the loader does
h = GetFileSize("\\Hard Disk\\Fonts\\ZuneCJK_UI_20261027.ttf");
if (h != EXPECTED_SIZE) return;        // sanity check baked into the binary
AddFontResourceW(L"\\Hard Disk\\Fonts\\ZuneCJK_UI_20261027.ttf");
SignalStarted();
```

The `EXPECTED_SIZE` constant is compiled in. If your font is 3,359,056 bytes, the
loader must contain that number. Patch it with the upstream `build_font_loader.py`:

```powershell
python build_font_loader.py --font-size 3359056 --out ZCJKBoot.exe
```

Then copy it to `F:\Fonts\ZCJKBoot.exe`.

### 3.5 Registry edits (inside default.fdf)

Add these values to the image's registry hive:

```
[HKLM\Software\Microsoft\FontLink\SystemLink]
"Zegoe UI"            = "\Hard Disk\Fonts\ZuneCJK_UI_20261027.ttf,Zune UI CJK"
"Zegoe UI Light"      = "\Hard Disk\Fonts\ZuneCJK_UI_20261027.ttf,Zune UI CJK"
"Zegoe UI Semibold"   = "\Hard Disk\Fonts\ZuneCJK_UI_20261027.ttf,Zune UI CJK"
```

And make the loader run at boot:

```
[HKLM\Init]
"Launch45" = "\Hard Disk\Fonts\ZCJKBoot.exe"
"Depend45" = "30"          ; wait for the filesystem
"Depend60" = "20,45"       ; depend on something that needs the font
```

> The exact `Depend` numbers matter. If the loader runs before the storage stack is up,
> it silently fails and you get boxes instead of characters.

### 3.6 Putting it together

The image build must, in one pass:

1. decompress `default.fdf` from the image,
2. insert the FontLink keys and the `Init` entries,
3. recompress it into the **same fixed ROM slot** (38,949 bytes in my build),
4. patch the version string so the Zune software doesn't offer an update,
5. rebuild B000FF records and recompute checksums,
6. verify by re-parsing the result.

That last step is not optional. If the record checksums are wrong the device shows a
progress bar and then a black screen.

---

## 4. Flashing and verifying

With the drive on the adapter:

```
F:\nk.bin      <- your custom image (13,956,899 bytes in my case)
F:\EBoot.bin   <- 11d94de4... (TEST bootloader, do not touch)
F:\Fonts\ZuneCJK_UI_20261027.ttf
F:\Fonts\ZCJKBoot.exe
```

Checks before booting:

```powershell
Get-FileHash F:\nk.bin    -Algorithm SHA256   # must match what you built
Get-FileHash F:\EBoot.bin -Algorithm SHA256   # must start with 11D94DE4
```

Then reassemble and boot. Expected result: 3.3 UI, and Chinese/Japanese text renders
instead of boxes.

If you get a black screen: wrong image (typically vault mismatch or a broken record list).
If you get boxes: FontLink/loader problem — check the font path, the family name and the
loader's size constant.

---

## 5. SSD swap freezes — the DMA timing fix

### 5.1 Symptom

After swapping the 30 GB HDD for an SSD:

- small chance of a freeze when switching menus,
- **high chance of a freeze while listening to music and browsing the song list**,
- the device hangs (frozen frame / black screen), it does not reboot,
- the original HDD never does this.

`G:\DumpFiles` contains kernel dumps with `0xC0000005` (access violation) and display /
power driver modules — but the dump count never increases during these freezes.
They are *hangs*, not crashes.

### 5.2 Cause

The PATA driver `pmc_atapi_mx31` was written in 2006 for a spinning disk. Its defaults:

| Value | Default |
|---|---|
| `softresettimeout` | 48 |
| `statuspollcycles` | 2000 |
| `statuspollcyclepause` | 400 |
| `device0\dma` | **1** |
| `device0\lookahead` | 1 |
| `device0\writecache` | 1 |

A HDD answers in ~10 ms, so requests queue naturally. An SSD answers in microseconds,
the interrupt rate explodes, and the old DMA completion handling falls behind —
the driver waits forever and the system hangs.

Raising the timeouts alone did **not** help. Disabling DMA did.

### 5.3 Fix

In `default.fdf`:

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

Rebuild, flash, done. No more freezes on my unit.

**Cost:** PIO mode is slower. Menu scrolling and library indexing are noticeably slower,
and battery life may be slightly worse (the CPU moves the data instead of the DMA engine).
Stability is worth it.

Still on DMA? Two untested ideas: keep DMA with `lookahead=0` and big timeouts, or lower
`transfermode` from `0x67` to a slower UDMA mode. Both can prevent boot if wrong — always
keep a known-good `nk.bin`.

### 5.4 Before blaming firmware

Try these first, they are free:

- reseat or replace the ZIF ribbon (most common physical cause),
- clean the SSD contacts,
- make sure the SSD isn't an old worn unit with long internal retries.

---

## 6. Syncing from Windows 10 / 11 — the WMDRM problem

### 6.1 Symptom

- MP3 syncs fine, **WMA fails**, video fails,
- error `C00D11CD (80004002)` — `E_NOINTERFACE`,
- the Zune UI says "converting…" and then fails,
- reinstalling Zune or rebuilding the library changes nothing.

### 6.2 Cause

Zune wraps content in WMDRM before writing it to the device. Windows 10 1607+ has been
removing WMDRM components; Windows 11 26H2 ships only a 28 KB `wmdrmsdk-stub`.
Zune asks for an interface that no longer exists.

### 6.3 Fix

Restore the real WMDRM components from a Windows 7 / 8.1 x64 install:

```
wmdrmdev.dll   wmdrmnet.dll   wmdrmsdk.dll   drmv2clt.dll   drmmgrtn.dll
```

1. Close Zune.
2. Back up the existing `C:\Windows\System32\wmdrmsdk.dll`.
3. Copy the five DLLs into `C:\Windows\System32`.
   (`wmdrmsdk.dll` is TrustedInstaller-owned: `takeown /f ... /a`, `icacls ... /grant Administrators:F`.)
4. Register them: `regsvr32 /s` each one.
5. Restart Zune, sync a WMA and a video.

Verify: with Zune running, check that it loaded `WMDRMSDK.DLL` v11.0.7601.x.

Alternative for **video only**: the community tool *Zune Modding Helper* ships a working
`WMVCORE.DLL`, patched into the Zune install folder. Different root cause, same error code
— worth trying if WMA sync is fine and only video fails.

---

## 7. Rollback and troubleshooting

### 7.1 Keep these files

```
known-good nk.bin           your last working image
nk.original-1.0TEST.bin     stock 1.0 TEST image
EBoot_bootloader2_TEST.bin  11d94de4...
F:\zfonts*                  nothing needed, fonts live in F:\Fonts
```

### 7.2 Common failures

| Symptom | Cause | Fix |
|---|---|---|
| Progress bar then black screen | broken B000FF records / checksum | rebuild, verify with a parser |
| Immediate black screen | vault mismatch (image not for this device) | use your own vault |
| Boxes instead of CJK | FontLink path/family wrong, loader not running | check `F:\Fonts`, registry, `Init` |
| Freezes only under load | SSD DMA | section 5 |
| `C00D11CD (80004002)` on WMA | host WMDRM missing | section 6 |
| `C00D11CD (80004005)` | device library/DRM state | restore `zunedb.dat`, `zunedb.BAK`, `drmStore.dat` |

### 7.3 ⚠️ Never

- never let Zune update/restore the device (kills the TEST bootloader),
- never flash another device's AUTH196 image,
- never write to the drive in the gaps between B000FF records,
- never trust a build you haven't re-parsed and hash-verified.

---

## 8. What's still open

- **Games**: built-in games live in `G:\Content\1300/1400/1500` as `.zcp` packages with
  licenses in `drmStore.dat`. Copying the packages does **not** install them — launching
  exits immediately. They need the licensed install path (official firmware update on a
  stock device).
- **MTPZ writes**: the device exposes read/write storage only after MTPZ authentication.
  With the right host key data, `mtp-detect` can see the storage, but a full third-party
  file write is still unverified.
- **SSD speed**: a `transfermode` value that keeps DMA and stays stable would give us the
  best of both worlds.

If you test any of these, I'd love the data.

---

*All of this was done on a single Zune 30 with a 64 GB Samsung SSD (MCCOE64GEMPP-01A).
Hashes and parameter tables are from my own images; your ROM slot sizes may differ —
always verify before flashing.*
