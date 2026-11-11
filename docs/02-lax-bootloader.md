# 02 — The 1.0 TEST bootloader (the unlock)

## What it is

A 2006-era engineering-sample bootloader, shipped inside the 1.0 TEST (build 186) firmware
package. On the splash screen it reports:

```
Version 3.30 (39)        ← whatever nk.bin you give it
Bootloader 2             ← this loader's own version
```

| Property | Value |
|---|---|
| File name in package | `EBoot.bin` |
| sha256 | `11D94DE42D80BCD0…` |
| Size | 262,339 B |
| Signed by | a key present in production eFuses (HAB accepts it) |
| Verifies `nk.bin` | **no** |

Because it does not check `nk.bin`, any WinCE image can be loaded — including the
`AUTH196`-patched official 3.3 and the CJK-modified images in this project.

## How it gets installed

EBoot lives in NOR. The device updates NOR from the disk when a valid `EBoot.bin` is
present on the 150 MB system partition at boot:

1. copy the 1.0 TEST `EBoot.bin` to `F:\EBoot.bin`;
2. boot the device once;
3. the loader is flashed into NOR;
4. splash shows `Bootloader 2`.

## Why it can never be replaced by a retail 3.3 loader

* The retail EBoot is a different binary; installing it requires the Zune software
  "restore" path or a CAB update.
* Once retail EBoot is in NOR, it verifies `nk.bin` — so a modified image no longer boots.
* HAB prevents writing an arbitrary EBoot, so the TEST loader cannot simply be patched
  back in afterwards.

> **Rule: never let the Zune software "restore"/"repair" the device, and never apply a
> firmware CAB update.** Those operations overwrite NOR with the retail loader and the
> project is over.

## Other observations

* The version suffix in the MTP firmware string is derived from this loader
  (`03.30.00039.00-00002`), which makes the Zune client think the firmware is outdated.
  That is why the image also patches the version format string (see `07-sync-fix.md`).
* `nk.bin` from the 1.0 TEST package itself boots to a red-`TEST` 1.0 UI. It is a useful
  fallback image but has no 3.3 features.
