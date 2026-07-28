# 会话迁移 SOP —— 把 Claude Code CLI 历史会话同步进 Claude Desktop

## 这个 SOP 是做什么的

你以前用 **Claude Code 命令行（CLI）** 聊过的会话，默认不会出现在 **Claude Desktop 桌面应用**的会话列表里。
这个工具会把它们**一次性同步进 Desktop**，之后你在 Desktop 里就能看到、点开、继续聊。

- 只新增"索引"，**不改动、不删除**你的任何原始对话记录。
- 可以反复运行：已经同步过的会自动跳过，不会重复。
- 可在**任意一台装了 CLI + Desktop 的电脑上就地运行**（自动适配该机的账号和路径，不写死任何机器专属信息）。

---

## 最简单的用法（推荐给任何人）

> 全程只需要在 Claude Desktop 里打字，不用碰命令行、不用懂技术。

### 第 1 步：把本文件夹的完整路径告诉 Claude Desktop

打开 Claude Desktop，把本 SOP 文件夹（含 `sync_cli_sessions.py`）拖进去，或把它的完整路径发给 Claude，并说：

```
请执行这个文件夹里的 sync_cli_sessions.py，
把我的 Claude Code CLI 历史会话同步进 Desktop。步骤见同目录的 README。
```

### 第 2 步：等 Claude 跑完

Claude 会自动运行同步脚本，并告诉你"新增了多少个会话"。

### 第 3 步：完全退出并重新打开 Claude Desktop

- **一定要彻底退出**：右下角托盘图标右键 → 退出（Quit），或任务管理器里结束 Claude 进程。只关窗口不算。
- 重新打开后，会话列表里就能看到你的历史 CLI 会话了（可能需要往下翻，按时间排序）。

### 第 4 步：验证

随便点开一两个会话，确认能看到历史对话、能继续聊。**完成。**

---

## 给 Claude 执行时看的操作步骤（Claude 请按此执行）

脚本 `sync_cli_sessions.py` 与本 README 在同一个文件夹里。以「本 SOP 目录」代指该文件夹。

1. 确认 `本 SOP 目录/sync_cli_sessions.py` 存在；若不存在，向用户询问脚本实际位置。
2. 先跑预览，让用户心里有数：
   ```
   py "本 SOP 目录/sync_cli_sessions.py" --dry-run
   ```
   - 如果 `py` 不可用，依次尝试 `python`、`python3`。
   - 如果整台机器都没有 Python：你（Claude）可以直接按脚本里的同样逻辑手动完成——
     读 `~/.claude/projects/*/*.jsonl`，对每个尚未在 Desktop 存储目录登记的会话，
     生成 `local_<会话id>.json`（schema 见脚本 `build_record`）。
3. 正式执行：
   ```
   py "本 SOP 目录/sync_cli_sessions.py"
   ```
4. 把"新增 N 个"的结果告诉用户，并提醒他**完全退出并重开 Desktop** 才能看到。
5. 结果明细在同目录的 `上次同步结果.txt`（运行时生成，不纳入版本库）。

---

## 原理（想了解的人再看）

真正存对话的，是这个文件（CLI 和 Desktop 共用同一份）：

```
C:\Users\<你>\.claude\projects\<工作目录>\<会话id>.jsonl
```

Desktop 的会话列表，靠的是这些"索引卡片"：

```
%LOCALAPPDATA%\Claude-3p\claude-code-sessions\<账号id>\<组织id>\local_<会话id>.json
```

卡片里只记标题、工作目录、以及 `cliSessionId`（指向哪份 jsonl），**不存对话内容**。
Desktop 恢复会话时执行的就是 `claude --resume <会话id>`，读的还是那份 jsonl。

所以：

- 本工具做的事 = 给每个 CLI 会话补一张 Desktop 缺失的"索引卡片"。
- 同步后，**在 Desktop 里续聊的内容，用 CLI `claude --resume` 也能看到**，反之亦然——因为是同一份 jsonl。

⚠️ **注意**：不要 CLI 和 Desktop **同时打开同一个会话**并同时输入，两边同时往一份 jsonl 里写可能写乱。先后切换没问题。

---

## 常见问题

**Q：脚本报"没找到 Desktop 的会话存储目录"？**
A：说明这台电脑的 Desktop 还没建过任何会话。先在 Desktop 里随便新建并发一句话、保存一个会话，让它自己生成目录，再运行本工具。

**Q：会不会弄坏我原来的对话？**
A：不会。脚本只在 Desktop 的索引目录里**新增** `local_*.json` 文件，从不碰 `~/.claude/projects` 里的原始记录。

**Q：同步后又用 CLI 新开了会话，怎么办？**
A：再运行一次本工具即可。已同步的会跳过，只补新的。

**Q：太短的会话（几句话就结束的）为什么没同步？**
A：脚本默认跳过少于 4 条消息的会话，避免列表被大量无意义会话塞满。想全部同步，可把脚本里的 `MIN_LINES` 改小。

---

## 如何回退（撤销这次同步）

同步只是新增了 `local_*.json` 索引文件，删掉它们即可还原（原始对话不受影响）。
但要注意：**Desktop 自己原生创建的会话也是同名格式**，不能一股脑全删。
如需干净回退，让 Claude 帮你写一个"只删本次同步新增、保留 Desktop 原生会话"的清理脚本即可。

---

> 仓库地址：https://github.com/MenciNank/claude-cli-sessions-to-desktop
