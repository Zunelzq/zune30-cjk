# Post 3 — Syncing from Windows 10/11

**Suggested title:**
Zune sync failing on Windows 10/11 with C00D11CD (80004002)? It's WMDRM — here's the real fix

**Flair:** Windows / PSA

---

**TL;DR** — If MP3 syncs but WMA and video fail with `C00D11CD (80004002)`, your PC is
missing WMDRM. Windows 10 1607+ removed the components and Windows 11 26H2 ships only a
28 KB stub. Restoring the Windows 7 WMDRM DLLs fixes it. There's a second, different cause
for *video-only* failures covered at the end.

---

## Is this you?

- MP3 files sync fine
- **WMA (including lossless) all fail**
- Video sync fails
- Error `C00D11CD (80004002)`
- Zune shows "converting…" and then errors out
- Reinstalling Zune, resetting the device, or rebuilding `ZuneStore.sdf` doesn't help
- The device itself is fine — it plays what's already on it

## What `80004002` means

`0x80004002` is `E_NOINTERFACE` — a COM error meaning "the interface you asked for does not
exist". That's a Windows-side error, not a device error. The device never got a chance to
refuse anything.

Zune encrypts content with **WMDRM** before writing it to the device. When the WMDRM
components are missing, creating the transcryptor fails immediately.

**This is why even DRM-free WMA files fail.** It's not about licensing — Zune puts
everything it syncs into a device-bound container.

## Why it happens

Windows 10 1607 and later progressively removed WMDRM. Windows 11 26H2 goes further: the
`wmdrmsdk-stub` package ships a 28 KB `wmdrmsdk.dll` that does nothing, and
`wmdrmdev.dll` / `wmdrmnet.dll` are simply absent.

Zune 4.8 was written in 2011 and expects the real thing.

## The fix

You need five DLLs from a **Windows 7 or 8.1 x64** installation:

```
wmdrmdev.dll    wmdrmnet.dll    wmdrmsdk.dll    drmv2clt.dll    drmmgrtn.dll
```

They're Microsoft system files, so please take them from your own old Windows install or
an old PC — I won't redistribute them, and neither should you.

### Steps

1. **Close Zune** (including the tray icon).
2. **Back up** the current `C:\Windows\System32\wmdrmsdk.dll` somewhere safe.
3. Copy the other four DLLs into `C:\Windows\System32`.
4. `wmdrmsdk.dll` is owned by TrustedInstaller, so it needs two commands in an **admin**
   prompt first:

   ```
   takeown /f C:\Windows\System32\wmdrmsdk.dll /a
   icacls C:\Windows\System32\wmdrmsdk.dll /grant Administrators:F
   ```

   Then copy the real `wmdrmsdk.dll` over it.
5. Register all five:

   ```
   regsvr32 /s C:\Windows\System32\wmdrmdev.dll
   regsvr32 /s C:\Windows\System32\wmdrmnet.dll
   regsvr32 /s C:\Windows\System32\wmdrmsdk.dll
   regsvr32 /s C:\Windows\System32\drmv2clt.dll
   regsvr32 /s C:\Windows\System32\drmmgrtn.dll
   ```

   (`regsvr32 /s` returns success even when it does nothing — verify with the check below.)
6. Reboot once. Then start Zune and try a WMA and a video.

### Verify it actually took

With Zune running, check the loaded module:

```powershell
Get-Process Zune | ForEach-Object { $_.Modules } |
  Where-Object { $_.ModuleName -match 'WMDRM' } |
  Select-Object ModuleName, FileVersion
```

You want `WMDRMSDK.DLL` around **11.0.7601.x** (Windows 7). If you see nothing, the DLL
isn't being loaded — most often because the file copy didn't replace the stub.

### Rollback

Restore the backed-up `wmdrmsdk.dll`, delete the four other DLLs, reboot. Nothing else on
the system depends on them in a way that breaks.

## If only video fails

That's a **different** root cause, same error code. The community tool **Zune Modding
Helper** ships a working `WMVCORE.DLL` and patches `ZuneEncEng.dll` so it loads that copy
from the Zune folder instead of the system one. If WMA syncs fine and only video fails,
try that first — it doesn't touch system files at all.

## If you get C00D11CD (80004005) instead

Different code: `0x80004005` is a generic failure, usually device library / DRM state, not
the PC. The usual fix is restoring the device's library files (`zunedb.dat`,
`zunedb.BAK`, `drmStore.dat`) from a backup. If you never backed them up, a sync-relationship
reset in Zune can help.

## Games

Built-in games are installed as content packages with licenses in `drmStore.dat`. Copying
the `.zcp` files into the content folder does **not** install them — they appear in the menu
and exit immediately when launched. They need the licensed install path (an official
firmware/device restore on a stock device), which is why a Zune that has been wiped or
re-flashed can lose its games permanently.

If your games still launch but won't sync, the WMDRM fix above may be enough — worth trying
before anything drastic.

---

If this fixes your sync, post your Windows build and the WMDRMSDK version that ended up
loaded — it helps map which Windows versions still ship anything usable.
