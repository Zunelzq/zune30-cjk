# Acknowledgements / 致谢

This project only exists because a lot of people, over almost twenty years, kept
information alive that nobody was being paid to keep alive. Below is what each of them
contributed, as precisely as we can attribute it.

If you contributed and are missing here, please open an issue — it will be fixed.

---

## Firmware tooling: `1977899016-cell/zune30-research`

The single largest contribution. Without this project there is no bootable 3.3 on a
1.0-era device, and no CJK work at all.

| What we used | Where it came from |
|---|---|
| `AUTH196` builder (`tools/upgrade/build_upgrade.py`) — appends a RAM-only vault re-wrap routine to an official 3.3 image, repacks the CE BIN | their repository |
| `ce_bin.py` — strict B000FF container parser / rebuilder, record checksum handling | their repository |
| `ce_lzx.py` + `wincedecompr.py` — CE "compressed ROM file" format (LZX, 4096-byte blocks) encoder and decoder | their repository |
| The ROM file-table layout (`romhdr` → module table → file entries, 28-byte records, `flags |= 0x800` = compressed) | their builder, which we reused verbatim |
| `prepare_registry.py` — CE `default.fdf` (registry hive) parser/writer, `Init` dependency graph | their tooling, used during the (failed) FontLink experiments |
| `build_font_loader.py` — native CE ARM font loader built from a local `coredll.dll` | their tooling |
| `ZZAudio-Zune30-Assistant` — the MTP/`qtk.exe` NOR + vault backup workflow | their application |
| Documentation of the 1.0 TEST → 3.3 upgrade path, ROM evidence, and the explicit statement that the 3.3 image does **not** include CJK | their README and issues |

Their README saying "3.3 compatibility image, Chinese not included" is what convinced us
this was worth attempting rather than assuming it was solved.

## Firmware behaviour: "Firmware Swapping on Zune 30 (Keel) Models" — *ahlanchuck*

An eight-page write-up that answered questions the vendor never documented:

* EBoot and recovery are **flashed from the disk into NOR** at boot; `nk.bin` is unpacked
  into RAM and runs from there;
* therefore the 150 MB partition's three files are the firmware update channel;
* "the Zune automatically checks each image for Microsoft's signature — there is no
  practical way around this";
* the 1.0/1.2/1.3/2.3/3.0/3.2 firmware builds are effectively lost.

That document is why we attacked the bootloader first instead of the image signature.

## The 2009 Chinese community (Baidu Tieba, `zune吧`)

Thread: *「教程】【转载】ZUNE30G可以软刷、硬刷成1.0中文test版」*

* proved that CJK was possible at all, on 1.0 TEST / 1.4;
* documented the firmware's U-disk behaviour and the "cannot upgrade afterwards" caveat;
* distributed the font trio — **SimSun / MS Gothic / Gulim** — that the firmware's
  built-in FontLink expects;
* their package (`Zune01050485(1.0test).cab`) is what ultimately gave us the
  **1.0 TEST bootloader** that does not verify `nk.bin`.

Everything about "copy the fonts into `\Fonts` and CJK appears" — on 1.x — is theirs.

## Firmware history and packaging: bilibili creator 「正直RM」

Articles: *《Zune 入坑必须了解的一些事情》* and *《Zune 的软件集合区》*

* the definitive public summary of Zune 30 firmware versions (1.0 / 1.0 TEST / 1.4 / 3.3)
  and their quirks, including that TEST boards will accept a 1.0 disk and that a
  non-TEST board can be converted by one;
* the 2023 archive of Zune software 4.8 / 1.3, the restore VM, and the 1.3
  Chinese localisation patch — which is how we could sync at all after Microsoft's
  update servers died.

## Preservation uploads: archive.org

* uploader **`OfficialZunity`** — the *Zune 30 (Keel) v2.1(4)TEST Firmware* item
  (raw bins + a 30 GB disk image of an engineering sample). This is where the
  v2.1(4) TEST bootloader, and the firmware-swapping PDF above, came from;
* the anonymous maintainers of the `zune-datamining`, `open-zdk`, and
  `updating-the-zune-firmware` items.

## General Zune reverse engineering

* **ZuneDev** organisation and **Project Lyra** (`wiki.zune.moe`) — the Zune HD
  persistent-jailbreak work (`zuneslayer`, `zuxhook.dll`) and the honest statement that
  the Zune 30 only ever received static analysis. Their methodology (find the loader,
  find the resource system) shaped ours.
* **`balcsida/zunextract`**, **`zunes/ZuneModdingFirmwareWebServer`**, **`ZuneDev/Nezu`** —
  extraction tools, local update server, and the (still early) emulator.

## Protocol references

* **`libmtp`** (`src/mtpz.c`) and **`kbhomes/libmtp-zune`** — MTPZ session behaviour,
  which is why we knew media uploads need the vendor protocol rather than plain MTP.
* **`zuneupdate.com`** and the people who kept firmware manifests alive after the
  official servers were switched off.

## Libraries

* **fontTools** — subsetting, hint stripping, name-table editing;
* **keystone-engine** — ARM assembler used by the community tooling;
* **comtypes** / Windows Portable Devices — talking to the device without the Zune client;
* **mutagen** — reading our own music library to build the character set.

## Hardware and testing

* The **device owner** who opened the player more times than anyone should, reseated the
  ZIF adapter through dozens of dropped connections, and ran every risky boot test
  personally. Nothing in this repository was verified by anyone else first.
* Everyone in the Zune community who kept answering "no, that doesn't work either" —
  negative results are why `docs/09-lessons-learned.md` exists.

---

## 中文致谢

这个工程不是一个人做出来的。近二十年来，很多人无偿地把资料留在了网上，我们只是接着往下走了一步。

* **`1977899016-cell/zune30-research`**：AUTH196 构建器、CE BIN/LZX 工具链、ROM 文件表结构、
  NOR/vault 备份流程、FDF 注册表编辑器。没有这个项目，就不存在"1.0 TEST 上跑 3.3"，
  更不会有这次的中文。
* **ahlanchuck**《Firmware Swapping on Zune 30 (Keel) Models》：讲清楚了 EBoot/recovery
  是从硬盘刷进 NOR、nk 是从硬盘读进内存，以及"微软签名没有实际可行的绕过办法"。
  这份文档让我们一开始就去攻启动器，而不是浪费时间去改镜像签名。
* **2009 年百度贴吧 `zune吧` 的中文先驱**：证明了 CJK 可行（1.0 TEST / 1.4），
  留下了 SimSun / MS Gothic / Gulim 三套字体和整套操作流程；
  他们流传下来的测试固件包，最终给了我们那个**不校验 nk 的启动器**。
* **B 站「正直RM」**：《Zune 入坑必须了解的一些事情》《Zune 的软件集合区》——
  固件版本谱系、TEST 主板行为、Zune 4.8/1.3 安装包与 1.3 汉化补丁，都是他整理的。
* **archive.org 的 `OfficialZunity`** 等保存者：v2.1(4)TEST 固件与整盘镜像、固件替换文档。
* **ZuneDev / Project Lyra**：Zune HD 持久越狱与 RE 方法论，以及"Zune 30 只做过静态分析"的诚实记录。
* **libmtp / kbhomes、zuneupdate.com**：MTPZ 协议与固件清单的参考。
* **fontTools / keystone / comtypes / mutagen**：实际干活的开源库。
* **这台设备的机主**：几十次拆装、无数次适配器掉线重试、所有高风险开机测试都是他亲自做的。

如果你也参与过而这里没提到，请开 issue，我们补上。
