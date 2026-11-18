# Zune 30 线刷教程（USB 免拆盘）

> 适用：本机（已改 AUTH196 3.3 + TEST 启动器）
> 实测：任意 AUTH196 3.3 镜像约 30 秒刷完并自动重启

---

## 一、前置条件

```
Windows 10/11
Python 3.9+（本项目使用 DSH 运行时自带 Python）
USB 数据线
Zune 开机、能连电脑（正常系统或恢复模式都行）
```

工具位置：`E:\DSH\workblock\zune\PROJECT\zune-sync\`

---

## 二、三条命令

```powershell
# 1) 看当前模式与能力
python flash_image.py --list          # 列出所有可用镜像及用途
python switch.py status               # 当前 USB 模式 / 固件版本

# 2) 切模式（两个常用镜像）
python switch.py mtp                  # 切到 MTP 模式（资源管理器传 FLAC）
python switch.py zune                 # 切回 Zune 模式（同步 + FLAC 播放）

# 3) 刷任意镜像（带安全校验）
python flash_image.py <镜像路径>
```

执行时保持 USB 连接，看到 `device back:` 即完成。

---

## 三、镜像选择

| sha8 | 文件 | 用途 |
|---|---|---|
| `23C8D9B9` | CLEAN-FLAC-ZUNE | **日常**：Zune 4.8 同步 + FLAC 播放 + 中文 + SSD 修复 |
| `6A996991` | CJK-FLAC-SAFE | **传 FLAC**：MTP 模式，资源管理器可写 |
| `230A8B43` | SAFE2 | 中文 + SSD 修复，无 FLAC |
| `E66595BE` | CLEAN | 原始 3.3 + 中文，无 SSD 修复 |
| `ABE47A52` | SAFE1 | DMA 参数调整版（未采用） |

镜像目录：`E:\zune_auth196\out1\`

---

## 四、工具做了什么（安全校验）

刷之前：

```
1. 校验文件是 B000FF 容器（不是乱改名）
2. 读取镜像内嵌的 ZV194.dat，算 SHA-256
   与本机 vault 比对 —— 不一致说明是别的设备的镜像，拒绝
3. 检查设备暂存队列为空（避免重复提交）
```

刷之中：

```
0x100C 暂存 → 0x100D 发送 14 MB → 0x9204 提交
```

刷之后：

```
轮询设备重新出现，读出固件版本与是否支持 FLAC，确认镜像真的生效
```

---

## 五、常见现象

| 现象 | 含义 | 处理 |
|---|---|---|
| `disconnect during commit (expected): WPD error 0x8007001F` | 设备重启，正常 | 无需处理 |
| `staging queue busy` | 设备里有未提交的暂存 | 拔插 USB 后重试 |
| `vault check: MISMATCH` | 镜像属于别的设备 | 换镜像；`--force` 强刷大概率黑屏 |
| `device not found` | 没连上/驱动异常 | 换 USB 口、确认设备开机 |
| 刷完黑屏 | 镜像不兼容或损坏 | 进恢复模式（见下） |

---

## 六、恢复模式（系统起不来时）

```
1. 关机（长按电源 15 秒）
2. 按住「返回键」不放
3. 插 USB 线
4. 出现 Connect 后松手
5. 屏幕显示 Pyxis maintenance → 按返回键选 "USB recovery mode"
6. 电脑运行：python flash_image.py <可用镜像>
```

**不要选**：restore factory defaults / format data partition / initialize disk。

恢复模式下设备报告 `00.00.00000.00-00.00`，工具会自动识别并照常刷入。

---

## 七、字体配对（刷完中文变方框时）

| 镜像类型 | 加载器 | 字体大小 |
|---|---|---|
| F214 系（`23C8D9B9`/`6A996991`） | ROM 内 F214 | 8,206,424 |
| ZCJKBoot 系（`CLEAN`/`SAFE2`） | `F:\Fonts\ZCJKBoot.exe` | 与加载器常量一致（当前 8,206,424） |

当前 `F:\Fonts` 已配好 8,206,424 字体与对应加载器，刷上述镜像都不需要改动。

---

## 八、红线

```
❌ 不要刷别的设备的镜像（vault 不匹配）
❌ 不要通过本工具写 EBoot.bin（工具也不支持）
❌ 不要在刷写过程中拔线/断电
✅ 刷坏了进恢复模式重刷（通道在启动器里，始终可用）
✅ 最后手段：拆盘直接改写 F: 分区（归档里有全部镜像）
```

---

## 九、完整示例

```powershell
cd E:\DSH\workblock\zune\PROJECT\zune-sync

# 需要传新 FLAC
python switch.py mtp
# 资源管理器 → Zune栗子球\Storage\Music → 拖入 .flac
python switch.py zune

# 想试别的镜像
python flash_image.py E:\zune_auth196\out1\nk.AUTH196-SAFE2.PRIVATE.bin
# 不满意就刷回来
python flash_image.py E:\zune_auth196\out1\nk.AUTH196-CLEAN-FLAC-ZUNE.PRIVATE.bin
```
