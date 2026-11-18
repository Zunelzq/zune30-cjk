# Project status — November 2026

A consolidated view of where this device stands after the firmware, font, storage and
transfer work. Hashes are the first eight hex digits of SHA-256.

## 1. Images

| Image | sha8 | USB identity | Zune 4.8 | FLAC playback | FLAC import | SSD fix |
|---|---|---|---|---|---|---|
| `CLEAN-FLAC-ZUNE` | **23C8D9B9** | `045E:0710` MTPZ | ✅ | ✅ | ❌ | ✅ |
| `CJK-FLAC` (MTP build) | **6A996991** | `1209:0001` MTP | ❌ | ✅ | ✅ | ✅ |
| `SAFE2` | 230A8B43 | `1209:0001` MTP | ❌ | ❌ | ❌ | ✅ |
| `CLEAN` | E66595BE | `1209:0001` MTP | ❌ | ❌ | ❌ | ❌ |
| `SAFE1` | ABE47A52 | `1209:0001` MTP | ❌ | ❌ | ❌ | ⚠️ |
| original 1.0 TEST | 9D947FEB | `045E:0710` | ⚠️ | ❌ | ❌ | ❌ |
| TEST bootloader | 11D94DE4 | — | — | — | — | — |

`CLEAN-FLAC-ZUNE` is the current daily image: Zune software syncs MP3/WMA with full
metadata, and FLAC tracks already on the device play normally.

`CJK-FLAC` is the transfer image: its generic-MTP identity lets Explorer write files,
which is the only way to add new FLAC tracks.

## 2. Why two images

The USB function driver configuration decides everything:

```
HKLM\Drivers\USB\FunctionDrivers\MtpClientDrvUsb
    compatibleid = MTPZ | MTP
    vid/pid      = 045E:0710 | 1209:0001
```

- `MTPZ + 045E` → the Zune driver binds, Zune 4.8 authenticates (MTPZ) and owns the
  session. Explorer/WPD access is closed.
- `MTP + 1209` → generic WPD driver, Explorer can write, but Zune 4.8 has no matching
  driver (its INF only lists Microsoft VIDs).

Swapping these values in the MTP build breaks USB enumeration entirely (the build lacks
the MTPZ components), which is why the reverse direction was used: start from `CLEAN`
(stock MTPZ) and add the FLAC registrations.

## 3. Adding FLAC — workflow

```
1. Flash CJK-FLAC (6A996991) via the 150 MB partition
2. Boot, connect USB, drag .flac into Storage\Music
3. Flash CLEAN-FLAC-ZUNE (23C8D9B9) back
4. The new tracks stay in the library and play in Zune mode
```

Both images share `G:\zunedb.dat`, so the library survives the switch. Batch additions to
limit disk swaps; wire flashing is not available (see §6).

## 4. Metadata capability (measured on hardware)

| Property | Code | Writable | Notes |
|---|---|---|---|
| Title | `0xDC44` | ✅ | immediate |
| Artist | `0xDC46` | ✅ | immediate |
| Genre | `0xDC8C` | ✅ | not the standard `0xDC4E` |
| Album | `0xDC4F` | ❌ `0xA803` | firmware refuses |
| File name | `0xDC07` | ⚠️ | normalised; `.flac` becomes `.z` |

Album is a separate object (format `0xBA03`, name `<artist>--<album>.alb`, living under
`Albums`). Tracks are attached by a library association that MTP cannot create
(`MoveObject` into an album returns `0x201A`).

`zunesync` (in `tools/`) can patch Title/Artist/Genre on objects already on the device.

## 5. Zune 4.8 and FLAC

- No `flac` string exists in any Zune binary; the library importer never picks FLAC up.
- Installing Xiph DirectShow codecs does not change that.
- Patching the extension list in `ZuneMde.dll` (`.dvr-ms` → `.flac`) does not change it.
- However, Zune's MTP layer *does* read FLAC objects from the device and lists them in the
  device pane — only library import is missing.

Making Zune sync FLAC would require patching its media import pipeline (multiple layers),
not a registry tweak.

## 6. Wire flashing: not available

The only firmware channel is the three files on the 150 MB partition
(`nk.bin`, `recovery.bin`, `EBoot.bin`). Zune's official update path validates signatures
and restores the retail bootloader, which destroys a TEST-bootloader setup. No third-party
USB flashing protocol was found.

## 7. Recurring limits

| Limit | Cause |
|---|---|
| Album / cover art cannot be written | firmware rejects the property; association is library-internal |
| Playlists cannot receive tracks | `References` not exposed to MTP |
| FLAC objects are named `*.z` | no extension mapping for the format; name is cosmetic |
| Zune cannot import FLAC | hard-coded media importer |
| MTPZ cannot be driven from Windows WPD | write commands require an authenticated session |

## 8. Recovery

```
1. Remove the drive, connect via ZIF→USB
2. Verify F:\nk.bin, F:\EBoot.bin (11D94DE4), F:\Fonts\ZCJKBoot.exe and the font size
3. Replace nk.bin with a known image if needed
```

Never let Zune "update/restore device"; never modify `EBoot.bin`.

## 9. Repository map

| Path | Content |
|---|---|
| `docs/01`–`docs/13` | boot chain, AUTH196, fonts, sync fix, MTPZ notes, field notes |
| `docs/14-sync-failure-taxonomy.md` | seven independent sync failure classes |
| `docs/15-mtp-metadata.md` | what MTP can and cannot write |
| `docs/16-project-status.md` | this file |
| `tools/zunesync/` | metadata patch tool (offline tests included) |

Private material (device vault, NOR dump, MTPZ key material) is deliberately not in this
repository.
