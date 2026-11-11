# Reddit post — r/zune

## Title (pick one)

1. **Zune 30 on official 3.3 firmware now renders Chinese/Japanese natively (write-up + tooling)**
2. **I got CJK text working on an official 3.3 Zune 30 — here is how (research, no firmware distributed)**
3. **Official 3.3 + Chinese song titles on a Zune 30: bootloader research, ROM font replacement, and everything that failed**

## Flair

`Mod` / `Project` / `Discussion` — whichever r/zune offers for projects.

## Body

---

For years the answer to "can a Zune 30 show Chinese?" has been *only on 1.0 TEST / 1.4*, because
those builds use GDI font linking. Official 3.3 was considered a dead end — even the
`zune30-research` project states that its 3.3 compatibility image does not include CJK.

That is no longer true. This is a first-gen Zune 30 (30 GB) running **official 3.3 (39)**,
rendering Chinese and Japanese in the shell and in the media library:

* device name: Chinese characters, no boxes
* song title: `巨大少女`
* Japanese title: `そらのおとしもの ～エターナル・イ...`
* artist: `40mP, 初音ミク`

**Why it was thought impossible**

3.3's shell (`gemstone.exe`) does not use GDI text fallback. Registry `FontLink` entries,
`Software\Microsoft\Zune\Fonts\*` locators, fallback fonts and a boot-time
`AddFontResourceW` loader were all tried on hardware and all do nothing. Swapping the two
ROM faces between entries produces zero visual change — proof the registry is not consulted.

**What actually happens**

The shell loads its UI faces straight from three ROM files:

```
\Windows\ZegoeUI.ttf
\Windows\ZegoeUI_L.ttf
\Windows\ZegoeUI_SB.ttf   (default face)
```

Replace the *contents* of those files and the UI changes instantly. So the fix is to put a
CJK font in ROM. The hard part is space: the image has ~36 KB free and a usable CJK subset
needs ~160–180 KB compressed.

**How the space was found**

* compress `skin_default.gem` in place (464 KB → 334 KB) — the CE ROM filesystem
  decompresses files whose file-table entry has `flags |= 0x800`;
* the freed tail is contiguous with the FM-radio firmware blob (`Acs_*.hex`) and two unused
  ZDK scene packages, giving 163–180 KB in one block;
* store a hint-free TrueType subset there, CE-LZX compressed with **4096-byte blocks only**,
  and point all three Zegoe file-table entries at it.

**The prerequisite nobody has**

Retail 3.3 EBoot verifies `nk.bin`. The unlock is the **1.0 TEST bootloader** — signed by a
key the production eFuses accept, but it never checks `nk.bin`. Once that is in NOR, any
image boots. That is documented too.

**Also covered in the write-up**

* how to dump NOR/vault without desoldering (the TEST firmware's boot-time `qtk.exe` hook);
* building the AUTH196 image (3.3 on a legacy vault);
* fixing `C00D11CD` sync failures after firmware surgery (restore your own
  `zunedb.dat` / `drmStore.dat`);
* the version-string patch that makes the Zune client stop thinking the firmware is outdated;
* **a long list of things that do NOT work** — relocating `.gem` packages, re-chunking the
  B000FF container, appending out-of-order records, raw MTP media uploads, FontLink, and more.

**Repository** (docs + scripts, MIT): https://github.com/Zunelzq/zune30-cjk

No Microsoft firmware, no fonts and no device-specific artifacts are distributed — you
build everything from firmware and fonts you already own.

Limitations, honestly: 1,050 Han characters fit in the available ROM space, so rare
characters still show as boxes; Latin text now uses the CJK face's Latin glyphs (serif-ish);
the FM-radio firmware slot is repurposed, so radio firmware updates are off the table.

Huge thanks to `zune30-research` (AUTH196 + CE tooling), ahlanchuck's firmware-swapping
document, the 2009 Baidu Tieba Chinese Zune community, and the archive.org preservation
uploaders. Credits are itemised in the repo.

Happy to answer questions — especially if someone has a cleaner way to free ROM space, or a
merged "Zegoe Latin + CJK" font (fontTools' merger kept crashing on this machine).

---

## Posting tips

* Post from the same account as the repository, or an alt — not your real-name account.
* Attach **one** image (the Chinese now-playing shot). Reddit shows it in the feed; put the
  rest inside the post.
* Do not link firmware downloads, do not offer to send `nk.bin` to anyone.
* If someone asks "can you send me the image" → "it embeds my device's encrypted vault, so
  no; the repo explains how to build your own".
* Expected question: *"will this brick my Zune?"* — answer: the bootloader swap is the only
  irreversible step; a bad `nk.bin` is recoverable by rewriting the file.
