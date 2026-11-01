#!/usr/bin/env python3
"""
挂机执行器 —— 把雷达发现的赏金变成真实产出

三段式（对应业界验证有效的 HITL 模式）：
  1. claim   —— 在 issue 下留言认领（这是竞争的胜负手，AI 全自动最容易翻车的地方）
  2. solve   —— 克隆仓库、跑测试、定位问题、生成修复补丁
  3. propose —— 推送分支并开 PR（或先存为草稿等人工放行）

关键设计原则（有实测依据）：
  · 纯无人值守提 PR 会毁掉账号信誉。业界实测中前 2 天 0 收益、转向"信誉库"后才爆发。
  · 因此默认 --stage claim 只做"占位认领"，实际改码需显式开启 --stage solve。
  · 所有不可逆操作（提交 PR、评论）都先落盘到 outbox/，人工核对后再推。

用法：
  python3 hunter.py --scan                 # 只看有什么可做
  python3 hunter.py --claim                 # 认领（需在 issue 下留言）
  python3 hunter.py --solve --repo X --issue N   # 生成修复补丁
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone

UA = "bounty-hunter/1.0"
GITHUB_API = "https://api.github.com"


def token():
    t = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not t:
        sys.exit("错误：未设置 GITHUB_TOKEN 环境变量")
    return t


def http_json(url, method="GET", body=None, headers=None, timeout=30):
    h = {"User-Agent": UA, "Accept": "application/vnd.github+json"}
    h.update(headers or {})
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        h["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", "replace")
            return resp.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, {"raw": raw[:400]}
    except Exception as e:
        return 0, {"error": str(e)}


def sh(cmd, cwd=None, timeout=300):
    """执行 shell 命令，返回 (returncode, stdout+stderr)。"""
    p = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True,
                       text=True, timeout=timeout)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def get_issue(repo, number):
    st, d = http_json(f"{GITHUB_API}/repos/{repo}/issues/{number}")
    return d if st == 200 else None


def post_comment(repo, number, body):
    st, d = http_json(
        f"{GITHUB_API}/repos/{repo}/issues/{number}/comments",
        method="POST", body={"body": body}, headers={"Authorization": f"Bearer {token()}"})
    return st, d


def clone_repo(repo, workdir):
    """克隆仓库到本地工作区。"""
    if not os.path.isdir(workdir):
        os.makedirs(workdir, exist_ok=True)
    dest = os.path.join(workdir, repo.replace("/", "_"))
    if os.path.isdir(os.path.join(dest, ".git")):
        return dest
    url = f"https://github.com/{repo}.git"
    rc, out = sh(f"git clone --depth 50 {url} {dest}")
    return dest if rc == 0 else None


def build_claim_comment(issue_title, amount, minutes, notes=""):
    """
    认领评论模板。
    要点：给出具体方案而非空喊"我来"，这是维护者接受外部 PR 的关键社会信号。
    """
    plan = (
        "I'd like to work on this. My approach:\n\n"
        f"- **Task**: {issue_title}\n"
        f"- **Plan**: Reproduce the issue against the current default branch, "
        "identify the root cause in the affected module, then implement a focused "
        "fix that follows the repository's existing conventions.\n"
        "- **Testing**: Run the existing test suite before and after the change; "
        "add a regression test covering the reported behaviour.\n"
        "- **Scope**: Keep the change minimal — no unrelated refactors or "
        "dependency upgrades.\n\n"
        "If the maintainers prefer a different approach or the scope needs "
        "adjusting, please let me know and I'll follow your direction.\n"
    )
    if amount:
        plan += f"\n(Noted the ${amount:.0f} bounty label — happy to go through "
        plan += "the standard claim/claim flow.)\n"
    if notes:
        plan += f"\n{note}\n"
    return plan


def do_claim(args):
    """认领目标 issue：先在本地生成评论，再确认推送。"""
    issue = get_issue(args.repo, args.issue)
    if not issue:
        print("无法读取 issue，请确认 repo/编号与权限")
        return 1
    if issue.get("state") != "open":
        print(f"issue 已关闭（state={issue.get('state')}），跳过")
        return 1
    if issue.get("assignee"):
        print("issue 已被指派，跳过")
        return 1

    labels = " ".join(l.get("name", "") for l in issue.get("labels", []))
    m = re.search(r"price:\s*([\d.]+)\s*usd", labels, re.I)
    amount = float(m.group(1)) if m else None
    tm = re.search(r"time:\s*<\s*(\d+)\s*(minute|min|hour|day)", labels, re.I)
    minutes = None
    if tm:
        v = int(tm.group(1))
        u = tm.group(2).lower()
        minutes = v * (60 if u.startswith("hour") else 1440 if u.startswith("day") else 1)

    comment = build_claim_comment(issue.get("title", ""), amount, minutes)

    os.makedirs("outbox", exist_ok=True)
    fn = f"outbox/claim_{args.repo.replace('/','_')}_{args.issue}.md"
    with open(fn, "w", encoding="utf-8") as f:
        f.write(comment)
    print(f"评论已生成：{fn}")
    print("-" * 60)
    print(comment)
    print("-" * 60)

    if args.yes:
        st, d = post_comment(args.repo, args.issue, comment)
        if st in (200, 201):
            print(f"✅ 已评论：{d.get('html_url')}")
        else:
            print(f"❌ 评论失败（HTTP {st}）：{d}")
            return 1
    else:
        print("未推送。确认内容无误后加 --yes，或手动复制到 issue 评论框。")
    return 0


def do_solve(args):
    """
    克隆并产出修复补丁骨架。
    注意：真正的代码修复需要模型推理能力，此处负责环境准备与上下文提取，
    补丁由上层 Agent 生成后通过 --patch-file 注入。
    """
    workdir = args.workdir
    dest = clone_repo(args.repo, workdir)
    if not dest:
        print("克隆失败")
        return 1
    print(f"仓库已克隆：{dest}")

    issue = get_issue(args.repo, args.issue)
    if issue:
        title = issue.get("title", "")
        body = (issue.get("body") or "")[:4000]
    else:
        title, body = "", ""

    # 读取 CONTRIBUTING 约定——决定 PR 能否被合并
    contrib = ""
    for p in ["CONTRIBUTING.md", ".github/CONTRIBUTING.md", "CONTRIBUTING.rst"]:
        fp = os.path.join(dest, p)
        if os.path.exists(fp):
            contrib = open(fp, encoding="utf-8", errors="ignore").read()[:2000]
            print(f"找到贡献指南：{p}")
            break

    # 探测测试命令
    test_cmd = ""
    pkg = os.path.join(dest, "package.json")
    if os.path.exists(pkg):
        try:
            scripts = json.load(open(pkg)).get("scripts", {}) or {}
            for key in ("test", "test:unit", "lint"):
                if key in scripts:
                    test_cmd = f"npm run {key}"
                    break
        except Exception:
            pass
    if not test_cmd and os.path.exists(os.path.join(dest, "Makefile")):
        test_cmd = "make test"
    if not test_cmd and os.path.exists(os.path.join(dest, "pyproject.toml")):
        test_cmd = "pytest"
    print(f"测试命令：{test_cmd or '未识别（需人工确认）'}")

    ctx = {
        "repo": args.repo,
        "issue": args.issue,
        "title": title,
        "body": body,
        "contributing": contrib,
        "test_command": test_cmd,
        "workdir": dest,
        "branch": args.branch,
    }
    os.makedirs("outbox", exist_ok=True)
    with open("outbox/context.json", "w", encoding="utf-8") as f:
        json.dump(ctx, f, ensure_ascii=False, indent=2)
    print("上下文已写入 outbox/context.json")

    if args.patch_file:
        if not os.path.exists(args.patch_file):
            print("补丁文件不存在")
            return 1
        sh(f"cp {args.patch_file} {dest}/agent.patch")
        rc, out = sh(f"cd {dest} && git apply --check agent.patch")
        if rc != 0:
            print(f"❌ 补丁无法应用：\n{out[:500]}")
            return 1
        sh(f"cd {dest} && git checkout -b {args.branch} && git apply agent.patch")
        print(f"✅ 补丁已应用，分支 {args.branch}")
        rc, out = sh(f"cd {dest} && git add -A && git commit -m 'fix: resolve #{args.issue} - automated bounty fix'")
        print(out[-500:])
        print("补丁已提交到本地分支。下一步：创建远端分支并开 PR（见 README 手动步骤）。")
    return 0


def do_scan(args):
    """列出当前可认领的目标（读取雷达生成的报告）。"""
    path = args.report or os.path.join("reports", "latest.json")
    if not os.path.exists(path):
        print(f"未找到报告 {path}，请先运行 radar/scan.py")
        return 1
    d = json.load(open(path, encoding="utf-8"))
    pool = d.get("pool", []) or d.get("bounties", [])
    if not pool:
        print("报告为空")
        return 1
    print(f"可认领目标 {len(pool)} 条（按评分排序，仅显示前 {args.limit} 条）：\n")
    for b in pool[:args.limit]:
        a = b["analysis"]
        tb = a.get("time_budget_min")
        tstr = f"{tb}分钟" if tb else "?"
        print(f"  [{a['score']:>5}] ${str(a['amount']):>6} | {tstr:>8} | {b['repo']}")
        print(f"          {b['title'][:70]}")
        print(f"          {b['url']}")
        print(f"          判据: {'；'.join(a['reasons'][:4])}")
        print()
    return 0


def main():
    ap = argparse.ArgumentParser(description="GitHub 赏金挂机执行器")
    ap.add_argument("--scan", action="store_true", help="列出可做目标")
    ap.add_argument("--claim", action="store_true", help="认领 issue")
    ap.add_argument("--solve", action="store_true", help="克隆并准备修复")
    ap.add_argument("--repo", help="owner/repo")
    ap.add_argument("--issue", type=int, help="issue 编号")
    ap.add_argument("--yes", action="store_true", help="确认推送（跳过人工核对）")
    ap.add_argument("--patch-file", help="要应用的补丁文件")
    ap.add_argument("--branch", default="agent/bounty-fix", help="分支名")
    ap.add_argument("--workdir", default="/tmp/bounty-work", help="克隆工作目录")
    ap.add_argument("--report", help="雷达报告路径")
    ap.add_argument("--limit", type=int, default=10)
    args = ap.parse_args()

    if args.scan:
        return do_scan(args)
    if args.claim:
        if not args.repo or not args.issue:
            ap.error("--claim 需要 --repo 和 --issue")
        return do_claim(args)
    if args.solve:
        if not args.repo or not args.issue:
            ap.error("--solve 需要 --repo 和 --issue")
        return do_solve(args)
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
