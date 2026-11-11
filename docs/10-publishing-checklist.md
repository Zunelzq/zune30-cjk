# 发布前检查清单（去敏 / 合规）

发到 GitHub 之前，逐条过一遍。

## 1. 绝对不能进仓库的文件

```powershell
# 快速自检：仓库里不应出现任何二进制/固件/字体
Get-ChildItem -Recurse -File -Include *.bin,*.cab,*.ttf,*.ttc,*.edb,*.dat
```

| 类别 | 例子 | 原因 |
|---|---|---|
| 固件镜像 | `nk.bin`、`EBoot.bin`、`recovery.bin`、`*.cab` | 微软版权 |
| 设备专属产物 | `nor.original.bin`、`vault.legacy.bin`、`*AUTH196*`、`zunedb.dat`、`drmStore.dat` | 含设备加密身份 |
| 字体 | `simsun.ttc`、`msgothic.ttc`、`gulim.ttc`、自建子集 | 商业字体授权 |
| 密钥/证书 | 任何 `*.p7b`、`devcert.dat` | 安全 |
| Zune 软件 | 安装包、汉化补丁 | 版权 |

`.gitignore` 已覆盖上述扩展名；`git add .` 前仍然建议先 `git status` 看一眼。

## 2. 截图去敏

| 内容 | 处理 |
|---|---|
| 设备名（机主昵称） | 文字里替换成占位符；图片里打码 |
| 专辑封面（第三方插画） | 打码 |
| 序列号、账号、路径 | 不应出现；如出现必须裁掉 |
| 房间背景、手、桌面杂物 | 视情况裁剪，避免可识别信息 |

当前 `assets/` 里的四张图已处理：
`01-boot-device-name-redacted.jpg`、`02-main-menu.jpg`、
`03-now-playing-jp-redacted.jpg`、`04-now-playing-cn-redacted.jpg`。

## 3. 文本去敏

```powershell
# 把 <...> 换成你自己要排查的词：本机用户名、盘符、设备昵称、序列号片段
Select-String -Path (Get-ChildItem -Recurse -Include *.md,*.py,*.ps1) `
  -Pattern '<你的用户名>','<盘符>:\','<设备昵称>','<序列号前8位>'
```

文档里一律使用：
- 相对路径（`tools/upgrade/build_upgrade.py`）或 `<your-backup>` 占位；
- “a Chinese device name” / “示例名” 代替真实昵称；
- 不写设备序列号、不写购买渠道、不写个人信息。

## 4. 法律表述

`NOTICE.md` 已经包含：

- 明确“不含固件/字体/密钥”；
- 说明这是**对自有硬件的互操作性研究**，不解密任何受保护内容；
- 诚实提示 DMCA §1201 等反规避条款的风险，并声明“非法律意见”；
- 不提供固件下载链接，只描述公开保存档案的存在。

发布时**不要**在 README 里加“下载固件”的链接，也不要附带任何 cab/bin。

## 5. 账号与署名

| 建议 | 说明 |
|---|---|
| 用**与真实身份无关**的 GitHub 账号发布 | 降低被关联的风险 |
| 提交邮箱使用 GitHub 的 `noreply` 地址 | `git config user.email "ID+user@users.noreply.github.com"` |
| 不要在 commit 里写真实姓名/公司 | `git log` 会永久保留 |
| 仓库描述避免“破解/jailbreak/绕过”等措辞 | 用 “interoperability research”“preservation” 更准确 |
| 不要上传含 EXIF 的原图 | 现在的图已重新保存，EXIF 已剥离 |

## 6. 发布命令

```powershell
cd <你的仓库目录>
git init
git config user.name  "<你的昵称>"
git config user.email "<ID>+<你的昵称>@users.noreply.github.com"
git add .
git status            # 再确认一次没有 bin/cab/ttf
git commit -m "Zune 30 (Keel): native CJK rendering on official 3.3 firmware"
git branch -M main
git remote add origin https://github.com/<账号>/zune30-cjk.git
git push -u origin main
```

## 7. 发布后

- 在 README 顶部保留那句 “no Microsoft firmware and no licensed fonts are distributed here”；
- 如果有人求固件，回复“请自行从你的设备/合法渠道获取”，不要私发；
- 收到 DMCA 或厂商联系时：**先下架、再沟通**，仓库里没有二进制，通常只需移除个别文档；
- 保留 `NOTICE.md` 的免责声明与致谢，不要为了“简洁”删掉。

## 8. 可选：更保守的做法

如果仍然担心，可以只发布 **`docs/05-font-mechanism.md` + `docs/09-lessons-learned.md`**
两篇纯分析文章（不含脚本），把工程细节留作私有。这两篇已经足以让社区知道
“3.3 的中文字体是从 ROM 里的 `ZegoeUI*.ttf` 加载的”，而不提供任何可直接执行的改造流程。
