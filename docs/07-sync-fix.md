# 07 — Making the Zune client sync again after firmware surgery

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
