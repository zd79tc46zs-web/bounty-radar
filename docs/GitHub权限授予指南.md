# 让 WorkBuddy 读写你的 GitHub

> 现状：**已经连上了，但只有读权限**。下面说明为什么、怎么升级。

---

## 一、当前状态（已实测）

WorkBuddy 的 GitHub 连接器显示 `connected`，我已成功用它：

| 能力 | 状态 | 验证方式 |
|---|---|---|
| 读取你的账号信息 | ✅ | 返回 `zd79tc46zs-web`，注册于 2026-10-07 |
| 搜索 issue / 仓库 | ✅ | 成功扫到 943 条带标价的真实赏金 |
| 读取文件内容 | ✅ | 成功读取仓库源码 |
| **创建仓库** | ❌ | 返回 `403 Resource not accessible by integration` |
| **Fork 仓库** | ❌ | 同上 403 |
| **提交文件 / 开 PR** | ❌ | 同上 403 |

**原因**：WorkBuddy 用的不是你的个人密码，而是一个 **GitHub App 安装令牌**。
App 安装时被限定了权限范围（只读），所以它能"看"但不能"写"。
这是 GitHub 的正常安全设计——但也意味着**光靠这个连接器，我无法替你建仓、推代码、开 PR**。

---

## 二、三个方案，按推荐度排序

### 方案 1：给连接器加权限（最省事，推荐先试）

1. 打开 <https://github.com/settings/installations> → 找到 WorkBuddy（或名称含 WorkBuddy/腾讯 的那个 App）
2. 点 **Configure** → 选 **Only select repositories** → 勾选你要操作的仓库
3. 同一页面下方 **Repository permissions** 里，把需要的那几项改成 **Read and write**：
   - `Contents`（推文件）
   - `Pull requests`（开 PR）
   - `Issues`（评论 issue）
   - `Actions`（跑工作流）
   - `Administration`（**勾上这个才能建仓库**）
4. 保存

**完成后回到对话说一句"权限已开，再试一次"**，我立刻重新验证。

### 方案 2：配置官方 GitHub MCP Server（功能最全）

WorkBuddy 支持自定义 MCP。官方 `github-mcp-server` 用 PAT 授权，权限完全由你控制。

**第一步：生成 PAT**

打开 <https://github.com/settings/personal-access-tokens/new>：

- Fine-grained token → Generate new token
- Token name：`workbuddy`
- Expiration：90 days（或更长）
- **Repository access**：Only select repositories → 勾选你的仓库
- **Repository permissions**：
  - Contents → **Read and write**
  - Pull requests → **Read and write**
  - Issues → **Read and write**
  - Actions → **Read and write**
  - Administration → **Read and write**
  - Metadata → Read-only（必选）
- Generate token → 复制（**只显示一次**）

**第二步：写入 MCP 配置**

配置文件是 `~/.workbuddy/mcp.json`（注意是 `mcp.json`，**不是** `.mcp.json`）：

```json
{
  "mcpServers": {
    "github": {
      "command": "docker",
      "args": [
        "run", "-i", "--rm",
        "-e", "GITHUB_PERSONAL_ACCESS_TOKEN",
        "ghcr.io/github/github-mcp-server"
      ],
      "env": {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "ghp_你的token"
      }
    }
  }
}
```

**没有 Docker？** 用远程 HTTP 版（无需本地环境）：

```json
{
  "mcpServers": {
    "github": {
      "type": "http",
      "url": "https://api.githubcopilot.com/mcp/",
      "headers": {
        "Authorization": "Bearer ghp_你的token"
      }
    }
  }
}
```

**第三步：启用**

配置写完后，打开 WorkBuddy 的连接器管理页 → 右上角自定义连接器入口 → 对新的 server 点 **Trust（信任）**。

> ⚠️ 注意：自定义 MCP 不会自动生效，必须在连接器管理页手动点信任。
> 另外不要用 `mcpServers` 之外的字段名，官方文档里写的是 `servers`，但多数 Host 需要 `mcpServers`；
> 如果你的 Host 报错，改一下键名即可。

### 方案 3：本地装 gh CLI（补齐建仓/推送能力）

```bash
brew install gh          # macOS
gh auth login           # 浏览器授权，PAT 或 OAuth 均可
gh auth status          # 验证
```

装完后我就能用 `gh` 在你本地建仓、推代码、开 PR，不依赖 WorkBuddy 的 App 权限。

---

## 三、安全建议

1. **不要把 PAT 直接发在对话里**。写进 `~/.workbuddy/mcp.json`（该文件加进 `.gitignore`），或用环境变量。
2. **用 Fine-grained token + 只勾选必要仓库**，不要给全账号 `repo` 权限。
3. **设短过期时间**（90 天），到期前重新生成。
4. **密码、2FA 验证码、私钥一律不要交给 AI**。平台账号的登录与授权请你自己在官方页面完成。
5. 官方文档建议的最小 scope 是 `repo` + `read:packages` + `read:org`，但那是通用建议；
   实际按你启用的工具集给，遵循最小权限原则。

---

## 四、验证权限是否生效

授权后对我说一句"验证一下 GitHub 权限"，我会实测三件事：

1. 调 `get_me` 确认身份
2. 尝试建一个测试仓库
3. 尝试推一个文件

三步都过 = 写权限已通。
