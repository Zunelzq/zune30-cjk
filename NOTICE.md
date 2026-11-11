# NOTICE — legal scope, de-identification, credits

## 0. Relationship to upstream

This repository is a **follow-up** to
[1977899016-cell/zune30-research](https://github.com/1977899016-cell/zune30-research), not an
independent invention. The AUTH196 builder, the CE BIN/LZX tooling, the registry (FDF) editor,
the native font loader and the FontLink approach are that project's work, used here under MIT.

What is original to this repository: three corrected configuration mistakes, the loader
size-constant patch, the in-place image assembler, the firmware version-string patch, the
C00D11CD sync repair, and the documentation/tutorials.
## 1. What this repository contains

Documentation and original scripts only. It deliberately contains **none** of:

| Excluded | Why |
|---|---|
| Microsoft firmware (`EBoot.bin`, `nk.bin`, `recovery.bin`, `*.cab`) | copyrighted, and redistribution is not needed to reproduce the work |
| Device-specific artifacts (`nor.original.bin`, `vault.legacy.bin`, AUTH196 images, `zunedb.dat`, `drmStore.dat`) | they embed one physical device's encrypted identity |
| Font binaries (SimSun, MS Gothic, Gulim …) | commercial fonts; build your own subset from a font you own |
| Keys, certificates, license blobs | never handled, never extracted, never published |
| Zune software installers | obtain them yourself from your own media/archives |

`.gitignore` blocks `*.bin`, `*.cab`, `*.ttf`, `*.ttc`, `*.PRIVATE.bin`, `backup/`, `out/`
so that a careless `git add .` cannot leak them.

## 2. Scope of the work

This is **interoperability and preservation research on hardware the author legally owns**:

* a 2006 media player whose vendor has shut down every service it depended on;
* the goal is to keep the owner's device usable in the owner's language, and to document
  how its software actually works;
* no DRM-protected content is decrypted, no content keys are touched, no purchased media
  is redistributed. The music used to test the result is the owner's own library;
* the analysis of the boot chain, ROM file system and font loader is published as
  **knowledge**, not as a tool that breaks content protection.

### A candid caveat about anti-circumvention law

Some jurisdictions (notably the United States, DMCA §1201) restrict "circumventing a
technological protection measure", and firmware signature checks can arguably fall inside
that definition even when no copyrighted work is being copied. Others (EU, and the
interoperability exceptions in many national laws) treat this kind of reverse engineering
more permissively. **This is not legal advice.** If you are unsure about your jurisdiction,
publish the *analysis* (which is what this repo is) and keep the device-specific binaries
to yourself.

What this repository intentionally does **not** do:

* it does not distribute or link to firmware downloads;
* it does not include the TEST bootloader binary or any way to obtain it beyond describing
  which public preservation archive holds it;
* it does not provide a generic "jailbreak" for devices you do not own.

## 3. De-identification

Everything published here was sanitised before release:

| Item | Treatment |
|---|---|
| Device nickname / user name shown on screen | replaced with a placeholder in the text; the corresponding line in the photo is blurred |
| Album artwork visible on the device | blurred (third-party illustration, unrelated to the research) |
| Device serial number (`MTP DeviceInfo`) | never published; not present in any file |
| Filesystem paths from the author's machine | removed; docs use relative or generic paths |
| Encrypted vault / NOR dump / `zunedb.dat` / `drmStore.dat` | never published |
| Zune client library database (`ZuneStore.sdf`) | never published |
| Font files used for testing | not published |

The four screenshots in `assets/` are the only images; they show the *rendering result*,
not any personal or licensed content.

## 4. Risk

Firmware modification on a 20-year-old device. The lax bootloader makes recovery easy
(rewrite `nk.bin`), but the device can still be rendered unusable. You accept that risk.

Nothing here is a supported product. No warranty of any kind.

## 5. Third-party work

Credits in full: [`docs/ACKNOWLEDGEMENTS.md`](docs/ACKNOWLEDGEMENTS.md).

Short version:

* [`1977899016-cell/zune30-research`](https://github.com/1977899016-cell/zune30-research)
  (MIT) — AUTH196 builder, CE BIN/LZX tooling, ROM file-table layout, `wincedecompr.py`,
  and the ZZAudio backup assistant. The CE-LZX encoder format reproduced in
  `scripts/build_cjk_font.py` is theirs; verification optionally loads their decoder.
* **ahlanchuck** — *Firmware Swapping on Zune 30 (Keel) Models*.
* The 2009 **Baidu Tieba `zune吧`** community — the 1.0 TEST / 1.4 CJK method and the font trio.
* **正直RM** (bilibili) — firmware history and the Zune 1.3/4.8 software archive.
* **`OfficialZunity`** and the archive.org preservation uploaders.
* **ZuneDev / Project Lyra**, **libmtp / kbhomes**, **zuneupdate.com**.
* **fontTools**, **keystone-engine**, **comtypes**, **mutagen**.

## 6. License

Documentation and scripts: **MIT** (see `LICENSE`).

"Zune" and "Microsoft" are trademarks of their owners, used descriptively only.
