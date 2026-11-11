# 11 — 降级：把 3.3 退回 1.0 TEST

> 适用对象：已经跑着 3.3（AUTH196）的 Zune 30，NOR 里是 1.0 TEST 启动器。
> 目标：退回到 1.0 TEST (186) 系统，验证可回退性，或临时获得 1.0 TEST 的 U 盘模式。
>
> **上游项目没有把这套流程写出来。** `zune30-research` 只有"恢复原系统"——把用户自己的
> `nk.original` 写回去，作为升级前的安全闸门，但不讨论跨版本降级后的分区、媒体库、
> 同步关系会发生什么。这一页补的就是这部分。

---

## 1. 为什么可以降级

因为启动器换了：

| 启动器 | 对 `nk.bin` 的处理 |
|---|---|
| 零售 3.3 EBoot | 校验微软签名；换版本被拒/格式化系统分区 |
| **1.0 TEST EBoot**（`Bootloader 2`） | **不校验**，硬盘上是哪个 nk 就启动哪个 |

所以"降级"在硬件层面只是**换一个 `nk.bin` 文件**。
真正的麻烦不在启动，而在**数据分区**：1.0 TEST 与 3.3 的媒体库格式完全不同。

---

## 2. 准备清单（缺一不可）

### 2.1 必须有的文件

| 文件 | 来源 | 说明 |
|---|---|---|
| `nk.original.bin` | 你自己的备份 | 1.0 TEST (186) 的 `nk.bin`，约 10,689,955 B |
| `EBoot.bin`（TEST） | 1.0 TEST 固件包 | sha256 前缀 `11D94DE4`，NOR 里应该已经是它 |
| `recovery.bin`（TEST） | 同上 | 恢复画面用 |
| `zconfig.dat` / `pmcver.dat` / `pmcstore.edb`（TEST） | 同上 | 配置与设备名 |
| **`zunedb.dat` / `zunedb.BAK` / `drmStore.dat`（3.3 时代的）** | 你自己在刷 3.3 后备份的 | **回到 3.3 时要用它们恢复同步** |

### 2.2 先想清楚：你是否真的需要降级

| 目的 | 建议 |
|---|---|
| 只是想验证"能不能刷回来" | 值得做一次，确认退路存在 |
| 想要 1.0 TEST 的 U 盘模式 | 可以，但会失去 3.3 的界面、游戏、无线 |
| 想修 3.3 的问题 | 不用降级，3.3 可以直接重写 `nk.bin` |
| 想长期使用 | 留在 3.3（中文已可用），1.0 TEST 只作为退路 |

---

## 3. 操作步骤

### 步骤 1：拆盘

设备关机，拆出硬盘，接 ZIF→USB 适配器。

### 步骤 2：备份当前（3.3）状态

```powershell
# 系统分区
Copy-Item F:\* <备份目录>\F -Recurse -Force
# 数据分区的媒体库三件套（回到 3.3 时要靠它们恢复同步）
Copy-Item G:\zunedb.dat, G:\zunedb.BAK, G:\drmStore.dat <备份目录>\G -Force
```

### 步骤 3：写入 1.0 TEST 的文件

```powershell
# 系统镜像
Copy-Item <1.0TEST>\nk.bin        F:\nk.bin        -Force
Copy-Item <1.0TEST>\recovery.bin  F:\recovery.bin  -Force
Copy-Item <1.0TEST>\EBoot.bin     F:\EBoot.bin     -Force
# 配置（用 1.0 TEST 自带的，避免它开机后自己重写/清盘）
Copy-Item <1.0TEST>\zconfig.dat   F:\zconfig.dat   -Force
Copy-Item <1.0TEST>\pmcver.dat    F:\pmcver.dat    -Force
Copy-Item <1.0TEST>\pmcstore.edb  F:\pmcstore.edb  -Force
```

校验：

```
nk.bin    sha256 前缀应为 9D947FEB
EBoot.bin sha256 前缀应为 11D94DE4
```

### 步骤 4：装回、开机

预期现象：

| 现象 | 说明 |
|---|---|
| 开机画面出现**红色 TEST 水印** | 正常，1.0 TEST 的标志 |
| 版本显示 `1.0 (186) TEST` | 正常 |
| 界面朴素（无 3.3 的花纹） | 正常 |
| 首次开机较慢 | 它在重建自己的媒体库 |
| 可能提示"清除/格式化" | 正常，数据分区要被 1.0 TEST 重新初始化 |

### 步骤 5：验收

| 检查 | 期望 |
|---|---|
| 能否进主界面 | ✅ |
| 关于页版本 | `1.0 (186) TEST` |
| 数据分区是否被重建 | `G:\` 出现 `MediaLibrary.edb`，原来的 `zunedb.dat` 可能被替换 |
| 歌曲还在不在 | 文件可能在 `Content`，但**库里多半没有**（见第 4 节） |

---

## 4. 降级的真实代价（重点）

这一步不会变砖，但**会破坏 3.3 的媒体库状态**：

| 项目 | 3.3 | 1.0 TEST | 结果 |
|---|---|---|---|
| 媒体库 | `zunedb.dat`（SQL CE） | `MediaLibrary.edb`（PMC） | 互不兼容，1.0 TEST 会重建 |
| 媒体库登记 | Zune 4.8 同步写入 | MTP 同步（Zune 1.3 / WMP） | 原有歌单/播放次数丢失 |
| DRM 库 | `drmStore.dat` | 同名但格式不同 | 可能被重写 |
| 数据分区布局 | `Content\<hash>` | PMC 目录结构 | 文件可能被移动/忽略 |

**实测结果**：降级后设备能正常启动、能用，但歌曲需要重新同步；
之后回到 3.3 时，必须把**降级前备份的 `zunedb.dat` / `zunedb.BAK` / `drmStore.dat`** 放回去，
否则 Zune 4.8 同步会报 `C00D11CD`（详见 `07-sync-fix.md`）。

---

## 5. 降级能带来什么好处

1. **确认退路存在**：证明这台设备可以自由往返 1.0 TEST ↔ 3.3，不是单向升级。
2. **1.0 TEST 的 U 盘模式**：在没装 Zune 驱动的电脑上，1.0 TEST 会以**大容量存储**出现，
   可以直接拖文件；3.3 只暴露 MTPZ，做不到。
3. **排障**：如果 3.3 的自制镜像出问题，退回 1.0 TEST 是一个已知可用的基线。

---

## 6. 再升回 3.3

```powershell
Copy-Item <AUTH196>\nk.AUTH196.PRIVATE.bin F:\nk.bin -Force
# 开机进 3.3 后，再恢复媒体库：
Copy-Item <备份>\G\zunedb.dat     G:\ -Force
Copy-Item <备份>\G\zunedb.BAK     G:\ -Force
Copy-Item <备份>\G\drmStore.dat   G:\ -Force
```

顺序很重要：**先让 3.3 启动一次**，再放回库文件，最后连 Zune 同步。

---

## 7. 与上游的差别

| 项 | `zune30-research` | 本文 |
|---|---|---|
| 写回原机 nk | ✅ 有（"恢复原系统"，升级前必做） | 复用同一动作 |
| 明确分析"3.3 → 1.0 TEST" | ❌ 没有 | ✅ 本文 |
| 降级后的媒体库/DRM 变化 | ❌ 未讨论 | ✅ 第 4 节 |
| 降级再升回的顺序 | ❌ 未讨论 | ✅ 第 6 节 |
| 1.0 TEST 的 U 盘模式作为降级收益 | ❌ 未提及 | ✅ 第 5 节 |

---

## 8. 风险

| 风险 | 说明 |
|---|---|
| 数据分区被重建 | 歌曲/播放列表可能丢失，**先备份 `G:\`** |
| 忘记备份 3.3 的库文件 | 回到 3.3 后同步可能永久失效 |
| 误用零售固件包 | 会把 1.0 TEST 启动器冲掉，**之后不能再刷任何自制镜像** |
| 降级后继续用 Zune 4.8 同步 | 4.8 面向 3.x，1.0 TEST 需要 1.x 时代的客户端或 WMP |
