# MTP 元数据写入：Zune 30 实测结论

> 目标：把本地音乐传进 Zune 时保留 Title / Artist / Album / Genre / 封面。
> 结论：**前三项可写，专辑、封面、播放列表成员不可写**。以下是完整证据。

## 1. 为什么资源管理器拖拽会丢元数据

资源管理器复制走 WPD 高层接口，只提交文件名/大小；设备把标题和艺术家**从路径猜出来**，
专辑、流派、封面一律 `Unknown`。

实测：复制一个带完整 ID3 标签的 MP3 后，设备显示：

```
Title  = 星の在り処 (Harmonica Short version)   ← 来自文件名
Artist = Falcom Sound Team jdk                 ← 来自文件夹名
Album  = Unknown Album                         ← 丢失
Genre  = Unknown Genre
```

## 2. 通道：WPD 的 MTP 直通

Zune 驱动把标准 MTP 命令暴露为 WPD `SendCommand`
（`WPD_CATEGORY_MTP_DEVICE_COMMANDS`）。这条路绕开 WPD 高层对象 API 的只读限制：

```python
values.SetGuidValue(COMMON, 1001, GUID(MTP))
values.SetUnsignedIntegerValue(PROP_COMMON_COMMAND, 12)   # 12 无数据 / 13 读 / 14 写
```

设备响应（固件 3.30.00039.00-00435）：

```
formats: 0xb906(FLAC) 0x3009(MP3) 0xb901(WMA) 0xb903(AAC) 0x3801(JPEG) 0xba05(Playlist) ...
operations: 0x100c SendObjectInfo, 0x100d SendObject, 0x9801..0x9802, 0x9810/0x9811
```

注意：`0x9804 SetObjectPropValue` **不在**设备声明的操作列表里，但实际可用；
`0x100c` 的响应参数（新对象句柄）无法通过 WPD 读出。

## 3. 属性映射与可写性（真机验证）

| 字段 | 属性码 | 可写 | 设备显示 |
|---|---|---|---|
| Title | `0xDC44` | ✅ | 立即更新 |
| Artist | `0xDC46` | ✅ | 立即更新 |
| Genre | `0xDC8C`（注意不是标准的 `0xDC4E`） | ✅ | 立即更新 |
| **Album** | `0xDC4F` | ❌ `0xA803` | 仍 `Unknown Album` |
| FileName | `0xDC07` | ✅ | 对象名变化 |
| 厂商扩展 | `0xDA01` `0xDA05` `0xDA9A` `0xDC47` | ✅ 可写 | 不映射到专辑 |

### 编码规则（关键）

属性值必须是**裸 MTP 值**：

```
字符串: u8 字符数 + UTF-16LE + 结束符
整数:   u32
```

**不要**加 `DataType` 前缀（`0xFFFF`）。加了会被设备当成字符串第一个字符，
表现为 `口TEST-ARTIST`（多一个 U+0CFF 之类的杂字符）。

## 4. 专辑为什么写不进去

尝试过的所有路径，全部返回 `0xA803`（invalid object property value）：

| 方法 | 结果 |
|---|---|
| `0x9804` + `0xDC4F`，带 DataType 前缀 | `0xA803` |
| `0x9804` + `0xDC4F`，裸编码 | `0xA803` |
| `0x9806 SetObjectPropList`（DataType 0xFFFF / 0x0000） | `0xA803` |
| `0x9811`（厂商批量接口） | `0x2009 invalid object handle` |
| 用 `0xDA01/0xDA05/0xDA9A/0xDC47` 冒充专辑 | 写入成功，设备仍显示 `Unknown Album` |

`0xDC4F` 在"支持的属性"列表里存在（可读），但写入被拒——**读得到、写不了**。

推断：专辑归属由 Zune 桌面软件的导入流程建立（它用带认证的 MTP 会话），
第三方会话只能改文本类属性。

## 5. 封面与播放列表

- 音频对象的支持属性列表里**没有** `References` 类字段，无法建立"曲目→封面图"关联。
- 设备声明支持 `0xBA05`（抽象播放列表）对象，说明列表在协议层存在；
  但同样的引用写入路径不可用，且资源管理器建列表只会产生空列表。

## 6. 会话行为

- 同一时刻只允许一个客户端持有内容会话：资源管理器打开设备时，
  另开的 WPD 会话只能看到一个空壳节点（`s10001 → o500000B`，无子项）。
- 连续快速开关 MTP 会话会让设备重新枚举，表现为工具 `discover()` 间歇性为空。
  操作之间留 1–2 秒间隔、并在一次会话里完成批量写入。
- WPD 高层写入返回 `0x80004005`，且存储的 `WPD_STORAGE_ACCESS_CAPABILITY = 0`（只读）；
  MTP 直通写入不受此限制。

## 7. 对同步工具的意义

可行的组合：

```
1. 资源管理器（或 MTP SendObject）把文件送进设备   ← 建立对象
2. MTP 直通补写 Title / Artist / Genre            ← 实测有效
```

不可行：

```
专辑、封面、播放列表成员  ← 固件拒绝或未暴露
```

因此 `zunesync` 的定位是"**元数据修补器**"：传输仍走系统通道，属性用它补。
若专辑是硬需求，只能回到 Zune 桌面软件导入（但它不支持 FLAC）。

## 8. 复现命令

```powershell
# 找到设备上已有对象并改属性（实测把 Artist/Genre 改成功）
python -m zunesync.cli enrich "歌曲名.mp3" --artist "CLEAN-ARTIST" --genre "CLEAN-GENRE"

# 专辑会打印失败原因
python -m zunesync.cli enrich "歌曲名.mp3" --album "TEST-ALBUM"
```

设备验证：音乐库立即显示 `CLEAN-ARTIST`，无需重启。
