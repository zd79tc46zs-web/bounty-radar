# Creem 收款开通 · 傻瓜式操作步骤（Mac）

> **重要前提（先看，能省你几天）**
>
> ① **Creem 被拒审后不会重新审核。** 有开发者实测被拒后想改再提，直接没戏。
> 　所以务必按本教程把 6 项材料准备齐再提交。
> ② **客服邮箱必须是域名邮箱**（如 support@你的域名.com）。用 QQ 邮箱 / Gmail / 临时邮箱
> 　**大概率直接被拒**。这是最常见的拒审原因。
> ③ **不要放假的用户评价。** 有开发者因页面用了"不可核实的通用身份"评价被原样打回。
> 　产品页在拿到真实反馈前，宁可一个评价都不放。
> ④ 一个 Creem 账号 = 一个店铺 = 一个网站。品牌隔离要另开账号重新过 KYC。
> ⑤ 审核通常 **1–2 个工作日**。

---

## 总览：6 项材料 + 4 个操作阶段

```
阶段一 备料（约30分钟）    ①域名 ②落地页 ③隐私政策 ④退款规则 ⑤服务条款 ⑥域名邮箱
   ↓
阶段二 上线（约10分钟）    把页面发布到 GitHub Pages → 得到 https://你的域名.com
   ↓
阶段三 开店（约20分钟）    注册 Creem → 填资料 → 传身份证 → 绑支付宝提现 → 等审核
   ↓
阶段四 上架（约10分钟）    创建产品 → 填 Checkout 链接回落地页 → 走一遍测试支付
```

---

# 阶段一：备料

## ① 域名（$9–12/年）

**推荐 Cloudflare Registrar**——按成本价卖，**不赚你差价**，且自带免费 DNS、CDN、自动 HTTPS、WHOIS 隐私保护。

**操作**：

1. 打开 <https://dash.cloudflare.com/sign-up> → 注册账号（用邮箱）
2. 登录后进 Dashboard → 左侧 **Domain Registrar** → **Register Domains**
3. 搜索想要的域名，建议：
   - 后缀选 **.com**（信任度高，评审看着专业）；实验性项目可用便宜后缀
   - 不要用连字符、不要数字开头
4. 填 **Registrant Contact**（注册人信息）——用真实信息，ICANN 要求
5. 勾选 **Auto Renew**（自动续费）→ 付款（支持信用卡）
6. 拿到域名后，**在 Cloudflare 左侧 Websites 点 "Add a site"，把域名添加进去**
   （这一步是把 DNS 托管到 Cloudflare，Email Routing 依赖它）

> **国内买域名行不行？** 阿里云/腾讯云也可以，但**不能**用它们做 Creem 的托管邮箱（要另配），
> 且如果网站要放在境内服务器还需备案。走 Cloudflare 全套最省事。

## ② 落地页（产品介绍 + 价格 + 买完得到什么）

**我已经给你做好了成品**，包含 Creem 审核要求的全部要素：产品介绍、清晰价格、交付内容清单、
退款政策入口、隐私政策入口、服务条款入口、客服邮箱。

文件位置：`~/Desktop/github-earning/store/site/index.html`

**你需要做的**（第 3 步会详说）：改 3 个地方——品牌名、客服邮箱、Creem 购买链接。

**页面已包含的审核要素**（对照检查）：

| 审核关注点 | 页面哪里有 |
|---|---|
| 产品介绍 | 首屏大标题 + 副标题 + 「产品包含什么」六张卡 |
| **价格** | 「价格」区块，$29 醒目大字 |
| 买完得到什么 | **交付清单表格**（文件/格式/说明三列，逐项列出） |
| 退款规则 | 独立区块 + 独立页面 refund.html |
| 隐私政策 | 独立区块 + 独立页面 privacy.html |
| 服务条款 | 独立区块 + 独立页面 terms.html |
| 客服邮箱 | 页脚 + 各页面联系方式 |

## ③ 隐私政策 / ④ 退款规则 / ⑤ 服务条款

**也都做好了**，各自独立成一个 HTML 文件（审核有时会单独检查这几个 URL）：

| 文件 | 对应 URL（发布后） |
|---|---|
| `privacy.html` | `https://你的域名.com/privacy.html` |
| `refund.html` | `https://你的域名.com/refund.html` |
| `terms.html` | `https://你的域名.com/terms.html` |

**已按审核要求写好的关键点**：

- **隐私政策**：写清哪些数据本地处理、哪些上传云端；明确「支付信息由 Creem 处理，我们不接触卡号」；
  说明留存期限与删除权；声明不出售不出租不共享；说明未成年人条款。
- **退款规则**：14 天 + 下载不超过 3 次可全额退；3 个工作日内回复；5–10 个工作日到账；
  明确列出不予退款情形。**关键是给了可量化的判定标准**（不因"用不上"这种主观理由拒退）——
  这正是避免审核时被认为"退款政策缺失或不合理"的关键。
- **服务条款**：许可授予范围（含公开课/教研分享）、知识产权、**免责说明**
  （明确工具输出不构成对教学结果或产业标准的权威认定）、适用法律与争议解决。

## ⑥ 客服邮箱（**最关键，最容易卡住**）

**必须是域名邮箱。** 方案：Cloudflare Email Routing 免费转发。

**操作**：

1. Cloudflare Dashboard → 左侧 **Email** → **Email Routing** → **Get started**
2. 选 **Add records and enable Email Routing** → 按提示添加 MX 和 TXT 记录
   （DNS 在 Cloudflare 托管，点 "Add records automatically" 最省事）
3. **添加转发规则**：
   - 自定义地址：`support`（或 `hello`、`contact`）
   - 目的地：填你**常用的真实邮箱**（Gmail / QQ 邮箱都行）
   - 打开 **Email Routing for custom addresses** 的开关
4. Cloudflare 会发一封确认邮件到你的常用邮箱 → **点里面的确认链接**
5. 现在 `support@你的域名.com` 就能收信了，而且**收信显示你的域名后缀**

> ⚠️ **注意**：
> - **Cloudflare Email Routing 是"转发"不是"邮箱"**——你在 Creem 后台填 `support@你的域名.com`，
>   客户邮件会转发到你的常用邮箱，你用常用邮箱回复即可。**Creem 要求的正是"网站和收据上展示可达的品牌客服邮箱"**，
>   转发完全满足。
> - 不需要发信功能。如果你要给客户发通知邮件，用 Resend 免费档（每月约 3000 封）。
> - **务必在 3 个工作日内回复用户请求**——Creem 官方说明：逾期未回复时，Creem 可代为退款。

---

# 阶段二：把页面发布上线（约 10 分钟）

## 2.1 改配置（3 分钟）

打开这个文件：

```bash
open ~/Desktop/github-earning/store/site/site-config.json
```

用**文本编辑**打开后，改这三行（其余保持不动）：

```json
"brand_name": "你的品牌名",
"support_email": "support@你的域名.com",
"creem_checkout_url": "https://buy.creem.io/xxx"
```

- `creem_checkout_url` 现在还填不出来（要等第 4 步创建产品后才有链接），**先留着占位符**
- 改完保存

**然后运行**：

```bash
cd ~/Desktop/github-earning/store && /usr/bin/python3 apply_config.py
```

看到 `✅ 已应用配置到 N 个页面` 就对了。

## 2.2 自检（1 分钟）

```bash
cd ~/Desktop/github-earning/store && /usr/bin/python3 deploy_site.py
```

**期望输出**：

```
=== 占位符检查 ===
  ⚠️  index.html: 仍含「https://buy.creem.io/你的产品ID」→ Creem Checkout 链接
=== 必需页面检查 ===
  ✅ 落地页：index.html（18332 字节）
  ✅ 隐私政策：privacy.html
  ✅ 服务条款：terms.html
  ✅ 退款政策：refund.html
=== 审核要点自检 ===
  ✅ 价格可见
  ✅ 产品介绍
  ...
```

**只要 checkout 链接那一项还亮着，就可以发布了**——那个链接第 4 步才有。

## 2.3 发布（2 分钟）

```bash
cd ~/Desktop/github-earning/store && /usr/bin/python3 deploy_site.py --publish
```

它会用你的 token 把 4 个页面推到 GitHub 的 `gh-pages` 分支，并自动启用 Pages。

**成功输出**：

```
✅ 已推送到 gh-pages 分支（commit xxxxxxx）
Pages 更新：HTTP 201
📍 站点地址：https://zd79tc46zs-web.github.io/bounty-radar/
```

**等 1–3 分钟**，浏览器打开这个地址就能看到你的落地页。

## 2.4 绑定自定义域名（5 分钟）

GitHub Pages 默认地址是 `用户名.github.io/仓库名/`，**但 Creem 审核更认自己的域名**，
而且以后换仓库、改名都不用重配。强烈建议绑。

1. Cloudflare Dashboard → 左侧 **Websites** → 点你的域名 → **DNS** → **Records** → Add record
2. 加这 4 条：

| 类型 | 名称 | 内容 | 代理状态 |
|---|---|---|---|
| CNAME | `www` | `zd79tc46zs-web.github.io` | **Proxied（橙色云）** |
| A | `@` | `185.199.108.153` | Proxied |
| A | `@` | `185.199.109.153` | Proxied |
| A | `@` | `185.199.110.153` | Proxied |
| A | `@` | `185.199.111.153` | Proxied |

> 这 4 个 IP 是 GitHub Pages 的官方 IP。代理状态保持**橙色云朵（Proxied）**。

3. 打开你的 GitHub 仓库 → **Settings** → **Pages** → **Custom domain** 填
   `你的域名.com` → 勾 **Enforce HTTPS** → Save

4. **等 DNS 生效（10 分钟–24 小时）**。验证命令：

```bash
dig +short 你的域名.com
```

能返回 `185.199.108.153` 之类就说明解析好了。然后访问 `https://你的域名.com` 看是否出页面。

5. （可选）再加一条 CNAME 把 `www` 指到主域，并检查 SSL 证书已签发

---

# 阶段三：注册 Creem（约 20 分钟）

1. 打开 <https://www.creem.io/sign-in> → 注册账号
2. 登录后进 Dashboard，右侧会提示完成三件事：
   - 提交产品与业务资料（Business Details）
   - 完成身份验证（KYC）
   - 添加收款账户（Payout Account）
3. 点 **Set Up Payout Account** 依次走：

### 3.1 Business Details（业务资料）

按**当前真实情况**填，不要按未来计划填：

| 字段 | 怎么填 |
|---|---|
| 经营类型 | 个人（Individual）——你就是个人开发者 |
| 税务居民国家 | **China**（默认可能是 United States，**记得手动改**） |
| 产品是否已可公开销售 | 是（站点已上线，选 Yes） |
| 产品/品牌名称 | 填你的品牌名 |
| **联系邮箱** | **必须是 `support@你的域名.com`** ← 这项卡最多人 |
| 产品与平台说明 | 写你卖什么、交付什么、在哪个平台交付 |
| 是否已有付费客户 | 选 No（第一次做） |
| 官网是否展示用户数或评价 | **如实选**。没有评价就选 No，**不要放假评价** |
| 是否为 AI wrapper | 视实情选（你的产品是 AI 教学工具包，如实说明即可） |

### 3.2 身份验证（KYC）

会跳到 **Sumsub** 流程：

1. 填个人信息 → 上传身份证件（**正反面都传**）
2. **真人检测**：需要开摄像头。浏览器会弹权限提示 → 点地址栏左侧的图标 → 允许摄像头
3. **PEP 问卷**：问你是不是政治公众人物（politically exposed person）或有密切关联
   → **如实回答**。不是就选否

全部完成后返回 Dashboard，会显示"资料已验证"。

### 3.3 添加收款账户（支付宝提现）

1. Dashboard → **Balance** → 右侧 **Payout Account** → **Set Up**
2. 进 Paysway 页面：

| 选项 | 选什么 |
|---|---|
| Payout country | **China** |
| Currency | **CNY** |
| Transfer method | **Alipay** |

3. 填支付宝账号 + **受益人姓名**
   ⚠️ **受益人姓名必须和 KYC 验证时填的完全一致**（一个字都不能差），否则打款会失败
4. 提交后，账户出现在列表里；再回到 Creem **把账户关联到你的店铺**
5. 之后 Dashboard 选 **Business → Payout → Alipay**，填同样信息

---

# 阶段四：创建产品并回填链接（约 10 分钟）

## 4.1 先开测试模式（重要）

Dashboard → **Settings** → 打开 **Test Mode**。
这样先走一遍假支付流程，**不真扣钱**，确认结账页正常。

## 4.2 创建产品

1. Dashboard → **Products** → **Create Product**
2. 填：

| 字段 | 填什么 |
|---|---|
| Product name | 你的产品名（如「AI 教学资源生成工具包」） |
| Description | **完整描述**：包含什么、怎么用、给谁用（审核重点） |
| Price | 29（USD） |
| Product type | **Digital**（数字产品） |
| **Product cover** | 上传一张封面图（1000×1000 或 1200×630） |

3. **创建后立刻复制 Checkout 链接**：
   Products 列表 → 该产品右侧 **⋯** 菜单 → **Copy Payment Link**
   长得像 `https://buy.creem.io/xxxxxxxx`

## 4.3 把链接填回落地页

1. 编辑 `~/Desktop/github-earning/store/site/site-config.json`
2. 把 `"creem_checkout_url"` 改成刚复制的链接
3. 运行：

```bash
cd ~/Desktop/github-earning/store && /usr/bin/python3 apply_config.py && /usr/bin/python3 deploy_site.py --publish
```

看到 `✅ 购买按钮已启用` 就成了。

## 4.4 走一遍测试支付（必做）

1. 打开你站点的「立即购买」按钮
2. 页面顶部会显示 **Test Mode** 提示 → 说明不会真扣钱
3. 随便填邮箱、姓名、账单地址 + 测试卡号 `4242 4242 4242 4242`
4. 支付成功 → 回 Dashboard → **Payments** 里应该看到这条记录，状态 **Paid**
5. **同时点一次退款**（Dashboard → 该订单 → Refund），确认退款流程通
   > 这一步别省。有开发者上线后才发现 webhook 只处理发放、没处理退款，
   > 造成"额度已用掉但钱退回来"的白嫖漏洞。

## 4.5 提交审核

1. Dashboard → **Settings** → 关掉 Test Mode
2. 回到 **Payout Account** 页面 → 点 **Submit for review**
3. 等待 **1–2 个工作日**

**被拒了怎么办？** 按前面说的，Creem 不一定给第二次机会。所以提交前务必确认：

- [ ] 域名邮箱已生效（**真发一封邮件测试过**）
- [ ] 隐私政策、服务条款、退款政策三个页面都能**独立打开**
- [ ] 落地页能看到**明确价格**和**交付内容清单**
- [ ] **没有占位符**（`你的产品ID`、`example.com`、Lorem ipsum 之类）
- [ ] **没有虚假用户评价**
- [ ] 客服邮箱在**页面和收据**上都可见
- [ ] 退款规则有**可量化判定标准**（14 天 / 下载不超过 3 次）
- [ ] 隐私政策**写清了数据流向**（哪些本地、哪些上云）
- [ ] 免责声明写明**输出不构成权威认定**
- [ ] 页脚有「本站与第三方支付平台无关」的免责说明

---

# 常见问题

**Q：一定要域名吗？能用 GitHub Pages 默认地址先凑合？**
A：技术上可以先上 `用户名.github.io/仓库名/`，但 **Creem 审核大概率要求自定义域名**，
而且一个店铺对应一个网站，后期换地址很麻烦。建议一次到位。

**Q：邮箱必须真的能收到信吗？**
A：**必须**。收不到信的邮箱会被拒。而且 Creem 会在**收据**上展示这个邮箱——
客户付了钱收不到回复，Creem 有权代为退款。

**Q：审核要多久？**
A：通常 1–2 个工作日。但**没有承诺时限**，赶时间的话别把上架时间卡死。

**Q：可以不绑域名邮箱，用 Zoho 邮箱吗？**
A：Zoho Mail 免费版支持 1 个域名、5 个用户、5GB，但只有网页版收发。
用 Cloudflare Email Routing 更省事（完全免费，配置简单）。

**Q：Creem 抽多少？**
A：**3.9% + $0.40/笔**，无月费、无开通费、无最低消费，**不加国际卡附加费**。
$100 一单扣 $4.30。提现每笔收 $7 或 1%（取高）。

**Q：什么时候能收到钱？**
A：余额满 **$50**（或 €50）才能提现，每月的 1 号和 15 号各一次。
支付可能因风控复核**延迟 7–12 天**才计入余额。所以第一笔钱到账通常要等两三周。

**Q：人民币怎么到手？**
A：Creem 结算时余额是美元/欧元，但**提现账户可以选 CNY**——
个人选 Alipay，企业选本地银行账户。买家那边支持多币种付款。

**Q：网站需要备案吗？**
A：**不需要**。GitHub Pages 在境外，国内服务器才要备案。

---

# 三十秒速查

| 目的 | 命令 |
|---|---|
| 改站点配置 | `open ~/Desktop/github-earning/store/site/site-config.json` |
| 应用配置 | `cd ~/Desktop/github-earning/store && /usr/bin/python3 apply_config.py` |
| 发布前自检 | `cd ~/Desktop/github-earning/store && /usr/bin/python3 deploy_site.py` |
| 发布上线 | `cd ~/Desktop/github-earning/store && /usr/bin/python3 deploy_site.py --publish` |
| 看本地页面 | `open ~/Desktop/github-earning/store/site/index.html` |
| 检查域名解析 | `dig +short 你的域名.com` |
