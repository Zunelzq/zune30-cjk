# zunesync

把本地音乐同步到 Zune（MTP 设备），**带上标签和封面**——解决"资源管理器拖进去后专辑/封面丢失"的问题。

## 为什么需要它

用资源管理器把文件拖进 `Zune栗子球\Storage\Music` 时：

```
资源管理器只报：文件名、大小、格式
设备收到后：Title 可能从文件名猜出来，Album/Genre/封面全是 Unknown
```

而 MTP 的元数据是**主机在创建对象时"报"给设备的**。这个工具在创建对象时把
Title / Artist / Album / Genre / Track / Year 一起写进去，并可选地附带封面对象。

## 支持的格式

| 扩展名 | 格式 | MTP 格式码 |
|---|---|---|
| `.mp3` | MP3 | 0x3009 |
| `.wma` / `.asf` | WMA | 0xB901 |
| `.wav` | WAV | 0x3008 |
| `.m4a` | AAC/M4A | 0x300A（专用 GUID） |
| `.aac` | AAC | 0xB903 |
| `.flac` | FLAC | 0xB906（社区固件注册的码） |
| `.wmv` / `.mp4` | 视频 | 0xB982 / 0xB984 |

格式码来自 Zune 30 固件注册表（`SupportedFormats`）；新增格式只需在
`zunesync/core.py` 的 `FORMATS` 表里加一行。

## 安装

```
pip install mutagen comtypes
```

（`comtypes` 用于调用系统自带的 `PortableDeviceApi.dll`，不需要第三方驱动。）

## 用法

```powershell
# 1. 看本地文件解析出了什么（不碰设备）
python -m zunesync.cli scan "E:\zune\Music"

# 2. 对比设备，看会传哪些（--offline 则不连设备）
python -m zunesync.cli plan "E:\zune\Music"

# 3. 真正同步
python -m zunesync.cli sync "E:\zune\Music" --dry-run     # 先预演
python -m zunesync.cli sync "E:\zune\Music"               # 执行
python -m zunesync.cli sync "E:\zune\Music" --limit 1     # 只传一首试试

# 4. 校验
python -m zunesync.cli verify "song.flac" "other.mp3"
```

### 设备没被识别？

```powershell
python -m zunesync.cli probe            # 看设备树
python -m zunesync.cli probe --props    # 顺便打印音乐对象的属性键
```

## 关键：属性键校准（第一次用必做）

不同固件对"媒体属性"的键定义可能不同。工具内置了一套默认值（`wpd.py` 里的
`DEFAULT_MEDIA_KEYS`），但**第一次使用前应当用真机校准**：

1. 在设备上放一首*已经带专辑信息*的歌（用 Zune 软件同步的）；
2. 运行：

```
python -m zunesync.cli probe --props
```

3. 输出会列出该对象所有可读属性，例如：

```
{2ED8BA05-0AD3-42DC-B0D0-3DBC3588EEA4}, 2 = '歌名'
{2ED8BA05-0AD3-42DC-B0D0-3DBC3588EEA4}, 21 = '歌手'
...
```

4. 把 `guid, pid` 填进 `props.json`：

```json
{
  "title":  ["{2ED8BA05-...}", 2],
  "artist": ["{2ED8BA05-...}", 21],
  "album":  ["{2ED8BA05-...}", 16]
}
```

5. 同步时带上：`--props props.json`

> 校准一次即可；同一固件版本通用。

## 会话限制（重要）

MTP 内容只在**被授权的会话**里可见。实测：

```
资源管理器占着设备时 → 本工具只能看到一个空壳节点
关闭所有资源管理器窗口 → 工具可以正常枚举（待验证）
```

所以同步前请：

1. 关闭所有打开着 `Zune栗子球` 的资源管理器窗口；
2. 不要同时开 Zune 桌面软件（它也会占用设备）。

如果工具报 "enumeration failed" 或只看到 `o500000B` 这样的空壳，就是被占用了。

## 状态

| 部分 | 状态 |
|---|---|
| 本地扫描 / 标签 / 封面解析 | ✅ 已实现，离线测试通过 |
| 格式表（MP3/WMA/WAV/M4A/AAC/FLAC/视频） | ✅ |
| 去重计划（按文件名） | ✅ |
| WPD 创建对象（带元数据） | ⚠️ 已实现，**未在真机上验证** |
| 封面对象 + References 关联 | ❌ 未实现（MTP 封面关联机制未确认，需真机试错） |
| 播放列表写入 | ❌ 需要 MTPZ 授权会话，暂不可行 |

## 已知限制

- 设备只能同时被一个客户端持有；同步时需独占。
- FLAC 在设备上显示为 `.z`（固件对未知扩展名的处理），不影响播放。
- 播放列表成员是 MTP 对象引用，FLAC 对象的格式不被列表写入路径接受。
- 24-bit FLAC 会被解码器降为 16-bit PCM 输出。

## 目录结构

```
zunesync/
  core.py    格式表、标签/封面解析、扫描与计划
  wpd.py     WPD 封装（发现设备、枚举、创建对象、属性）
  cli.py     命令行
tests/
  test_core.py
```

## 测试

```
python tests/test_core.py
```

7 个离线用例：格式码、GUID 规则、M4A 特例、FLAC 标签、计划去重。

## 真机验证结果（Zune 30，固件 3.30.00039.00-00435）

用 MTP 直通（WPD `SendCommand`）在设备上实测：

| 属性 | MTP 属性码 | 可写 | 设备库是否更新 |
|---|---|---|---|
| Title | `0xDC44` | ✅ | ✅ 显示新值 |
| Artist | `0xDC46` | ✅ | ✅ 显示新值 |
| Genre | `0xDC8C` | ✅ | ✅ |
| Album | `0xDC4F` | ❌ `0xA803` | — |
| 封面 | References（码未暴露） | ❌ 未验证 | — |

编码要求：**纯 MTP 值**（`u8 字符数 + UTF-16LE`），不要加 `DataType` 前缀；
加了会被设备当成第一个字符（表现为 `口TEST-ARTIST`）。

写入后设备媒体库会更新，**不需要重启**（实测界面直接显示新 Artist）。

## 用法：给已存在的歌曲补元数据

```powershell
python -m zunesync.cli enrich "测试标题.mp3" --title "曲名" --artist "歌手" --genre "流派"
```

（Album 目前会被固件拒绝，命令会打印失败原因。）

## 已知阻塞

- **专辑字段**：固件返回 `0xA803`（invalid value），各种编码/批量接口均被拒。
  可能只允许 Zune 桌面软件的导入通道写入。
- **封面**：需要对象引用（References），当前对象的支持属性列表里没有该字段。
- **播放列表成员**：同上，References 不可写。
- **设备会话不稳定**：连续打开/关闭 MTP 直通可能让设备重新枚举，操作间留间隔。