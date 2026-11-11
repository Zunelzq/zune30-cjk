# Zune 30（Keel）——官方 3.3 固件原生显示中日文

**状态：已在真机验证通过。**

> ## 先说清楚：这是站在别人肩膀上做的
>
> 本方案的核心方法、工具链和关键知识全部来自
> **[`1977899016-cell/zune30-research`](https://github.com/1977899016-cell/zune30-research)**：
> AUTH196 镜像构建器、CE BIN/LZX 工具链、`default.fdf` 注册表编辑器、原生字体加载器
> （`ZCJKBoot.exe`）以及 FontLink 方案本身。
>
> 我们做的事比他们少：
> 1. 按他们的配方操作，**发现并修正了三处让我们这边失败的配置错误**，并写清了错误是什么；
> 2. **解锁了加载器写死的 8,206,424 字节尺寸校验**，因此任意大小字体都能用；
> 3. 补上了他们刻意留给用户的环节——镜像打包、固件版本串、`C00D11CD` 同步修复——并做成可复现脚本；
> 4. 整理了**降级路径**（3.3 退回 1.0 TEST）、代价，以及怎么升回去——上游只把同样的动作当作内部恢复步骤。
>
> 如果你要用这里的任何东西，请先去给他们的仓库点 star。

一台第一代 Zune 30（30GB），运行**官方 3.3 (39) 固件**，现在可以原生显示中文和日文。

| 项目 | 修改前 | 修改后 |
|---|---|---|
| 设备名 | `Zune□□□` | 中文正常显示 |
| 中文歌名 | `□□□□` | `巨大少女` |
| 日文歌名 | `□□□□` | `そらのおとしもの ～エターナル・イ...` |
| 歌手 | `□□, □□□` | `40mP, 初音ミク` |
| 英文界面 | Zegoe | **仍是原版 Zegoe**（FontLink 只补缺失字形） |

| 开机画面 | 主菜单 |
|---|---|
| ![boot](assets/01-boot-device-name-redacted.jpg) | ![menu](assets/02-main-menu.jpg) |

| 日文歌名 | 中文歌名 |
|---|---|
| ![jp](assets/03-now-playing-jp-redacted.jpg) | ![cn](assets/04-now-playing-cn-redacted.jpg) |

**从教程开始 → [`docs/tutorial.zh-CN.md`](docs/tutorial.zh-CN.md)**（中文，步骤最细） ·
[`docs/tutorial.md`](docs/tutorial.md)（English）

---

## 一句话原理

3.3 的界面通过系统 GDI 画字。GDI 支持 **FontLink**：当主字体（ROM 里的 `Zegoe UI` 系列）
缺某个字形时，可以从第二个字体里取。所以我们把中文字体注册成"回退字体"，并在界面程序启动前
用一个极小的 ARM 程序把它加载进 GDI。英文继续用 Zegoe，中文从中文字体来。

前提才是难点：

* 需要一个 **1.0 TEST 启动器**（零售 3.3 的启动器会校验 `nk.bin`）；
* 需要 **AUTH196** 镜像（3.3 在 1.0 时代的 vault 上会黑屏）；
* 字体必须放在 `\Hard Disk` —— 这是**150 MB 系统分区**，不是数据分区（我们在这上面错了几个小时）；
* 注册表里的字族名必须和字体内部名称**完全一致**；
* 加载器会把文件大小和一个写死的常量比对，必须改成你的字体大小。

另有一条 **ROM 替换**路线（直接替换 `ZegoeUI*.ttf` 三个文件），也能成功，写在
`docs/06-rom-space.md`。它的好处是不需要启动程序，代价是英文也会变成中文字体的拉丁字形。

---

## 仓库结构

```
README.md / README.zh-CN.md     总览（本文件）
NOTICE.md                       法律范围、去敏说明、致谢
docs/
  tutorial.md / tutorial.zh-CN.md   ★ 分步教程，从这里开始
  01-background.md              硬件、启动链、三层保护
  02-lax-bootloader.md          1.0 TEST 启动器为何是关键
  03-nor-vault-backup.md        不拆芯片备份 NOR/vault
  04-auth196.md                 让 3.3 跑在旧 vault 上
  05-font-mechanism.md          3.3 的文字/字体机制（含更正声明）
  06-rom-space.md               ROM 替换方案（备选）
  07-sync-fix.md                修复 C00D11CD 同步错误
  08-reproduction.md            精简复现清单
  09-lessons-learned.md         所有失败尝试，以及我们下过的错误结论
  10-publishing-checklist.md    去敏与发布检查清单
  11-downgrade.md               3.3 降回 1.0 TEST 的流程与代价
  ACKNOWLEDGEMENTS.md           详细致谢（中英）
scripts/
  build_cjk_font.py             子集化 + 去 hinting + 改名 + CE-LZX 体积校验
  patch_loader.py               改写加载器的字体大小常量
  build_image.py                FontLink 注册表 + 版本串 + 原地替换 FDF + 重建容器
  write_device.ps1              系统分区安全写入
assets/                         已打码截图
```

## 快速开始

```powershell
# 0. 先备份 F:\、G:\zunedb.dat、G:\zunedb.BAK、G:\drmStore.dat，并 dump NOR/vault
# 1. 安装 1.0 TEST 启动器（不可逆，见 docs/02）

# 2. 构建 AUTH196
python <research>\tools\upgrade\build_upgrade.py --stock-nk ... --legacy-vault ...

# 3. 生成字体
python scripts\build_cjk_font.py --font your.ttf --charset charset.txt ^
    --limit 4000000 --family "Zune UI CJK" --out font.ttf --out-packed font.packed.bin

# 4. 改加载器尺寸
python scripts\patch_loader.py --in <research>\artifacts\ZCJKBoot.exe ^
    --size <字体字节数> --out ZCJKBoot.exe

# 5. 构建镜像
python scripts\build_image.py --research-dir <research> ^
    --base nk.AUTH196.bin --fdf-in default.fdf --out nk.CJK.bin

# 6. 写入设备
powershell -ExecutionPolicy Bypass -File scripts\write_device.ps1 -Image nk.CJK.bin
```

详细步骤、验证点、故障排查见 `docs/tutorial.zh-CN.md`。

## 已验证 / 未验证

| 结论 | 状态 |
|---|---|
| 官方 3.3 上显示中日文，英文保持 Zegoe | ✅ 真机验证 |
| GB2312 子集（8,011 字形，1.9 MB）可加载显示 | ✅ 真机验证 |
| 修改后 Zune 4.8 同步正常 | ✅ 真机验证（恢复 zunedb/drmStore 后） |
| Windows 11 上 WMA 同步（全部报 `C00D11CD / 80004002`） | ✅ 已修复：补回 Windows 不再提供的 WMDRM 组件，见 `docs/07-sync-fix.md` |
| AUTH196 + 3.3 在 1.0 TEST 时代 vault 上启动 | ✅ 真机验证 |
| GBK / 完整字体（14 MB+） | ⚠️ 未测，内存上限未知 |
| 菜单汉化 | ❌ 未尝试 |
| FLAC 播放 | ❌ 未尝试（上游声称有解码器 DLL，未分发） |
| 不依赖 Zune 软件传歌 | ❌ 已测试，被设备的 MTP 实现拒绝 |

## 注意事项

* **含设备身份的产物不要外传**（AUTH196 内含你的加密 vault）；
* **字体版权**：用你自己持有的字体生成子集，本仓库不含字体数据；
* **换启动器不可逆**：保管好 `F:\EBoot.bin`，永远不要让 Zune 软件"还原"设备；
* **同步会坏，而且可以预防**：刷机前先复制 `G:\zunedb.dat`、`G:\zunedb.BAK`、`G:\drmStore.dat`（见 `docs/07`）；
* 目前只覆盖 GB2312，生僻字仍会方框；
* 本仓库不含任何微软固件、字体、密钥或设备专属文件。

## 致谢

完整清单见 **[docs/ACKNOWLEDGEMENTS.md](docs/ACKNOWLEDGEMENTS.md)**。

`1977899016-cell/zune30-research`（AUTH196、CE 工具链、加载器）· **ahlanchuck**（固件替换文档）·
2009 年百度贴吧 `zune吧` 中文先驱 · **正直RM**（固件谱系与软件归档）· archive.org 保存者 ·
ZuneDev / Project Lyra · libmtp / kbhomes · fontTools、keystone、comtypes、mutagen。

## 隐私

截图已打码（设备昵称与专辑封面模糊处理），仓库内不含序列号、本机路径或个人信息。
检查清单见 `docs/10-publishing-checklist.md`。

## 许可

文档与脚本：MIT。不含微软二进制、字体或设备专属产物。
