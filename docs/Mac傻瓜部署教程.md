# MacBook Air 傻瓜部署教程（从零开始）

**这份教程假设你从没见过命令行。** 每一步都写清楚：点哪里、敲什么、看到什么算成功。

全程约 30 分钟，不花钱。

---

## 第 0 步：打开终端（1 分钟）

**这是唯一一个需要你动手找的东西，后面全靠它。**

1. 按键盘上的 `Command` 键（⌘，就是空格键左下角那个），**不放开**
2. 同时按 `空格` 键
3. 屏幕上会弹出一个搜索框（Spotlight 搜索）
4. 输入两个字：**终端**
5. 屏幕上出现"终端"这个黑色图标，点击它

**成功标志**：屏幕上出现一个黑色窗口，左上角有一行字，像这样：

```
Last login: Sun Nov  1 13:30:00 on ttys000
houxixi@MacBook-Air ~ %
```

看到 `%` 或 `$` 结尾就对了。这个窗口就是"终端"。

> 找不到终端？试试：打开 Finder → 应用程序 → 实用工具 → 终端，双击。

---

## 第 1 步：解压这个项目到你的电脑（3 分钟）

**这一步完全不用终端，只用鼠标。**

项目我打成了一个 zip 包，你只需要解压。

1. 打开 Mac 的 **Finder**（访达）—— Dock 栏左边第一个笑脸图标，或按 `Command+空格` 打字 "访达"
2. 点左边栏的 **下载**
3. 找到 `github-earning.zip`，**双击**它
4. Mac 会自动解压出一个 `github-earning` 文件夹
5. 把这个文件夹**拖到桌面上**（拖到 Finder 窗口的空白处松手即可）

> **为什么用 zip 而不是直接拖文件夹？**
> 因为挂机的核心文件 `.github/workflows/radar.yml` 藏在以点开头的隐藏目录里。
> Finder 默认不显示隐藏文件，直接拖很容易漏掉它——漏了就没有定时任务了。
> zip 解压会完整保留它。

**怎么确认解压成功而且文件完整？** 在终端粘贴（复制下面这行，粘贴进去，回车）：

```bash
ls ~/Desktop/github-earning/.github/workflows/
```

**成功标志**：屏幕上出现一行

```
radar.yml
```

看到 `radar.yml` 就说明隐藏文件也完整带过来了。**如果什么都没显示**，说明少了隐藏目录，
按 `Command+Shift+.`（句号）可以切换显示隐藏文件，再检查一遍。

> 如果你不想放桌面，跳过拖动那一步也行——只要记住项目文件夹在哪，
> 后面命令里的路径改成实际位置即可。

---

## 第 2 步：检查 Python 装没装（1 分钟）

在终端里粘贴这行，回车：

```bash
python3 --version
```

**成功标志**：屏幕上出现类似

```
Python 3.9.6
```

只要有 `Python 3.` 开头的字就行，**版本号不用管**（3.9 到 3.13 都能跑这套代码，我验证过）。

**如果显示 `command not found`**，粘贴这行：

```bash
xcode-select --install
```

然后按回车，弹出的窗口点"安装"，等它跑完（大约 1–3 分钟），再重新执行 `python3 --version`。

---

## 第 3 步：让电脑能访问 GitHub（2 分钟）

**为什么要这步**：GitHub 在国内有时访问不稳定，如果后面扫描报网络错误，就是这里没弄好。

在终端粘贴这行，回车：

```bash
curl -s https://api.github.com/rate_limit | head -5
```

**情况 A**：屏幕上出现一堆 JSON，里面能看到 `"limit": 60` 之类的东西
→ ✅ **网络通了，跳过第 3 步，直接看第 4 步**

**情况 B**：屏幕上出现 `API rate limit exceeded` 或 `Could not resolve host` 或干脆空白
→ 需要配代理，继续往下：

**情况 B 的解决办法**：

如果你电脑上装了代理软件（Clash / Surge / V2Ray / 小火箭之类），它的本地端口通常是 `7890` 或 `1080`。
在终端粘贴（把 `7890` 换成你代理软件里显示的端口）：

```bash
export http_proxy=http://127.0.0.1:7890
export https_proxy=http://127.0.0.1:7890
```

然后再跑一次检测：

```bash
curl -s https://api.github.com/rate_limit | head -5
```

> **注意**：这个代理设置**只在这个终端窗口有效**，关掉窗口就没了。
> 这是故意的——不想让你的电脑其他软件莫名其妙走代理。
> 如果你想永久设置，去 <https://www.workbuddy.cn/docs/workbuddy/Overview> 不需要；
> 只需要每次开新终端时重敲这两行，或者用教程第 8 步给的永久写法。

---

## 第 4 步：在本地跑一次扫描，看看能扫出什么（3 分钟）

在终端粘贴这行，回车：

```bash
cd ~/Desktop/github-earning && python3 radar/scan.py
```

**它会做什么**（大概 2 分钟，屏幕上会滚动显示进度）：

```
[radar] 抓取 GitHub 赏金…
[radar] 命中 110 条候选
[radar] 抓取真实付费赏金池…
[radar] 赏金池 79 条
[radar] 抓取 Opire 平台…
[radar] Opire 3 条
[radar] 抓取需求信号…
[radar] 信号 30 条
[radar] 报告已写入 reports/latest.md
```

**成功标志**：最后一行出现 `报告已写入 reports/latest.md`。

**如果报 `API rate limit exceeded`**：正常现象，未登录每小时只能查 60 次。
等一小时，或者做第 6 步拿到 token 后再跑（配额涨到 5000 次/小时）。

**跑完后看看结果**：

```bash
open reports/latest.md
```

这会用系统默认的"文本编辑"打开报告。里面有三块内容：
- **一、高价值赏金候选** —— 扫到的赏金，按可信度排序
- **二、真实付费赏金池** —— 实测确认真付过款的仓库，**★重点看这块**
- **四、需求信号** —— 真实开发者的需求，这些是自建产品的选题

---

## 第 5 步：先在本地跑通"认领"流程（可选，2 分钟）

扫描出来只是看看，真正干活是这个。**先看会发生什么，不真发出去**：

```bash
python3 radar/hunter.py --scan --limit 5
```

**成功标志**：列出 5 条目标，每条长这样：

```
  [  50.0] $  300.0 |    240分钟 | 0x4007/os.ubq.fi
          Design tokens and theme polish
          https://github.com/0x4007/os.ubq.fi/issues/20
          判据: 金额 $300；仅 3 条评论；🤖 标注 4 小时内可完成
```

---

## 第 6 步：建 GitHub 仓库，让它自己在云端挂机（8 分钟）

**到这一步才真正开始"挂机"。** 前面都是本地试跑。

### 6.1 生成一个 Token（浏览器操作，3 分钟）

1. 浏览器打开这个地址：<https://github.com/settings/personal-access-tokens/new>
2. 如果要求登录，用你的 GitHub 账号登录
3. 按下面填：

| 填哪里 | 填什么 |
|---|---|
| Token name | `radar` |
| Expiration | 90 days |
| Repository access | 选 **Only select repositories** |
| Resource owner | 你的账号 |

4. **往下滚到 Repository permissions**，按下面设置：

| 权限项 | 设成 |
|---|---|
| Contents | **Read and write** |
| Issues | **Read and write** |
| Pull requests | **Read and write** |
| Actions | **Read and write** |
| **Workflows** | **Read and write** |
| **Secrets** | **Read and write** |
| Metadata | Read-only（默认就行） |

5. 滚到最下面点 **Generate token**
6. 页面上会出现一串以 `github_pat_` 开头的字符

**⚠️ 极其重要**：这串字符**只显示这一次**，关掉页面就再也看不到了。

7. 立刻把它复制下来。做法：点旁边的复制图标，然后打开"文本编辑"（TextEdit）粘贴保存。

> **安全提醒**：这串东西等同于你 GitHub 账号的钥匙。不要发给我、不要贴到聊天群里、不要写在别人能看到的纸上。

### 6.2 存到文件里（终端操作，2 分钟）

在终端粘贴（把 `xxx` 换成你复制的 token）：

```bash
cd ~/Desktop/github-earning && echo "github_pat_你的完整token" > .token && chmod 600 .token && echo "✅ 已保存"
```

> 说明：`.token` 开头有个点是**隐藏文件**的意思，`ls` 看不到它，这是对的。
> `chmod 600` 是设置权限，只有你能读写。

**验证一下存对了**（不会显示完整 token，只显示前 8 位）：

```bash
head -c 8 .token && echo " ...（后面省略）"
```

看到 `github_pat` 开头就对了。

### 6.3 用 token 跑一次带认证的扫描（1 分钟）

```bash
export GITHUB_TOKEN=$(cat .token) && python3 radar/scan.py
```

这次应该不会报限流了。

### 6.4 建仓库并传上去（2 分钟）

先在浏览器建一个空仓库：

1. 打开 <https://github.com/new>
2. Repository name 填 `bounty-radar`
3. **Public**（公开）—— 必须选这个，公开仓库的 Actions 免费额度无限
4. **不要勾** "Add a README file"
5. 点 **Create repository**

然后回终端，粘贴（把 `你的用户名` 换成你的 GitHub 用户名，在 <https://github.com> 右上角头像里能看到）：

```bash
cd ~/Desktop/github-earning && git init && git add -A && git commit -m "init: 挂机收益雷达"
```

接着（下面这行的 `你的用户名` 也要换）：

```bash
git remote add origin https://github.com/你的用户名/bounty-radar.git && git push -u origin main
```

**可能会问你要密码**：
- 如果弹的是 GitHub 账号密码：填账号，密码位置**粘贴那个 token**
- 如果弹的是用户名密码 + 2FA：说明 token 权限不够或者没生效，回 6.1 检查

**成功标志**：看到类似

```
To https://github.com/你的用户名/bounty-radar.git
 * [new branch]      main -> main
```

### 6.5 把 token 存进 GitHub 密钥（浏览器，2 分钟）

这样云端跑的时候就不用每次手动设环境变量了。

1. 打开你的仓库：<https://github.com/你的用户名/bounty-radar>
2. 点顶部的 **Settings** 标签
3. 左边菜单找 **Secrets and variables** → 点 **Actions**
4. 点绿色按钮 **New repository secret**
5. 填：
   - Name: `GITHUB_TOKEN`
   - Secret: 粘贴你的 token
6. 点 **Add secret**

### 6.6 开启挂机（1 分钟）

1. 回到仓库页面，点顶部 **Actions** 标签
2. 左边菜单选 **挂机收益雷达**
3. 右边点 **Run workflow** 按钮
4. 等 2 分钟

**成功标志**：这次运行显示绿色对勾 ✅，点进去能看到 5 个步骤全部绿色。

**从这一刻起就是挂机了**：

`.github/workflows/radar.yml` 里写的是

```yaml
cron: '0 3,9,15,21 * * *'
```

意思是**每 3 小时自动跑一次**，GitHub 的服务器替你干活，**你的电脑可以关机**。每次运行会：
- 扫描全网赏金
- 把结果写成报告提交到仓库
- 自动开一个 Issue 提醒你

---

## 第 7 步：让手机/电脑收到提醒（可选）

### 方法 A：订阅仓库的 Issue（最简单）

1. 打开你的仓库页面
2. 右上角找到 **Watch** 按钮 → 点它 → 选 **Custom** → 只勾 **Issues** → 确定

这样雷达每次开提醒 Issue，你的邮箱就会收到通知。

### 方法 B：微信/企业微信推送（需要一点配置）

1. 仓库 → Settings → Secrets and variables → Actions → New repository secret
2. Name: `WECHAT_WEBHOOK`，Secret 填你的机器人 Webhook 地址
3. 在 `radar.yml` 末尾加一段推送代码

（这一步我可以在你确认后帮你改，不着急）

---

## 第 8 步：想要永久有效，不用每次重敲代理（可选）

第 3 步的代理设置关掉终端就失效。如果你希望永久生效：

```bash
echo 'export http_proxy=http://127.0.0.1:7890' >> ~/.zshrc
echo 'export https_proxy=http://127.0.0.1:7890' >> ~/.zshrc
source ~/.zshrc
```

> 端口 `7890` 换成你代理软件实际的端口。
> 好处是以后开终端自动生效；坏处是所有命令行工具都走代理，可能拖慢某些国内网站的操作。
> **我的建议是先用第 3 步的临时方式，不着急搞永久的。**

---

## 第 9 步：真正收钱的路（这部分需要你自己操作，我做不了）

**必须先说清楚**：前 8 步做完，你得到的是"信息自动化"——知道哪里有活、哪些是坑。
**钱能不能到手，取决于收款通道。** 这一步必须你本人亲自去开通。

### 为什么不能靠抢赏金赚钱

主流赏金平台（Algora、Polar）全部通过 Stripe 结算，而 **Stripe 不支持中国大陆个人开户**。
官方 issue #321 就记录了香港用户被身份验证拦截的真实案例。
Ubiquity 用 UBQ 稳定币结算，链上出入金在大陆有合规风险。

**结论**：赏金就算真付了，你也提不出来。所以要走自建产品 + 能提现的通道。

### 推荐的通道：Creem

| 项目 | 数据 |
|---|---|
| 大陆个人 | ✅ 支持，提现到**支付宝** |
| 费率 | 3.9% + $0.40/笔，无月费 |
| 税务 | 平台代缴全球 VAT/GST/销售税（MoR 模式） |
| 提现门槛 | 满 $50 |
| 提现周期 | 每月 1 号、15 号 |
| 审核 | 1–2 个工作日 |

### 开通流程

1. 注册 <https://www.creem.io>
2. **按这个清单准备齐再提交**（缺一项就会被拒）：

| 准备什么 | 具体要求 |
|---|---|
| 域名 | 一个真实域名，约 $10/年 |
| 落地页 | 能看到：产品介绍、**价格**、买完得到什么 |
| 隐私政策 | 写清哪些数据本地处理、哪些上传云端 |
| 退款规则 | 结账页显眼位置写明，一键取消入口 |
| 服务条款 | 单独一页 |
| 客服邮箱 | **必须用域名邮箱**，且与隐私政策里写的邮箱一致 |

3. 创建产品 → 填名称、描述、价格
4. 提现方式选 **Alipay**，受益人姓名必须和验证时填的完全一致

### 货架上的货从哪来

第 4 步报告里的**第四部分「需求信号」**就是选题来源——那是真实开发者在 GitHub 上
公开抱怨的需求。把其中一个做成解决方案（文档 + 脚本 + 模板），就是能卖的产品。

用这条命令自动生成产品定义骨架：

```bash
python3 store/publish.py --limit 8 --price 2900
```

输出示例：

```
从需求信号中提炼 8 个选题：
  · [Feature] HR页应该也能批量创建任务
    来源：pt-plugins/PT-depiler
已生成 8 个产品定义到 store/products/
=== 演练模式（未真实上架）===
  [产品] [Feature] HR页应该也能批量创建任务
          定价 $29.00 | slug=feature-hr
```

生成的 JSON 在 `store/products/` 里，**直接用文本编辑打开改**。
改完真正上架：

```bash
export CREEM_API_KEY=你的creem密钥 && python3 store/publish.py --limit 8 --price 2900 --publish
```

> **它默认是演练模式**（不真上架）。这是故意的——自动生成的描述只是骨架，
> 直接上架卖不动，商品文案必须你自己打磨。

---

## 一键自检（做完跑一次，确认全通）

```bash
cd ~/Desktop/github-earning && python3 radar/scan.py && python3 radar/hunter.py --scan --limit 3 && python3 store/publish.py --limit 3 && echo "✅✅✅ 全链路正常 ✅✅✅"
```

三段都有输出、最后看到 `全链路正常` = 部署成功。

**如果这一步失败了，多半不是坏了，是 API 限流。** 未登录时 GitHub 每小时只给 60 次调用，
连跑几轮扫描很容易撞上。判断方法：失败时屏幕上如果有 `API rate limit exceeded` 字样，
等一小时再跑，或者做第 6 步拿到 token（配额涨到 5000 次/小时）后再跑。

分步验证（想看清每一段都干了什么，就用这个）：

```bash
cd ~/Desktop/github-earning
python3 radar/scan.py              # 扫网络，看最后有没有"报告已写入"
python3 radar/hunter.py --scan --limit 3   # 看可认领目标
python3 store/publish.py --limit 3  # 生成产品定义（演练）
```

---

## 常见问题

**Q：终端里粘贴命令，粘贴了但没反应？**
A：Mac 终端首次粘贴要按 `Command+V`（不是 Ctrl+V）。如果连 `Command+V` 都不行，
点终端菜单栏的 **Edit → Paste**。

**Q：`cd: no such file or directory`？**
A：项目没在下载文件夹。用这条找一下：
```bash
find ~/Desktop ~/Downloads -maxdepth 2 -name "github-earning" 2>/dev/null
```
找到后 `cd` 到输出的那个路径。

**Q：`git: command not found`？**
A：运行 `xcode-select --install`，装完重试。

**Q：推送时提示 `Authentication failed`？**
A：密码位置要粘 token，不是账号密码。或者先配好凭据助手：
```bash
git config --global credential.helper osxkeychain
```
然后重跑 `git push -u origin main`，再输一次 token，它会记住。

**Q：Actions 报 `Resource not accessible by integration`？**
A：仓库权限设置问题。仓库 → Settings → Actions → General → Workflow permissions →
选 **Read and write permissions**。

**Q：报告里全是"⛔ 大陆不可收款"，是不是白做了？**
A：没白做。这正是真实情况——它帮你**提前避坑**。同时报告第四部分给了你能收钱的选题。
真正收钱走第 9 步的自建产品路线。

**Q：真的能完全不管吗？**
A：扫描、报告、提醒、自动上架都自动了。但**内容质量要你把关**——
自动生成的商品描述是骨架，直接上架卖不动。合理分工：机器跑流水线，你做选题和文案。

**Q：多久能看到钱？**
A：实话实说：不确定，可能很久。挂机系统解决"信息和流程"，不解决"需求和信任"。
建议先用第 9 步验证第一笔（哪怕 $9），再决定要不要放大投入。

---

## 三十秒速查表

| 目的 | 命令 |
|---|---|
| 打开终端 | `⌘` + `空格` → 输入"终端" → 回车 |
| 进项目目录 | `cd ~/Desktop/github-earning` |
| 跑扫描 | `python3 radar/scan.py` |
| 看报告 | `open reports/latest.md` |
| 看可认领目标 | `python3 radar/hunter.py --scan --limit 5` |
| 生成产品定义 | `python3 store/publish.py --limit 8` |
| 带认证跑 | `export GITHUB_TOKEN=$(cat .token) && python3 radar/scan.py` |
| 全链路自检 | `python3 radar/scan.py && python3 radar/hunter.py --scan --limit 3 && python3 store/publish.py --limit 3 && echo "✅ 全链路正常"` |
