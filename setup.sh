#!/bin/bash
# 一键部署脚本：剪贴板读 token → 建仓 → 推代码 → 配 Actions 密钥
# 设计原则：token 全程不打印到屏幕、不进 shell 历史、不写入仓库
set -euo pipefail

REPO_NAME="bounty-radar"
GITHUB_USER="zd79tc46zs-web"
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

red()   { printf '\033[0;31m%s\033[0m\n' "$*"; }
green() { printf '\033[0;32m%s\033[0m\n' "$*"; }
blue()  { printf '\033[0;34m%s\033[0m\n' "$*"; }

cd "$PROJECT_DIR"

# ── 1. 从剪贴板读取 token ──
blue "【1/5】读取剪贴板中的 token…"
TOKEN="$(pbpaste | tr -d '\n\r' | tr -d ' ')"
if [[ ! "$TOKEN" =~ ^github_pat_ ]]; then
  red "✗ 剪贴板里不是 GitHub token。"
  red "  请先回到 GitHub 页面，点 token 右侧的复制图标，再回来运行本脚本。"
  exit 1
fi
TOKEN_LEN=${#TOKEN}
if [[ "$TOKEN_LEN" -lt 80 ]]; then
  red "✗ token 长度只有 $TOKEN_LEN 位，正常应 90+ 位——可能没复制全。"
  exit 1
fi
green "✓ 读到 token（长度 $TOKEN_LEN 位，内容不显示）"

# ── 2. 验证 token 有效性 ──
blue "【2/5】验证 token 是否有效…"
API="https://api.github.com"
AUTH="Authorization: Bearer $TOKEN"

VERIFY="$(curl -s -H "$AUTH" -H "Accept: application/vnd.github+json" "$API/user" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('login','FAIL'))" 2>/dev/null || echo FAIL)"

if [[ "$VERIFY" != "$GITHUB_USER" ]]; then
  red "✗ token 验证失败（返回：$VERIFY）"
  red "  可能是复制不全、已过期，或权限没给对。"
  exit 1
fi
green "✓ token 有效，身份：$VERIFY"

# ── 3. 建仓库（已存在则跳过）──
blue "【3/5】创建仓库 $GITHUB_USER/$REPO_NAME…"
EXIST="$(curl -s -H "$AUTH" "$API/repos/$GITHUB_USER/$REPO_NAME" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print('YES' if d.get('id') else 'NO')" 2>/dev/null || echo NO)"

if [[ "$EXIST" == "YES" ]]; then
  green "✓ 仓库已存在，跳过创建"
else
  CREATE="$(curl -s -X POST -H "$AUTH" -H "Accept: application/vnd.github+json" \
    -H "Content-Type: application/json" \
    -d "{\"name\":\"$REPO_NAME\",\"description\":\"挂机收益雷达：自动扫描 GitHub 赏金、识别虚假赏金、生成数字产品选题\",\"private\":false,\"auto_init\":false}" \
    "$API/user/repos")"
  RESULT="$(echo "$CREATE" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('full_name') or d.get('message','FAIL'))" 2>/dev/null || echo FAIL)"
  if [[ "$RESULT" == "$GITHUB_USER/$REPO_NAME" ]]; then
    green "✓ 仓库创建成功：$RESULT"
  else
    red "✗ 创建失败：$RESULT"
    exit 1
  fi
fi

# ── 4. 提交并推送代码 ──
blue "【4/5】上传代码到仓库…"
git config user.name  "houxixi"
git config user.email "$(git config user.email 2>/dev/null || echo 'zd79tc46zs-web@users.noreply.github.com')"

if [[ ! -d ".git" ]]; then
  git init -q
  git branch -M main
fi

# 先确保 .token 不会被提交
git add -A
if git diff --staged --name-only | grep -q "^\.token$"; then
  git reset -q HEAD .token 2>/dev/null || true
  red "  （已阻止 .token 进入提交）"
fi

git add -A
git commit -q -m "feat: 挂机收益雷达 v1

- radar/scan.py：赏金扫描 + 反作弊判据 + 结算通道判定 + 自动适配度评分
- radar/hunter.py：认领/克隆/出补丁执行器（默认 dry-run + outbox 人工核对）
- store/publish.py：数字产品自动生成与上架（Creem，默认演练模式）
- .github/workflows/radar.yml：每 3 小时定时扫描 + 自动开 Issue 提醒
- docs/：Mac 部署教程、收款通道可行性、GitHub 权限指南"

# 用 token 做认证推送（token 不写进 remote url）
REMOTE="https://github.com/$GITHUB_USER/$REPO_NAME.git"
git remote remove origin 2>/dev/null || true

# 通过临时 credential helper 使用 token，命令结束后即失效
cat > /tmp/.gh_helper_$$ << 'HELPER'
#!/bin/bash
echo "username=x-access-token"
echo "password=$GH_TOKEN_VALUE"
HELPER
chmod +x /tmp/.gh_helper_$$
export GH_TOKEN_VALUE="$TOKEN"
export GIT_ASKPASS=/tmp/.gh_helper_$$

PUSH_OUT="$(git push -u "$REMOTE" main 2>&1)" || true
unset GH_TOKEN_VALUE GIT_ASKPASS
rm -f /tmp/.gh_helper_$$

if echo "$PUSH_OUT" | grep -qi "error\|denied\|fatal"; then
  red "✗ 推送失败："
  echo "$PUSH_OUT" | head -10 | sed 's/^/    /'
  exit 1
fi
git remote add origin "$REMOTE" 2>/dev/null || git remote set-url origin "$REMOTE"
green "✓ 代码已推送"

# ── 5. 配置 Actions 密钥（RSA 公钥加密）──
blue "【5/5】配置 GitHub Actions 密钥…"

# 5.1 取仓库公钥
PUBKEY_JSON="$(curl -s -H "$AUTH" -H "Accept: application/vnd.github+json" \
  "$API/repos/$GITHUB_USER/$REPO_NAME/actions/secrets/public-key")"

PUBKEY="$(echo "$PUBKEY_JSON" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('key',''))" 2>/dev/null || echo "")"
KEY_ID="$(echo "$PUBKEY_JSON" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('key_id',''))" 2>/dev/null || echo "")"

if [[ -z "$PUBKEY" || -z "$KEY_ID" ]]; then
  red "✗ 未能获取仓库公钥，自动配置跳过"
  red "  请手动配置：仓库 → Settings → Secrets and variables → Actions → New repository secret"
  red "  Name 填 GITHUB_TOKEN，Value 粘贴你的 token"
else
  # 5.2 用公钥加密 token
  ENC_FILE="$(mktemp)"
  printf '%s' "$TOKEN" > "$ENC_FILE"
  ENCRYPTED="$(openssl pkeyutl -encrypt -pubin -inkey <(printf '%s\n' "$PUBKEY") \
    -in "$ENC_FILE" -outform DER 2>/dev/null | base64 -w0 2>/dev/null || \
    openssl pkeyutl -encrypt -pubin -inkey <(printf '%s\n' "$PUBKEY") \
    -in "$ENC_FILE" -outform DER 2>/dev/null | base64)"
  rm -f "$ENC_FILE"

  if [[ -z "$ENCRYPTED" ]]; then
    red "✗ 加密失败，自动配置跳过"
    red "  请手动配置：仓库 → Settings → Secrets and variables → Actions → New repository secret"
    red "  Name 填 GITHUB_TOKEN，Value 粘贴你的 token"
  else
    # 5.3 写入密钥
    BODY="$(python3 -c "
import json,sys
print(json.dumps({'encrypted_value':sys.argv[1],'key_id':sys.argv[2]}))
" "$ENCRYPTED" "$KEY_ID")"

    PUT_OUT="$(curl -s -H "$AUTH" -H "Accept: application/vnd.github+json" \
      -H "Content-Type: application/json" -X PUT \
      "$API/repos/$GITHUB_USER/$REPO_NAME/actions/secrets/GITHUB_TOKEN" \
      -d "$BODY")"

    if [[ -z "$PUT_OUT" ]] || echo "$PUT_OUT" | grep -qi '"message"'; then
      red "✗ 密钥写入失败：$(echo "$PUT_OUT" | head -c 200)"
      red "  请手动配置：仓库 → Settings → Secrets and variables → Actions → New repository secret"
      red "  Name 填 GITHUB_TOKEN，Value 粘贴你的 token"
    else
      green "✓ 密钥 GITHUB_TOKEN 已加密写入（内容不落盘于仓库）"
    fi
  fi
fi

# 清理
unset TOKEN

echo ""
green "════════════════════════════════════════"
green " ✅ 部署完成"
green "════════════════════════════════════════"
echo ""
echo "仓库地址：https://github.com/$GITHUB_USER/$REPO_NAME"
echo ""
echo "接下来做这一步（开启挂机）："
echo "  1. 浏览器打开上面那个网址"
echo "  2. 点顶部的 Actions 标签"
echo "  3. 左边选「挂机收益雷达」"
echo "  4. 右边点 Run workflow，等 2 分钟"
echo ""
echo "本地也能看报告："
echo "  cd ~/Desktop/github-earning && open reports/latest.md"
