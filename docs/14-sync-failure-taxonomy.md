# Sync failures: a taxonomy

> "Zune won't sync" is not one problem. Over the device's life there have been at least
> seven independent failure modes, and they produce overlapping symptoms and the same
> error code. This document separates them, so you can tell which one you are hitting
> before you start changing things.

**Scope:** Zune 30 / 80 / HD with the Zune 4.8 desktop software, on Windows 7 through 11.
Device-side firmware surgery is covered in `07-sync-fix.md`; this file is the map.

---

## 0. The one-paragraph version

Zune wraps everything it writes to the device in a device-bound DRM container. That single
design decision creates most of the failure modes: it needs WMDRM on the PC, a matching
license state on the device, a valid pairing relationship between the two, and a working
storage path. Remove or corrupt any of those and the sync fails — often with the same
`C00D11CD` family of errors.

---

## 1. Who fails, what it looks like

| # | Failure class | Typical symptom | Where the cause is |
|---|---|---|---|
| A | PC missing WMDRM | MP3 syncs, WMA + video fail, `80004002` | Windows |
| B | WMVCORE mismatch | **only video** fails, same `C00D11CD` | Windows / Zune install |
| C | Device library / DRM store damaged | `80004005`, stalls, empty library | Device (`G:`) |
| D | Pairing / ownership lost | "belongs to another account", guest mode | Device + PC |
| E | Licensing gone (service shutdown) | purchased/rented content never syncs | Microsoft servers |
| F | Storage hardware | sync hangs, device freezes or disconnects | SSD/HDD, ribbon |
| G | Windows plumbing | device not detected at all | driver / service / installer |

Everything below is the detailed version of that table.

---

## 2. Class A — the PC is missing WMDRM

**Symptom.** MP3 files sync fine. Every WMA (including lossless) fails. Video fails. The
error is `C00D11CD (80004002)`. The Zune UI shows "converting…" and then gives up.

**Cause.** Zune encrypts WMA and video with WMDRM before writing them to the device. That
is not a licence check — even a DRM-free WMA is wrapped. Windows 10 1607+ progressively
removed WMDRM; Windows 11 26H2 ships only a 28 KB `wmdrmsdk-stub`. Zune asks for an
interface that no longer exists, and `0x80004002` is literally `E_NOINTERFACE`.

**Diagnosis.** With Zune running:

```powershell
Get-Process Zune | ForEach-Object { $_.Modules } |
  Where-Object { $_.ModuleName -match 'WMDRM' } |
  Select-Object ModuleName, FileVersion
```

No output = the components are missing or stubbed.

**Fix.** Restore `wmdrmdev.dll`, `wmdrmnet.dll`, `wmdrmsdk.dll`, `drmv2clt.dll`,
`drmmgrtn.dll` from a Windows 7 / 8.1 x64 install, then `regsvr32` each. Full procedure and
rollback in `07-sync-fix.md`.

**Why MP3 still works:** MP3 is copied without the DRM wrapper. That asymmetry is the
fastest way to recognise this class.

---

## 3. Class B — WMVCORE, video only

**Symptom.** WMA syncs correctly, but video fails with the same `C00D11CD`. Sometimes the
conversion step completes and the write still fails.

**Cause.** Different component: `ZuneEncEng.dll` loads `WMVCORE.dll`, and the version
shipped by newer Windows is not compatible with the encoder pipeline Zune expects.

**Fix.** The community tool *Zune Modding Helper* ships a working `WMVCORE.DLL` and patches
`ZuneEncEng.dll` so it loads the copy from the Zune folder instead of the system one. It
touches no system files.

**How to tell A and B apart:** try a WMA. If WMA works and only video fails, it's B. If
WMA also fails, it's A (or both).

---

## 4. Class C — the device library or DRM store is damaged

**Symptom.** `C00D11CD (80004005)` (note: 05, not 02), sync stalls at a percentage, the
device library looks empty or duplicated, or the device reboots mid-sync.

**Cause.** The device keeps three files on the data partition (`G:`):

| File | Role |
|---|---|
| `zunedb.dat` | media library database |
| `zunedb.BAK` | its backup |
| `drmStore.dat` | licence / DRM state |

They get damaged by interrupted writes, failed firmware flashes, or the device formatting
the 150 MB partition after a bad boot. Restoring the firmware does **not** restore these.

**Fix.** Copy your own backups back:

```powershell
Copy-Item zunedb.dat, zunedb.BAK, drmStore.dat G:\ -Force
```

Then reboot the device before opening Zune.

**Prevention:** before any firmware work, copy those three files to your PC. This is the
single most valuable backup on the device.

---

## 5. Class D — pairing / ownership

**Symptom.** Zune says the device belongs to another account, or the device shows up as a
guest. Sync is refused, or the library is wiped and re-synced from scratch.

**Cause.** The sync relationship lives on both sides — the PC's Zune database and the
device's library/DRM state. Reinstalling Windows, restoring the device, or using a second
PC can leave the two out of step. Running firmware experiments on the device can do the
same thing.

**Fix.** Use Zune's "change sync relationship" / "forget device" and re-pair. Expect the
library to be rebuilt: in our case it re-transferred 17 GB.

**Note.** This is a *state* problem, not a hardware problem — the device is fine.

---

## 6. Class E — the licences no longer exist

**Symptom.** Content that used to sync (or used to play on the device) can no longer be
transferred. Purchased or subscription tracks fail regardless of format or PC.

**Cause.** Zune Marketplace was retired in 2012 and the services were shut down in 2015.
Licences were issued by Microsoft servers that no longer answer. A device reset or a
reinstall can make previously licensed content unusable.

**Fix.** There is no technical fix for expired or unobtainable licences. Practical options:

- keep a working device + PC pair untouched, so existing licences stay valid;
- treat DRM-free files (MP3, your own WMA rips) as the long-term library;
- accept that "purchased" content may be unplayable on a reset device.

This class is the reason "back up before you touch anything" is not paranoia.

---

## 7. Class F — storage hardware

**Symptom.** Sync starts and then hangs; the device freezes or disappears from USB; the
device freezes during playback + library browsing even outside sync.

**Cause.** Either the drive is failing, the ZIF ribbon is loose, or — with an SSD swap —
the PATA driver's DMA handling falls behind a drive that answers in microseconds.

**Fix.**

1. Reseat or replace the ribbon (most common physical cause).
2. Check the drive in a ZIF→USB adapter; if a PC can read and partition it, the drive is
   probably fine.
3. If it only freezes under load after an SSD swap, see the DMA fix:
   `dma = 0` in `drivers\builtin\pmc_atapi_mx31\device0` — documented in `13-field-notes.md`
   and the SSD write-up under `docs/announcements/reddit/`.

---

## 8. Class G — Windows plumbing

**Symptom.** The device is not detected at all; Zune spins on "connecting"; the installer
fails; the device shows up under "other devices".

**Causes and checks.**

| Check | How |
|---|---|
| Zune communication service | `Get-Service WMZuneComm, ZuneWlanCfgSvc` |
| MTP/WPD driver state | Device Manager → Portable Devices |
| USB port / cable | try another port, prefer a rear port, no hub |
| Zune 4.8 installer on modern Windows | compatibility mode, or a community repack |
| Device in a bad state | hold Back+Down until it powers off, then reboot |

**Note.** The device only exposes storage over MTP **after** MTPZ authentication. Without a
working Zune stack the device may show "charging" and no storage at all — that is normal,
not a fault. See `12-mtpz-protocol.md`.

---

## 9. Decision tree

```
Can the PC see the device at all?
├─ no  → Class G (driver / service / cable / device state)
└─ yes
   ├─ Does MP3 sync?
   │  ├─ no  → Class C (device library) or Class D (pairing) or Class F (storage)
   │  └─ yes
   │     ├─ Does WMA sync?
   │     │  ├─ no  → Class A (WMDRM)
   │     │  └─ yes
   │     │     └─ Does video sync?
   │     │        ├─ no  → Class B (WMVCORE)
   │     │        └─ yes → then the failure is content-specific: Class E
   └─ Does it only fail for content you bought/rented?
      └─ yes → Class E (licensing, no technical fix)
```

---

## 10. Quick error-code map

| Code | Most likely class |
|---|---|
| `C00D11CD (80004002)` | A (WMDRM) |
| `C00D11CD (80004005)` | C (device library / DRM store) |
| `C00D11CD`, video only | B (WMVCORE) |
| "belongs to another account" | D (pairing) |
| Device not listed | G (plumbing) |
| Sync hangs mid-transfer | F (storage) |
| Content specific, format-independent | E (licensing) |

---

## 11. Before you touch anything

1. Copy `G:\zunedb.dat`, `G:\zunedb.BAK`, `G:\drmStore.dat` to your PC.
2. Copy your current `F:\nk.bin` and `F:\EBoot.bin`.
3. Note the device's firmware version and the Zune software version.
4. Try a **WMA and a video** — the pattern of what succeeds is the fastest diagnostic you
   have.

The rest of this repository is about the cases where fixing the PC is not enough.
