# 资源下载清单（Zune 30 中文化）

> 本页只列出**需要你自己下载**的东西，以及每个文件的校验哈希。
> 本仓库不分发任何固件、字体或设备专属文件。

---

## 一、软件工具

| 用途 | 名称 | 地址 | 备注 |
|---|---|---|---|
| 跑脚本 | **Python 3.10+** | https://www.python.org/downloads/ | 安装时勾选 `Add python.exe to PATH` |
| 处理字体 | **fontTools** | 命令行执行 `py -m pip install fonttools` | |
| 解压 | **7-Zip**（可选） | https://www.7-zip.org/ | |
| 同步歌曲 | **Zune 软件 4.8** | 见下方"固件与软件" | 装在一台 Windows 上 |

---

## 二、必须的上游项目

| 内容 | 地址 |
|---|---|
| **zune30-research**（AUTH196 构建器、CE 工具链、注册表编辑器、字体加载器） | https://github.com/1977899016-cell/zune30-research |
| **ZZAudio-Zune30-Assistant**（不拆芯片备份 NOR / vault 的图形助手） | https://github.com/1977899016-cell/zune30-research/raw/refs/heads/main/downloads/ZZAudio-Zune30-Assistant-v0.1.0-alpha.2-win64.zip |

> 没有第一个项目，本教程不存在。请先给它点 star。

---

## 三、固件与软件

### 3.1 官方 3.3 固件 `KeelBaseline.cab`

| 项 | 值 |
|---|---|
| 大小 | 35,832,824 字节 |
| sha256 | `0aaa0fe19d261cef741cba4fa51876a112378e056679ad227efcd35604d5bb8e` |

获取途径（任选）：

1. **你自己的 Zune 4.8 安装包**里通常带有固件；
2. 装过 Zune 4.8 的电脑上，客户端缓存目录里可能留有 `KeelBaseline.cab`；
3. 网上流传的 Zune 4.8 安装包（例如贴吧/B 站整理包）里一般也带。

> 这个文件**必须是微软签名的原始包**，不要用任何"改过的" cab。

### 3.2 1.0 TEST 固件包（内含宽松启动器）

| 项 | 值 |
|---|---|
| 常见文件名 | `Zune01050485(1.0test).cab` |
| 大小 | 15,619,281 字节 |
| sha256 | `59eac3f4f712b5f0c99f15eef4ed84058c76000f5f0b89493625efec5bdbde12` |
| **内部关键文件** `EBoot.bin` | 262,339 字节，sha256 `11d94de42d80bcd0390fee6641882e38904dd9386e389ecd6d5a22e420f7e582` |

来源：这个包在中文社区流传多年（贴吧、网盘整理包、B 站文章附件等），
也出现在一些保存档案里。**只有一个用途：取出里面的 `EBoot.bin` 作为启动器。**

> ⚠️ 这个 cab 里的 `nk.bin` 是 1.x 系统，不是 3.3，不要直接当 3.3 用。

### 3.3 Zune 软件

| 版本 | 用途 |
|---|---|
| **4.8** | 与 3.3 设备同步歌曲（推荐） |
| 1.3 | 与 1.x 固件设备同步（只在需要时用） |

来源：微软官方已下架，只能从整理包或保存档案获取（例如 B 站「正直RM」整理的网盘包）。

---

## 四、字体

| 文件 | 大小 | sha256 |
|---|---|---|
| `simsun.ttc`（宋体，Windows 自带） | 14,565,616 | `ec8689cbdedc46f21a469d713e4646c1901a7b9f1f7be6b8146ff8a38f673455` |
| `msgothic.ttc`（MS Gothic） | 9,176,636 | `ef9044f54896c6d045a425e62e38b3232d49facc5549a12837d077ff0bf74298` |
| `gulim.ttc`（Gulim） | 13,524,972 | `a167be36290c0696737da35eaf48b7ce7704d930985406a1e661f94e54fd191a` |

- `simsun.ttc` 在 `C:\Windows\Fonts` 里就有（Windows 系统字体）；
- 日文/韩文字体同样可以从系统字体或 Office 安装目录取得；
- **注意授权**：这些是商业字体，仅在你拥有授权的机器上用于自制子集。

---

## 五、上游加载器（字体加载器原版）

| 文件 | 大小 | sha256 |
|---|---|---|
| `ZCJKBoot.exe` | 2,048 | `dd2c0bf0fad44cc24a058820395b51b960a39fd662364654992144ef92df982d` |

位置：上游仓库 `artifacts/ZCJKBoot.exe`。
它硬编码字体大小 8,206,424 字节，用本仓库的 `scripts/patch_loader.py` 改成你的字体大小。

---

## 六、保存档案（查资料 / 补齐缺失文件）

| 内容 | 地址 |
|---|---|
| 固件替换文档（ahlanchuck） | https://archive.org/details/updating-the-zune-firmware |
| Zune 30 v2.1(4)TEST 固件与整盘镜像 | https://archive.org/details/zune-30-keel-v2.14test-firmware |
| Zune 数据挖掘素材 | https://archive.org/details/zune-datamining |
| OpenZDK / CE 开发包 | https://archive.org/details/open-zdk |

---

## 七、本教程仓库

| 内容 | 地址 |
|---|---|
| 教程 + 脚本 | https://github.com/Zunelzq/zune30-cjk |

---

## 八、重要提醒

1. **不要下载别人做好的"中文 nk.bin"** —— 它内含对方设备的加密 vault，
   你的机器用不了，作者也不该外发。
2. **1.0 TEST 启动器刷入后不可逆**：之后永远不能让 Zune 软件"修复/还原"设备，
   也不要刷任何官方固件包。
3. **先备份再动手**：`F:\`、`G:\zunedb.dat`、`G:\zunedb.BAK`、`G:\drmStore.dat`。
4. **核对哈希**：尤其是固件与启动器，改过的文件可能让机器变砖。
5. 论坛可能会吞长链接，必要时把链接分行或加空格发。
