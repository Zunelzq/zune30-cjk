# 07 — Making the Zune client sync again after firmware surgery

> **Read this before you flash anything.** This failure is caused by the modification
> process itself, and it is 100% preventable by backing up two files first:
> `G:\zunedb.dat`, `G:\zunedb.BAK`, `G:\drmStore.dat`.
> If you flash first and lose them, you may never get sync back on that unit.

## Why it happens (the actual mechanism)

Three things in this project can damage the device's media/DRM state:

1. **A failed boot formats the 150 MB system partition.** Every time the bootloader rejects
   an image, the device wipes `F:` as a "security measure". That is recoverable — `F:` is
   just firmware files — but it also means the device comes up in a half-initialised state.
2. **Running the 1.0 TEST firmware rewrites the data partition's library.** 1.0 TEST is a
   PMC (Portable Media Center) build: it creates `G:\MediaLibrary.edb` and
   `G:\MediaLibrary_thumbs.edb`, and rebuilds the partition layout in its own image. 3.3
   then finds a library it does not understand.
3. **The vault re-wrap (AUTH196) is RAM-only.** The device cannot persist new security
   state (`persistent_security_write_implemented: false` in the builder's report), so the
   Zune client's cached "relationship" no longer matches what the device presents.

The visible result is always the same: the device enumerates fine, and sync dies with
`C00D11CD (80004005)` while the relationship shows **guest**.

## Symptom

The Zune 4.8 client enumerates the device (name, capacity, art), but every sync fails with:

```
无法同步 / Cannot sync
C00D11CD (80004005)
Relationship: 访客 (guest)
```

## Three independent causes — check them in this order

### 1. Firmware version string is "wrong"

The MTP `DeviceInfo` firmware string is produced by a format string inside `nk.bin`:

```
%02d.%02d.%05d.%02d-%05d     at ROM offset 0x7cda6c (UTF-16LE)
```

The last field is the **bootloader version**. With the TEST loader it is `2`, so the device
reports:

```
03.30.00039.00-00002     instead of    03.30.00039.00-00435
```

The client treats that as an outdated firmware and stops before syncing.

Fix (applied in the shipped image): overwrite the format string with the literal

```
03.30.00039.00-00435
```

It is 20 characters where the format was 24, so it fits in place; the extra printf
arguments are simply ignored. Verify over MTP afterwards — the string must change.

> This alone did **not** fix our device, but it removed one variable.

### 2. Empty/foreign media + DRM stores

If the data partition was ever reformatted (a failed boot formats the *system* partition;
a TEST-firmware detour rewrites the data partition's library), the device ends up with a
fresh, empty library while the Zune client still remembers the old relationship.

Fix: restore the device's **own** backup of:

```
G:\zunedb.dat        (4 MB, SQL CE media library)
G:\zunedb.BAK
G:\drmStore.dat      (54 MB in our case)
```

After this, sync worked immediately on our unit.

### 3. Zune client library state (least likely)

Resetting `%LOCALAPPDATA%\Microsoft\Zune\ZuneStore.sdf` (rename it while Zune is closed)
forces a library rebuild and re-creates the device relationship. In our case this changed
nothing, but it is a cheap step that eliminates the client side.

## Things that do **not** help

* renaming the device to pure ASCII;
* "forgetting" the device in the client UI;
* copying MP3 files into `G:\Content\Music` — neither 3.3 nor 1.0 TEST scans folders;
* raw MTP uploads (`SendObjectInfo` + `SendObject`) — the device resets the USB session.

## Known-good recipe

1. flash the CJK image;
2. boot once, let the device initialise its partitions;
3. power off, put the original `zunedb.dat` + `zunedb.BAK` + `drmStore.dat` back;
4. boot, connect, open Zune, sync.

## If you have no original backup

You will not get the same relationship back. Options: borrow an untouched device to
donate a matching data partition (only works if the vault/cert state matches), or accept a
device without sync.

---

## C00D11CD (80004002) when the failing items are all WMA — Windows removed WMDRM

This is a **different** failure from the one above, and it is not caused by any firmware
modification. Verified on Windows 11 26H2 (build 26300) in November 2026.

### Symptoms

* MP3 files sync fine; **every WMA file fails** (standard WMA *and* WMA Lossless);
* the failed items are listed with a warning icon, and clicking one shows
  `无法同步 / 出现未知错误 / C00D11CD (80004002)`;
* the sync page shows `正在转换 …` ("converting…") for those files;
* the transcode cache directory (`%LOCALAPPDATA%`-configured, in our case `E:\zune\zhuanhuan`)
  **stays empty** — no conversion has ever completed;
* conversion settings are already correct (`仅转换设备不支持的媒体文件`).

### Root cause

`80004002` is `E_NOINTERFACE`. Zune 4.8 encrypts WMA content for the device through
**WMDRM**; its binaries reference `wmdrmdev.dll`, `wmdrmnet.dll`, `wmdrmsdk.dll`,
`WMCreateDRMTranscryptorPriv` and `WMCreateDRMTranscryptionManagerPriv`.

Modern Windows 11 no longer ships those libraries — instead there is a component named
`amd64_microsoft-windows-wmdrmsdk-stub` (a 28 KB placeholder, owner `TrustedInstaller`) and
**no** `wmdrmdev.dll` / `wmdrmnet.dll`. Zune asks COM for the WMDRM interface, gets
`E_NOINTERFACE`, and reports the generic `C00D11CD`.

### Fix (verified working)

Take the five DLLs from a **Windows 7 / 8.1 installation you own** (their `System32`, x64):

```
wmdrmdev.dll
wmdrmnet.dll
wmdrmsdk.dll      (the real one, ~780 KB — not the 28 KB stub)
drmv2clt.dll
drmmgrtn.dll
```

Then, as administrator:

1. copy the first four into `C:\Windows\System32\`;
2. back up the stub:
   `copy C:\Windows\System32\wmdrmsdk.dll <backup>\wmdrmsdk.stub.dll`;
3. stop all Zune processes (the stub is loaded by `Zune.exe`);
4. take ownership and replace:
   `takeown /f C:\Windows\System32\wmdrmsdk.dll /a`
   `icacls C:\Windows\System32\wmdrmsdk.dll /grant Administrators:F`
   `copy /y wmdrmsdk.dll C:\Windows\System32\`;
5. register all five: `regsvr32 /s C:\Windows\System32\<dll>`;
6. restart Zune, connect the device, sync a WMA file.

Success indicators: `Zune.exe` loads `WMDRMSDK.DLL` (version `11.0.7601.x`), the device's used
space grows while syncing WMA, and no `C00D11CD` dialog appears.

### Rollback

Stop Zune, restore `wmdrmsdk.dll` from the backup, delete the four added DLLs, reboot.

> **Licensing:** these DLLs are Microsoft binaries. Do not redistribute them. Every user has
> to extract them from their own Windows installation.

### Why this is not a firmware problem

We compared the CE registry (`default.fdf`) of the official 3.3 image and our modified image:
1,900 keys in both, **0 keys lost**, 1 added (`FontLink\SystemLink`) — see `05-font-mechanism.md`.
The device's format support is unchanged; the failure is entirely on the PC side.

### If you cannot source the DLLs

Two workarounds:

1. sync the WMA files from a Windows 7/8.1 machine (its Zune install still has WMDRM);
2. convert the WMA files to MP3 yourself (e.g. `ffmpeg -i in.wma -c:a libmp3lame -b:a 320k out.mp3`);
   MP3 sync does not need WMDRM.

