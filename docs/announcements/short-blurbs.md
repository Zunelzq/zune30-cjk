# Short blurbs (Discord / forums / group chats)

## English — Discord / forum post

> **Zune 30, official 3.3 firmware, native CJK — it finally works.**
>
> Turns out the 3.3 shell ignores GDI FontLink entirely: `gemstone.exe` loads its UI faces
> straight from `\Windows\ZegoeUI*.ttf` in ROM. So the fix is to replace those files with a
> CJK font — the tricky part is finding ~180 KB of contiguous ROM space (compress
> `skin_default.gem` in place, it's read through the CE filesystem which decompresses
> `flags |= 0x800` files).
>
> Prerequisite: the 1.0 TEST bootloader (it doesn't verify `nk.bin`).
>
> Write-up, scripts, and a long list of things that *don't* work:
> https://github.com/Zunelzq/zune30-cjk
>
> No firmware/fonts distributed — you build from what you own. 1,050 Han characters fit;
> rare characters still box out.

## 中文 — 群聊 / 短贴

> **Zune 30 官方 3.3 固件，原生显示中文了。**
>
> 3.3 的界面不走 GDI FontLink，`gemstone.exe` 直接从 ROM 里的 `\Windows\ZegoeUI*.ttf`
> 加载字体——所以只能替换这三个文件。难点是 ROM 空间：原地压缩 `skin_default.gem`
> 腾出 130 KB，再占用两个用不到的槽位，凑出 180 KB 放中文字体。
>
> 前提是 1.0 TEST 启动器（它不校验 nk）。
>
> 文档、脚本、以及一堆"失败的尝试"都在这里：
> https://github.com/Zunelzq/zune30-cjk
>
> 不分发固件和字体。目前塞得下 1,050 个汉字，生僻字还是方框。

## GitHub Release notes (v1.0)

```
First public release — native CJK on official Zune 3.3.

What works
- official 3.3 (39) shell renders Chinese/Japanese: device name, song titles, artists
- Zune client sync restored
- reproducible pipeline: font subsetter + image assembler + safe writer

What is documented but NOT included
- Microsoft firmware, fonts, NOR/vault dumps, device-specific images

Known limits
- 1,050 Han characters fit in ROM (rare characters box out)
- Latin glyphs come from the CJK face (serif look)
- FM radio firmware slot repurposed
```
