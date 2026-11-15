**TL;DR** — MP3 syncs, WMA and video fail with `C00D11CD (80004002)`, and reinstalling
Zune doesn't help? Your PC is missing WMDRM. Windows 10 1607+ removed it; Windows 11 26H2
ships a 28 KB stub. Restoring the Windows 7 WMDRM DLLs fixes it. There's a different cause
for video-only failures, covered at the end.

---

## What you need

| Item | Where |
|---|---|
| A Windows 7 / 8.1 x64 install (or an old PC) | for five DLLs — see step 2 |
| Admin rights | for the copy/register steps |
| Zune 4.8 installed | archive.org still hosts the installer |

> I won't link or host the DLLs: they're Microsoft system files. Take them from your own
> old Windows installation.

---

## Step 1 — Confirm the diagnosis

- [ ] MP3 files sync fine
- [ ] **WMA (including lossless) all fail**
- [ ] Video sync fails
- [ ] Error is `C00D11CD (80004002)`
- [ ] Zune shows "converting…" then errors
- [ ] Reinstalling Zune / rebuilding `ZuneStore.sdf` changes nothing

`0x80004002` is `E_NOINTERFACE` — a COM "interface doesn't exist" error. That's the PC
refusing, not the device.

## Step 2 — Get the five DLLs

From a Windows 7 / 8.1 **x64** machine, `C:\Windows\System32`:

```
wmdrmdev.dll    wmdrmnet.dll    wmdrmsdk.dll    drmv2clt.dll    drmmgrtn.dll
```

`wmdrmsdk.dll` must be the real one (~700–800 KB), not a 28 KB stub.

## Step 3 — Back up and copy

1. Close Zune (tray icon too).
2. Back up the current `C:\Windows\System32\wmdrmsdk.dll` somewhere safe.
3. Copy the four other DLLs into `C:\Windows\System32`.
4. `wmdrmsdk.dll` is TrustedInstaller-owned — in an **admin** prompt:

   ```
   takeown /f C:\Windows\System32\wmdrmsdk.dll /a
   icacls C:\Windows\System32\wmdrmsdk.dll /grant Administrators:F
   ```

   Then copy the real `wmdrmsdk.dll` over it.

## Step 4 — Register them

```
regsvr32 /s C:\Windows\System32\wmdrmdev.dll
regsvr32 /s C:\Windows\System32\wmdrmnet.dll
regsvr32 /s C:\Windows\System32\wmdrmsdk.dll
regsvr32 /s C:\Windows\System32\drmv2clt.dll
regsvr32 /s C:\Windows\System32\drmmgrtn.dll
```

`regsvr32 /s` returns success even when it does nothing — verify with step 5.

## Step 5 — Verify

Reboot, start Zune, then:

```powershell
Get-Process Zune | ForEach-Object { $_.Modules } |
  Where-Object { $_.ModuleName -match 'WMDRM' } |
  Select-Object ModuleName, FileVersion
```

**Success:** you see `WMDRMSDK.DLL` around **11.0.7601.x** (Windows 7 build).

**Failure:** nothing listed → the stub wasn't replaced. Redo step 3.

## Step 6 — Test

Sync one WMA and one video.

**Success:** no `C00D11CD`, device free space grows, the file plays on the device.

## Rollback

Restore the backed-up `wmdrmsdk.dll`, delete the four other DLLs, reboot.

---

## If only video fails

Different root cause, same error code. **Zune Modding Helper** ships a working
`WMVCORE.DLL` and patches `ZuneEncEng.dll` to load it from the Zune folder — no system
files touched:

github.com/ZuneDev/ZuneModdingHelper (link in comments)

Try that first if WMA syncs fine.

## If you get C00D11CD (80004005) instead

`0x80004005` is generic failure — usually device library / DRM state, not the PC. Restore
the device's `zunedb.dat`, `zunedb.BAK` and `drmStore.dat` from a backup.

## A note on games

Built-in games ship as content packages with licenses in `drmStore.dat`. Copying the
`.zcp` files into the content folder does **not** install them — they appear in the menu
and exit immediately when launched. They need the licensed install path (an official
device restore on stock firmware), which is why a wiped or re-flashed Zune can lose its
games permanently.

If games still launch but won't sync, try the WMDRM fix first.

---

## Credits

**ZuneDev / Zune Modding Helper** — the community tool whose WMVCORE shim fixes the
video-only variant of this error, and whose authors documented the Windows-side breakage
long before I hit it.

**1977899016-cell/zune30-research** — the CE tooling and AUTH196 work that makes custom
firmware possible; the device-side notes in this write-up came from comparing against their
research.

**kbhomes/libmtp-zune** — the MTPZ protocol documentation that explains why the device
behaves the way it does once it is unlocked.

If you contributed and I missed you, say so and I'll fix the credits.

---

## Links

- Repo (full write-up + device-side notes): github.com/Zunelzq/zune30-cjk (link in comments)
- Zune Modding Helper (video-only fix): github.com/ZuneDev/ZuneModdingHelper (link in comments)
- Zune 4.8 installer mirrors: search archive.org for "Zune 4.8"

---

If this fixes your sync, post your Windows build and the `WMDRMSDK.DLL` version that ended
up loaded — it helps map which Windows versions still ship anything usable.