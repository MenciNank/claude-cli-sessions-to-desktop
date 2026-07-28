# -*- coding: utf-8 -*-
r"""
把 Claude Code CLI 的历史会话同步进 Claude Desktop 的会话列表。

原理：
  - 对话内容真正存放在   ~/.claude/projects/<工作目录>/<会话id>.jsonl（CLI 和 Desktop 共用）
  - Desktop 的会话列表靠  %LOCALAPPDATA%\Claude-3p\claude-code-sessions\<账号>\<组织>\local_<会话id>.json
    这些是“索引卡片”，只记录标题/路径/指向哪个 jsonl，不存对话本身。
  - 本脚本为每个尚未登记的 CLI 会话，生成一张索引卡片，让它出现在 Desktop 列表里。
    恢复时 Desktop 执行的就是 `claude --resume <会话id>`，读的还是那份 jsonl。

特点：
  - 全自动探测账号/组织目录，不写死任何机器专属 ID（换台电脑也能用）。
  - 幂等：已登记的会话会跳过，可反复运行，不会重复或覆盖。
  - 只新增文件，绝不修改/删除原始对话（~/.claude/projects 一字不动）。

用法：
  py sync_cli_sessions.py           # 正式同步
  py sync_cli_sessions.py --dry-run # 只预览会新增哪些，不写盘
"""
import os, sys, json, glob, datetime

MIN_LINES = 4          # 少于这么多条消息的会话视为“太短”，跳过，避免列表被垃圾塞满
DRY = "--dry-run" in sys.argv


def log(msg):
    # 控制台在中文 Windows 上可能是 GBK，遇到无法编码的字符不崩溃
    try:
        print(msg)
    except Exception:
        print(msg.encode("ascii", "replace").decode("ascii"))


def find_projects_dir():
    """CLI 会话原文所在目录。"""
    p = os.path.join(os.path.expanduser("~"), ".claude", "projects")
    return p if os.path.isdir(p) else None


def find_store_dir():
    r"""
    自动探测 Desktop 会话索引目录：
    %LOCALAPPDATA%\Claude-3p\claude-code-sessions\<账号uuid>\<组织uuid>\
    选择规则：在所有 <账号>/<组织> 组合里，挑“已有 local_*.json 最多、且最近修改”的那个，
    也就是你当前登录、正在用的那个账号。
    """
    lad = os.environ.get("LOCALAPPDATA")
    if not lad:
        return None, "找不到 LOCALAPPDATA 环境变量（本脚本仅适用于 Windows）。"
    root = os.path.join(lad, "Claude-3p", "claude-code-sessions")
    if not os.path.isdir(root):
        return None, ("没找到 Desktop 的会话存储目录：\n  " + root +
                      "\n请先打开 Claude Desktop 并随便新建一个会话（让它自己生成目录），再运行本脚本。")
    candidates = []
    for acc in glob.glob(os.path.join(root, "*")):
        if not os.path.isdir(acc):
            continue
        for org in glob.glob(os.path.join(acc, "*")):
            if not os.path.isdir(org):
                continue
            cnt = len(glob.glob(os.path.join(org, "local_*.json")))
            mtime = os.path.getmtime(org)
            candidates.append((cnt, mtime, org))
    if not candidates:
        return None, ("Desktop 存储目录存在但里面没有任何会话：\n  " + root +
                      "\n请先在 Claude Desktop 里新建并保存一个会话，再运行本脚本。")
    # 先按已有会话数、再按最近修改时间挑
    candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return candidates[0][2], None


def to_ms(iso):
    try:
        return int(datetime.datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp() * 1000)
    except Exception:
        return 0


def extract(jsonl_path):
    """从一个 .jsonl 里读出 cwd / 标题 / 时间 / 条数。"""
    cwd = ""
    title = ""
    n = 0
    first_ts = None
    last_ts = None
    with open(jsonl_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                o = json.loads(line)
            except Exception:
                continue
            n += 1
            if not cwd and isinstance(o, dict) and o.get("cwd"):
                cwd = o["cwd"]
            ts = o.get("timestamp") if isinstance(o, dict) else None
            if ts:
                if not first_ts:
                    first_ts = ts
                last_ts = ts
            if not title and isinstance(o, dict) and o.get("type") == "user":
                msg = o.get("message", {}) or {}
                c = msg.get("content")
                txt = ""
                if isinstance(c, str):
                    txt = c
                elif isinstance(c, list):
                    for part in c:
                        if isinstance(part, dict) and part.get("type") == "text":
                            txt += part.get("text", "")
                txt = "".join(ch for ch in txt if ch.isprintable()).strip()
                # 跳过斜杠命令、系统提示等，取第一条真实人话
                if txt and not txt.startswith("<") and "command-name" not in txt:
                    title = txt[:50]
    return cwd, (title or "(无标题会话)"), n, first_ts, last_ts


def build_record(cli_id, cwd, title, first_ts, last_ts):
    c_ms = to_ms(first_ts) if first_ts else 0
    l_ms = to_ms(last_ts) if last_ts else c_ms
    return {
        "sessionId": "local_" + cli_id,
        "cliSessionId": cli_id,
        "cwd": cwd,
        "originCwd": cwd,
        "lastFocusedAt": l_ms,
        "createdAt": c_ms,
        "lastActivityAt": l_ms,
        "model": "claude-sonnet-4-6[1m]",
        "effort": "medium",
        "sessionSettings": {"ultracode": False},
        "isArchived": False,
        "title": title,
        "permissionMode": "default",
        "enabledMcpTools": {},
        "remoteMcpServersConfig": [],
        "completedTurns": 1,
        "alwaysAllowedReasons": [],
        "sessionPermissionUpdates": [],
        "classifierSummaryEnabled": False,
        "reportFindingsCard": False,
        "spawnSeed": {},
    }


def main():
    projects = find_projects_dir()
    if not projects:
        log("没找到 CLI 会话目录 ~/.claude/projects —— 你可能从没用过 Claude Code CLI，无需迁移。")
        return 1
    store, err = find_store_dir()
    if err:
        log("[无法继续] " + err)
        return 1

    log("CLI 会话来源: " + projects)
    log("Desktop 索引目录: " + store)
    if DRY:
        log(">>> 预览模式（--dry-run），不会写任何文件 <<<")

    existing = set(os.listdir(store))
    created, skipped_exist, skipped_short = [], 0, 0

    for jf in glob.glob(os.path.join(projects, "*", "*.jsonl")):
        cli_id = os.path.splitext(os.path.basename(jf))[0]
        fname = "local_" + cli_id + ".json"
        if fname in existing:
            skipped_exist += 1
            continue
        cwd, title, n, first_ts, last_ts = extract(jf)
        if n < MIN_LINES:
            skipped_short += 1
            continue
        rec = build_record(cli_id, cwd, title, first_ts, last_ts)
        if not DRY:
            with open(os.path.join(store, fname), "w", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False))
        created.append((cwd, title))

    # 报告：写一份 UTF-8 文件，避免控制台乱码
    report_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "上次同步结果.txt")
    lines = []
    lines.append("=== 会话同步结果 ===")
    lines.append(("[预览] " if DRY else "") + "新增: %d   已存在(跳过): %d   太短(跳过): %d"
                 % (len(created), skipped_exist, skipped_short))
    lines.append("")
    lines.append("--- 本次" + ("将" if DRY else "已") + "新增的会话 ---")
    for cwd, t in created:
        lines.append("[%s] %s" % (cwd, t))
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    log(("[预览] " if DRY else "") + "完成：新增 %d，已存在跳过 %d，太短跳过 %d。"
        % (len(created), skipped_exist, skipped_short))
    log("详细清单见: " + report_path)
    if not DRY and created:
        log("请【完全退出并重开 Claude Desktop】即可在会话列表看到它们。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
