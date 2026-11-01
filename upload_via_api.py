#!/usr/bin/env python3
"""
通过 GitHub REST API 上传文件 —— git 协议走不通时的替代方案。

背景：部分网络环境（含本机）下 git push 会报 "CONNECT tunnel failed, 502"
或 "Error in the HTTP2 framing layer"，因为 git 走的是 git-upload-pack 长连接，
而代理对这种连接的兼容性较差。但普通的 HTTPS REST API 调用是通的。
本脚本用 Contents API 逐个创建文件，效果与 git push 等价。

用法：python3 upload_via_api.py [项目目录]
"""
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request

OWNER = "zd79tc46zs-web"
REPO = "bounty-radar"
API = f"https://api.github.com/repos/{OWNER}/{REPO}"
TOKEN_FILE = ".token"

# ── 权限补充说明（实测 403 根因）──
# 上传 .github/workflows/*.yml 需要 "Workflows" repository permission (write)
# 读取 actions/secrets/public-key 需要 "Secrets" repository permission (read)
# 写入 secrets 需要 "Secrets" repository permission (write)
# 缺少以上权限时 API 返回 403 "Resource not accessible by personal access token"


# 跳过这些（本地文件，不该进仓库）
SKIP_NAMES = {".DS_Store", ".token", ".env"}
SKIP_DIRS = {".git", "__pycache__", "outbox", ".venv", "venv", ".idea", ".vscode"}
SKIP_EXT = {".pyc", ".key", ".pem", ".patch"}


def get_token():
    for p in [TOKEN_FILE, os.path.join(os.path.dirname(os.path.abspath(__file__)), TOKEN_FILE)]:
        if os.path.exists(p):
            t = open(p, encoding="utf-8").read().strip()
            if t.startswith("github_pat_"):
                return t
    return None


def request(method, path, body=None, token=None, timeout=40):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
        "User-Agent": "bounty-radar-setup",
    }
    req = urllib.request.Request(API + path, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", "replace")
            return resp.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, {"message": raw[:300]}
    except Exception as e:
        return 0, {"message": str(e)}


def collect_files(root):
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if fn in SKIP_NAMES:
                continue
            ext = os.path.splitext(fn)[1]
            if ext in SKIP_EXT:
                continue
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, root)
            out.append((full, rel.replace(os.sep, "/")))
    return out


def upload(root, token):
    files = collect_files(root)
    print(f"准备上传 {len(files)} 个文件")

    ok = fail = skip = 0
    for full, rel in sorted(files, key=lambda x: (x[1] != "README.md", x[1])):
        try:
            content = open(full, "rb").read()
        except Exception as e:
            print(f"  ✗ 读取失败 {rel}: {e}")
            fail += 1
            continue

        # 文本文件用文本模式，保留可读性；大文件跳过（走 git LFS 不现实）
        if len(content) > 3 * 1024 * 1024:
            print(f"  ⊘ 跳过超大文件 {rel}（{len(content)//1024}KB）")
            skip += 1
            continue

        b64 = base64.b64encode(content).decode("ascii")
        body = {
            "message": f"feat: 上传 {rel}",
            "content": b64,
            "branch": "main",
        }

        # 已存在则需带 sha 更新
        st, d = request("GET", f"/contents/{urllib.parse.quote(rel)}", token=token)
        if st == 200 and isinstance(d, dict) and d.get("sha"):
            body["sha"] = d["sha"]
            st, d = request("PUT", f"/contents/{urllib.parse.quote(rel)}", body, token)
        else:
            st, d = request("PUT", f"/contents/{urllib.parse.quote(rel)}", body, token)

        if st in (200, 201):
            ok += 1
            print(f"  ✓ {rel}")
        else:
            fail += 1
            msg = d.get("message", "") if isinstance(d, dict) else str(d)
            print(f"  ✗ {rel} → HTTP {st}: {msg[:120]}")
            if st == 403 and ".github/workflows" in rel:
                print("      → 需要在 token 上加 Workflows 权限 (Read and write)")
                print("      → https://github.com/settings/personal-access-tokens → radar → 编辑")
                print("      → 加完后重跑本脚本即可，只需补传这一个文件")

        time.sleep(0.25)  # 控制 API 调用频率

    print(f"\n成功 {ok} ｜ 失败 {fail} ｜ 跳过 {skip}")
    return 0 if fail == 0 else 1


def configure_secret(token):
    """配置 Actions 密钥：取公钥 → openssl 加密 → PUT。"""
    import subprocess
    print("\n配置 Actions 密钥 GITHUB_TOKEN…")
    st, d = request("GET", "/actions/secrets/public-key", token=token)
    if st != 200:
        msg = d.get("message", "") if isinstance(d, dict) else str(d)
        print(f"  ✗ 取公钥失败 HTTP {st}: {msg}")
        if st == 403:
            print("    → 需要在 token 上加 Secrets 权限 (Read and write)")
            print("    → https://github.com/settings/personal-access-tokens → 点 radar → 编辑")
        return False
    pubkey = d.get("key", "")
    key_id = d.get("key_id", "")
    if not pubkey:
        print("  ✗ 公钥为空")
        return False

    tmp = "/tmp/.secrets_payload"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(token)

    # macOS 的 openssl 不支持 -outform DER 用于 pkeyutl，改用 -pkeyopt rsa_padding_mode:pkcs1
    enc = subprocess.run(
        ["openssl", "pkeyutl", "-encrypt", "-pubin", "-inkey", "/dev/stdin",
         "-in", tmp, "-outform", "DER", "-pkeyopt", "rsa_padding_mode:pkcs1"],
        input=pubkey, capture_output=True, text=False)
    if enc.returncode != 0 or not enc.stdout:
        # 回退：把公钥写成文件
        pk = "/tmp/.pubkey.pem"
        with open(pk, "w", encoding="utf-8") as f:
            f.write(pubkey)
        enc = subprocess.run(
            ["openssl", "pkeyutl", "-encrypt", "-pubin", "-inkey", pk,
             "-in", tmp, "-outform", "DER", "-pkeyopt", "rsa_padding_mode:pkcs1"],
            capture_output=True)
    os.remove(tmp)

    if not enc.stdout:
        print("  ✗ 加密失败")
        return False
    encrypted = base64.b64encode(enc.stdout).decode("ascii")

    st, d = request("PUT", "/actions/secrets/GITHUB_TOKEN",
                    {"encrypted_value": encrypted, "key_id": key_id}, token)
    if st in (201, 204) or (st == 200 and not d.get("message")):
        print("  ✓ 密钥已加密写入（明文不落盘于仓库）")
        return True
    print(f"  ✗ 写入失败 HTTP {st}: {str(d)[:200]}")
    return False


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__))
    root = os.path.abspath(root)

    token = get_token()
    if not token:
        print("✗ 找不到 .token 文件（里面应有 github_pat_ 开头的 token）")
        return 1
    print(f"✓ 读取到 token（{len(token)} 位）\n")

    st, d = request("GET", "", token=token)
    if st != 200:
        print(f"✗ 仓库访问失败 HTTP {st}: {d.get('message')}")
        return 1
    print(f"✓ 目标仓库：{d.get('full_name')}（{'空仓库' if d.get('size') == 0 else '已有内容'}）\n")

    rc = upload(root, token)
    configure_secret(token)

    print("\n" + "=" * 50)
    print(f" 仓库地址：https://github.com/{OWNER}/{REPO}")
    print(" 下一步：打开仓库 → Actions 标签 → 选「挂机收益雷达」→ Run workflow")
    print("=" * 50)
    return rc


if __name__ == "__main__":
    import urllib.parse
    sys.exit(main())
