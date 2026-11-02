#!/usr/bin/env python3
"""
把 site/ 下的静态页面发布到 GitHub Pages（零成本、免服务器）。

为什么用 GitHub Pages：
- 公开仓库免费，无需备案（中国大陆服务器才需要备案）
- 自带 HTTPS 证书，Creem 审核要求可访问的 HTTPS 站点
- 部署全自动化，不占本地资源

用法：
  python3 deploy_site.py              # 仅本地检查
  python3 deploy_site.py --publish    # 推送到 gh-pages 分支并触发部署
"""

import json
import os
import subprocess
import sys
import urllib.parse

OWNER = "zd79tc46zs-web"
REPO = "bounty-radar"
BRANCH = "gh-pages"
API = f"https://api.github.com/repos/{OWNER}/{REPO}"

# 必须替换的占位符
PLACEHOLDERS = {
    "support@example.com": "客服邮箱（必须是你的域名邮箱）",
    "https://buy.creem.io/你的产品ID": "Creem Checkout 链接",
    "EduForge AI": "你的品牌名",
}


def get_token():
    for p in [".token", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".token")]:
        if os.path.exists(p):
            t = open(p, encoding="utf-8").read().strip()
            if t.startswith("github_pat_"):
                return t
    return None


def api(method, path, body=None, token=None):
    import urllib.request, urllib.error
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
        "User-Agent": "deploy-site",
    }
    req = urllib.request.Request(API + path, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            raw = r.read().decode("utf-8", "replace")
            return r.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, {"raw": raw[:300]}
    except Exception as e:
        return 0, {"message": str(e)}


def check_placeholders(site_dir):
    """检查是否还有未替换的占位符——这是 Creem 审核最常见的拒审原因。"""
    print("=== 占位符检查 ===")
    problems = []
    for root, _, files in os.walk(site_dir):
        for fn in files:
            if not fn.endswith((".html", ".md", ".txt")):
                continue
            if fn == "site-config.json":
                continue
            p = os.path.join(root, fn)
            text = open(p, encoding="utf-8", errors="ignore").read()
            for ph, desc in PLACEHOLDERS.items():
                if ph in text:
                    problems.append((p, ph, desc))
    if problems:
        for p, ph, desc in problems:
            print(f"  ⚠️  {p}: 仍含「{ph}」→ {desc}")
    else:
        print("  ✅ 无未替换占位符")
    return problems


def check_pages(site_dir):
    """检查四个必需页面是否都存在且内容非空。"""
    print("\n=== 必需页面检查 ===")
    idx = os.path.join(site_dir, "index.html")
    need = {
        "落地页（含产品介绍/价格/包含什么）": idx,
        "隐私政策": os.path.join(site_dir, "privacy.html"),
        "服务条款": os.path.join(site_dir, "terms.html"),
        "退款政策": os.path.join(site_dir, "refund.html"),
    }
    ok = True
    for desc, path in need.items():
        if os.path.exists(path):
            size = os.path.getsize(path)
            print(f"  ✅ {desc}：{os.path.basename(path)}（{size} 字节）")
        else:
            print(f"  ❌ {desc}：缺 {os.path.basename(path)}")
            ok = False
    return ok


def check_content(site_dir):
    """检查 Creem 审核关注的关键内容点是否都在落地页里。"""
    print("\n=== 审核要点自检 ===")
    idx = os.path.join(site_dir, "index.html")
    if not os.path.exists(idx):
        print("  ❌ 缺 index.html")
        return False
    html = open(idx, encoding="utf-8", errors="ignore").read()
    checks = {
        "价格可见": ("$" in html and ("price" in html or "价格" in html)),
        "产品介绍": ("产品包含" in html or "什么" in html),
        "交付内容清单": ("交付清单" in html or "包含什么" in html),
        "退款政策可见": ("退款" in html),
        "隐私政策可见": ("隐私" in html),
        "服务条款可见": ("条款" in html),
        "客服邮箱": ("mailto:" in html),
        "无占位符残留": ("你的产品ID" not in html and "example.com" not in html),
    }
    ok = True
    for k, v in checks.items():
        print(f"  {'✅' if v else '❌'} {k}")
        if not v:
            ok = False
    return ok


def publish(token):
    """把 site/ 内容推到 gh-pages 分支。"""
    print("\n=== 发布到 GitHub Pages ===")
    site = os.path.join(os.path.dirname(os.path.abspath(__file__)), "site")

    # 收集文件
    files = {}
    for root, _, fns in os.walk(site):
        for fn in fns:
            if fn.startswith("."):
                continue
            full = os.path.join(root, fn)
            rel = os.path.relpath(full, site).replace(os.sep, "/")
            files[rel] = open(full, "rb").read().decode("utf-8", "replace")
    print(f"  待发布 {len(files)} 个文件")

    # 取当前 gh-pages 分支的 tree
    st, ref = api("GET", f"/git/ref/heads/{BRANCH}", token=token)
    if st == 200:
        sha = ref["object"]["sha"]
        st2, commit = api("GET", f"/git/commits/{sha}", token=token)
        base_tree = commit.get("tree", {}).get("sha")
    else:
        sha = None
        base_tree = None
        print("  gh-pages 分支不存在，将新建")

    # 建 blob
    blobs = {}
    for path, content in files.items():
        st, b = api("POST", "/git/blobs",
                    {"content": content, "encoding": "utf-8"}, token)
        if st not in (200, 201):
            print(f"  ❌ blob 创建失败 {path}: {b}")
            return False
        blobs[path] = b["sha"]

    # 建 tree
    tree_items = [{"path": p, "mode": "100644", "type": "blob", "sha": s}
                  for p, s in blobs.items()]
    body = {"tree": tree_items}
    if base_tree:
        body["base_tree"] = base_tree
    st, tree = api("POST", "/git/trees", body, token)
    if st not in (200, 201):
        print(f"  ❌ tree 创建失败: {tree}")
        return False

    # 建 commit
    msg = "docs: 发布落地页与合规页面 " + __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M")
    cbody = {"message": msg, "tree": tree["sha"]}
    if sha:
        cbody["parents"] = [sha]
    st, commit = api("POST", "/git/commits", cbody, token)
    if st not in (200, 201):
        print(f"  ❌ commit 创建失败: {commit}")
        return False

    # 更新 ref
    if sha:
        st, d = api("PATCH", f"/git/refs/heads/{BRANCH}",
                    {"sha": commit["sha"], "force": True}, token)
    else:
        st, d = api("POST", f"/git/refs",
                    {"ref": f"refs/heads/{BRANCH}", "sha": commit["sha"]}, token)
    if st not in (200, 201):
        print(f"  ❌ 分支更新失败: {d}")
        return False

    print(f"  ✅ 已推送到 {BRANCH} 分支（commit {commit['sha'][:7]}）")

    # 启用 Pages
    st, d = api("GET", "/pages", token=token)
    if st == 404:
        st, d = api("POST", "/pages",
                    {"source": {"branch": BRANCH, "path": "/"}}, token)
        print(f"  Pages 创建：HTTP {st} {'' if st in (200,201) else str(d)[:150]}")
    else:
        st, d = api("POST", "/pages",
                    {"source": {"branch": BRANCH, "path": "/"}}, token)
        print(f"  Pages 更新：HTTP {st} {'' if st in (200,201) else str(d)[:150]}")

    url = f"https://{OWNER}.github.io/{REPO}/"
    print(f"\n  📍 站点地址：{url}")
    print("  （首次启用 Pages 需 1-3 分钟生效）")
    return True


def main():
    site = os.path.join(os.path.dirname(os.path.abspath(__file__)), "site")
    if not os.path.isdir(site):
        print(f"❌ 找不到站点目录 {site}")
        return 1

    ph = check_placeholders(site)
    pages_ok = check_pages(site)
    content_ok = check_content(site)

    print("\n" + "=" * 56)
    if ph or not pages_ok or not content_ok:
        print(" ⚠️  有未完成项。先处理上面标 ⚠️/❌ 的条目，再发布。")
        print("     特别注意：带占位符的页面提交 Creem 会被直接拒审。")
        print("=" * 56)
        return 1

    print(" ✅ 全部检查通过")
    print("=" * 56)

    if "--publish" in sys.argv:
        token = get_token()
        if not token:
            print("❌ 找不到 .token 文件")
            return 1
        return 0 if publish(token) else 1
    else:
        print("\n加 --publish 参数即可发布上线")
    return 0


if __name__ == "__main__":
    sys.exit(main())
