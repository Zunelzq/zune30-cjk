# 教程：让 Zune 30 的官方 3.3 固件显示中文

> ## 声明：本教程建立在前人的工作上
>
> **本流程的核心方法来自 [`1977899016-cell/zune30-research`](https://github.com/1977899016-cell/zune30-research)**：
> AUTH196 镜像构建器、CE BIN/LZX 工具链、`default.fdf` 注册表编辑器、原生字体加载器
> （`ZCJKBoot.exe`）与 FontLink 方案，全部出自那个项目。
>
> 我们做的事只有三件：
> 1. 在他们的方案上**修正三处配置错误**（字体分区、字族名、加载器），使其在真机生效；
> 2. 把字体从 8.2 MB 固定大小**解锁为任意大小**（修改加载器里的尺寸常量）；
> 3. 补上**镜像打包、版本串修正、同步修复**这几个他们未覆盖的环节，并写成可复现的脚本。
>
> 如果没有他们的工作，这篇教程不存在。请先给上游项目点 star。

---

## 0. 你将得到什么

一台第一代 Zune 30（30GB），运行**官方 3.3 (39) 固件**：

- 英文界面保持**原版 Zegoe 字体**（不是宋体）；
- 中文歌名、日文歌名、设备名**正常显示**；
- Zune 软件同步正常；
- 字库可自定义（本教程用 GB2312 全集，约 8,000 字形）。

---

## 1. 你需要什么

| 项目 | 说明 |
|---|---|
| Zune 30（Keel，30GB） | 第一代，i.MX31 |
| ZIF 转 USB 适配器 | 用于把硬盘接到电脑；接触不良很常见，建议后置 USB 口 |
| Windows 电脑 | PowerShell + Python 3.10+ |
| 官方 3.3 固件 | 你自己的 `KeelBaseline.cab`（Zune 4.8 安装包内，或你自己的设备备份） |
| **1.0 TEST 的启动器** | `EBoot.bin`，sha256 前缀 `11D94DE4`；可从公开保存档案或 1.0 TEST 设备获得 |
| 一份中文字体 | 你有权使用的 TTF（本教程示例用宋体） |
| `1977899016-cell/zune30-research` | 克隆到本地，本教程会调用它的工具 |
| `ZZAudio-Zune30-Assistant`（可选） | 来自上游，用于在不拆芯片的情况下备份 NOR/vault |

安装 Python 依赖：

```powershell
py -m pip install fonttools
```

---

## 2. 第一步永远是备份（不可跳过）

### 2.1 备份两个分区

把硬盘接到适配器，把两个分区**完整复制**到电脑：

```
F:\  →  150 MB 系统分区
        EBoot.bin、nk.bin、recovery.bin、zconfig.dat、pmcver.dat、pmcstore.edb

G:\  →  数据分区（必拷这三个，否则同步可能永久损坏）
        zunedb.dat      约 4 MB
        zunedb.BAK      约 4 MB
        drmStore.dat    约 54 MB
```

### 2.2 备份 NOR 与 vault

如果设备当前是 **1.0 TEST 固件**，用上游的 `ZZAudio-Zune30-Assistant`：

1. 关闭 Zune 软件；
2. 运行助手 → 「检查连接」→「开始备份」；
3. 得到 `nor.original.bin`（2 MB）、`vault.legacy.bin`（64 KB）、`nk.original.bin` 等。

> 这些文件包含**你设备的加密身份**，永远不要上传或发给别人。

---

## 3. 安装 1.0 TEST 启动器

零售 3.3 的启动器会校验 `nk.bin` 签名，所以必须先换成 1.0 TEST 的启动器（它不校验）。

1. 把 1.0 TEST 的 `EBoot.bin` 复制到 `F:\EBoot.bin`；
2. 同时把同一包的 `recovery.bin`、`zconfig.dat`、`pmcver.dat` 复制到 `F:\`；
3. 装回设备，开机一次 —— 设备会把磁盘上的 `EBoot.bin` 刷进 NOR；
4. 开机画面应显示 **`Bootloader 2`**。

> ⚠️ 一旦这个启动器进了 NOR，**永远不要**用 Zune 软件的"还原/修复"，也不要刷官方固件包，
> 否则会被零售启动器覆盖，之后自制镜像全部失效，且**无法恢复**（HAB 验签，改不了启动器）。

---

## 4. 构建 AUTH196（让 3.3 跑在旧 vault 上）

1.0 TEST 设备的 vault 是旧格式，直接跑官方 3.3 会黑屏。AUTH196 会在开机时把旧 vault
重封装成新格式（仅内存）。

```powershell
python <zune30-research>\tools\upgrade\build_upgrade.py `
  --stock-nk      <官方3.3的nk.bin> `
  --legacy-vault  <你的vault.legacy.bin> `
  --vault-sha256  <vault的sha256> `
  --decompressor-dir <zune30-research>\app\vendor `
  --output-dir    out\auth196
```

产出 `out\auth196\nk.AUTH196.PRIVATE.bin`（约 13.3 MB）。

**先单独验证它能开机**：写入 `F:\nk.bin` → 开机 → 应进入 3.3 主界面。
这一步不通过就不要继续。

---

## 5. 准备中文字体

### 5.1 取出注册表

从 `nk.AUTH196.PRIVATE.bin` 里提取 `default.fdf` 并解压（上游 `ce_bin.py` + `ce_lzx.py` 可做），
得到一个未压缩的 `default.fdf`（约 186 KB）。

### 5.2 生成字体子集

```powershell
python scripts\build_cjk_font.py `
  --font      <你的中文字体.ttf> `
  --charset   charset.txt `
  --limit     4000000 `
  --family    "Zune UI CJK" `
  --out       out\font.ttf `
  --out-packed out\font.packed.bin
```

`charset.txt` 是你要覆盖的汉字（UTF-8 文本）。本教程的实测配置：

| 字符集 | 字形数 | 字体大小 |
|---|---|---|
| 曲库用字 + 假名 + ASCII | 1,819 | 379 KB |
| **GB2312 全集 + 曲库 + 假名** | **8,011** | **1.9 MB** |

> **建议保留 hinting**（加 `--keep-hinting`）：体积约 3.2 MB，但小字号清晰得多。
> 只有走 ROM 替换路线（空间紧张）时才需要去掉 hinting。
> 在意观感可以加回（文件约 3–4 MB，仍然可用）。

把生成的字体重命名为：

```
F:\Fonts\ZuneCJK_UI_20261027.ttf
```

（这个名字是固定路径，改动需同时改注册表。）

---

## 6. 修改加载器的尺寸校验

上游的 `ZCJKBoot.exe` 硬编码了 `GetFileSize == 8,206,424`。如果你的字体不是这个大小，
它不会加载字体。

```powershell
python scripts\patch_loader.py `
  --in  <zune30-research>\artifacts\ZCJKBoot.exe `
  --size <你字体文件的字节数> `
  --out out\ZCJKBoot.exe
```

脚本会打印它找到的常量位置（默认 `0x2ec`）并改写。
把产物复制到：

```
F:\Fonts\ZCJKBoot.exe
```

---

## 7. 构建镜像

```powershell
python scripts\build_image.py `
  --research-dir <zune30-research> `
  --base     out\auth196\nk.AUTH196.PRIVATE.bin `
  --fdf-in   out\default.fdf `
  --out      out\nk.CJK.bin
```

脚本做四件事：

1. 在注册表里加入 FontLink（三个 Zegoe 面 → 你的字体）和 `Launch45` 启动项；
2. 用 CE LZX（块大小必须 4096）压缩，并**原地**覆盖 `default.fdf` 的 ROM 槽位
   （必须塞得进 38,949 字节，塞不进会直接报错，不会冒险搬移）；
3. 把固件版本格式串改成 `03.30.00039.00-00435`（否则 Zune 软件认为固件过旧）；
4. 按**原始记录结构**重打包 B000FF 容器（重排记录会导致启动失败，见 `09`）。

预期输出：

```
registry: 186,629 bytes, launch order [20, 30, 45, 60]
registry compressed: 38,927 bytes
default.fdf: 186,629 -> 38,927 (slot 38,949)
version string patched at 0x7cda6c -> 03.30.00039.00-00435
written: out\nk.CJK.bin  (13,956,899 bytes)
```

---

## 8. 写入设备

```powershell
powershell -ExecutionPolicy Bypass -File scripts\write_device.ps1 -Image out\nk.CJK.bin
```

脚本会：

- 等待 `F:` 出现（适配器掉线是常态，会重试）；
- 备份当前 `nk.bin`；
- 写入并**校验哈希**；
- 检查 `F:\EBoot.bin` 是不是 1.0 TEST 的启动器，不是就警告。

写完安全弹出，装回设备，开机。

---

## 9. 验证

| 检查点 | 期望 |
|---|---|
| 开机画面 | `Version 3.30 (39)`、`Bootloader 2` |
| 设备名 | 中文正常显示（如果你设了中文名） |
| 主界面英文 | **仍是原版 Zegoe**（圆润无衬线） |
| 中文歌名 | 正常显示，不是 `□□□` |
| 生僻字 | GB2312 范围内的应正常 |

如果中文仍显示方框，按 `11. 故障排查` 逐项检查。

---

## 10. 修复 Zune 软件同步（如果坏了）

症状：Zune 能识别设备，但同步报 `C00D11CD (80004005)`，关系显示"访客"。

原因：刷机过程中的失败启动会格式化系统分区，1.0 TEST 固件会重写数据分区的媒体库，
而 AUTH196 的 vault 重封装无法持久化安全状态 —— 三者叠加让 Zune 缓存的设备关系失效。

修复：把**你自己设备**原来的三个文件放回 `G:\`：

```
G:\zunedb.dat
G:\zunedb.BAK
G:\drmStore.dat
```

然后开机、连电脑、打开 Zune，同步即可恢复。（详见 `07-sync-fix.md`）

---

## 11. 故障排查

| 现象 | 可能原因 | 处理 |
|---|---|---|
| 开机黑屏/重启 | AUTH196 与这台设备的 vault 不匹配 | 回到第 4 步验证基线 |
| 进系统但中文方框 | 字体路径/字族名/加载器不匹配 | 见下表 |
| 进系统后文字消失 | 字体文件损坏或过大 | 换小字体（1–2 MB）重试 |
| 英文变成宋体 | 你走的是 ROM 替换路径（`06`），不是 FontLink | 正常现象，或改用本教程 |
| 提示 `please wait` 后要求连电脑 | 镜像被启动器拒绝（记录结构问题） | 用本仓库脚本重建，不要手工重排容器 |
| Zune 同步失败 | 见第 10 步 | 恢复三个库文件 |

方框排查三连：

1. 字体真的在 `F:\Fonts\`（不是 `G:\Fonts`）吗？
2. 字体内部 family 名与注册表里逗号后的字符串**完全一致**吗？
3. `ZCJKBoot.exe` 里的大小常量等于字体文件的真实字节数吗？

---

## 12. 限制与风险

- 目前只覆盖 GB2312 范围，生僻字（GBK 扩展）仍会方框；扩到 GBK 需要更大字体并测试内存。
- 菜单仍是英文 —— 界面字符串在 `strings.gem` 里，本教程不涉及。
- 换启动器是不可逆的一步；之后**永远不能**让 Zune 软件"修复设备"。
- 固件手术有风险，虽然启动器宽松（写错 `nk.bin` 可以重写），但请务必先备份。
- 本仓库不分发任何微软固件、字体或设备专属文件。

---

## 13. 致谢

完整清单见 `ACKNOWLEDGEMENTS.md`。核心是：

- **`1977899016-cell/zune30-research`**：AUTH196、CE 工具链、FDF 编辑器、字体加载器、备份助手；
- **ahlanchuck**《Firmware Swapping on Zune 30 (Keel) Models》：讲清了 EBoot/恢复镜像的刷写与验签；
- **2009 年百度贴吧 `zune吧`** 的中文先驱：证明 CJK 可行；
- **archive.org** 的保存者、**ZuneDev / Project Lyra**、**libmtp** 等。

---

## 回退

如果想退回 1.0 TEST，见 [11-downgrade.md](11-downgrade.md)：流程、预期现象、以及它会破坏哪些数据。
