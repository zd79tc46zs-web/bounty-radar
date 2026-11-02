#!/usr/bin/env python3
"""
信号雷达 —— 挂机收益系统的"眼睛"

每轮扫描做三件事：
  1. 抓取 GitHub 上的付费机会（bounty issue）与需求信号（help wanted / good first issue）
  2. 用可验证的证据筛掉"看着像赏金、其实从不付款"的假仓库
  3. 判定每个机会的结算通道是否对"中国大陆个人"可行（这是能不能真收到钱的唯一关键）

只用 Python 标准库，无第三方依赖，可直接丢进 GitHub Actions 跑。
"""

import json
import os
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

GITHUB_API = "https://api.github.com"
OPIRE_API = "https://api.opire.dev/rewards"
UA = "bounty-radar/1.0 (+github actions)"

# 结算通道 → 中国大陆个人能否实际收到钱
# 依据见 docs/收款通道可行性.md，每条都对应可核验的公开来源
PAYOUT_RAILS = {
    "stripe":    {"cn": False, "note": "Stripe Connect 收款，大陆个人无法开户/提现"},
    "algora":    {"cn": False, "note": "Algora 仅 Stripe Connect，无 USDC 付款通道"},
    "polar":     {"cn": False, "note": "Polar 走 Stripe Connect Express，大陆不在 payout 列表"},
    "opire_crypto": {"cn": False, "note": "加密货币结算在大陆存在合规风险，不建议"},
    "ubq_crypto": {"cn": False, "note": "Ubiquity 用 UBQ 稳定币结算，链上出入金在大陆有合规风险"},
    "paypal":    {"cn": True,  "note": "PayPal 大陆商家可提现，但单笔固定费 $35"},
    "creem":     {"cn": True,  "note": "Creem 支持大陆个人，提现到支付宝，MoR 代缴税"},
    "paddle":    {"cn": True,  "note": "Paddle 支持大陆卖家，结算到大陆银行，月结"},
    "gumroad":   {"cn": True,  "note": "Gumroad 大陆仅可提现到 PayPal，费率 10%"},
    "unknown":   {"cn": None,  "note": "通道未知，需人工确认"},
}

# 疑似刷量/诈骗仓库的已知特征（来自实测：同一标题在多仓库重复出现）
SPAM_TITLE_PAT = re.compile(r"(bounty\s*seguro|\$\$?\d+\s*seguro)", re.I)

AMOUNT_PATTERNS = [
    re.compile(r"\$\s?([\d,]+(?:\.\d+)?)"),
    re.compile(r"(?:price|reward|bounty|amount)\s*[:=]\s*\$?\s?([\d,]+(?:\.\d+)?)", re.I),
    re.compile(r"([\d,]+(?:\.\d+)?)\s*(?:usd|USDT|USDC)", re.I),
    re.compile(r"reward-([\d]+)-usd", re.I),
]


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def http_json(url, headers=None, timeout=25):
    """返回 (status, parsed_body)。网络失败不抛异常，返回 (0, None)。"""
    h = {"User-Agent": UA, "Accept": "application/vnd.github+json"}
    h.update(headers or {})
    try:
        req = urllib.request.Request(url, headers=h)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", "replace")
            try:
                return resp.status, json.loads(raw)
            except json.JSONDecodeError:
                return resp.status, raw
    except urllib.error.HTTPError as e:
        return e.code, None
    except Exception:
        return 0, None


def extract_amount(text):
    """从标题/正文/标签中提取金额。找不到返回 None。"""
    if not text:
        return None
    for pat in AMOUNT_PATTERNS:
        m = pat.search(text)
        if m:
            raw = m.group(1).replace(",", "")
            try:
                val = float(raw)
            except ValueError:
                continue
            # 过滤明显不是金额的数字（如年份、issue 号）
            if 5 <= val <= 200000:
                return val
    return None


def detect_rail(text):
    """从文本判断结算通道。"""
    t = (text or "").lower()
    if "algora" in t:
        return "algora"
    if "polar" in t:
        return "polar"
    if "ubiquity" in t or "ubq" in t or "devpool" in t:
        return "ubq_crypto"
    if "opire" in t:
        return "opire_crypto"
    if "creem" in t:
        return "creem"
    if "paddle" in t:
        return "paddle"
    if "paypal" in t:
        return "paypal"
    if "stripe" in t:
        return "stripe"
    if "gumroad" in t:
        return "gumroad"
    return "unknown"


def detect_time_budget(text):
    """
    识别 Ubiquity 的 "Time: <15 Minutes" / "<1 Hour" 标签。
    这类任务是全自动化的最优目标——AI 能在单次运行内完成并提交 PR。
    返回分钟数上限，找不到返回 None。
    """
    t = (text or "")
    m = re.search(r"time:\s*<\s*(\d+)\s*(minute|min|hour|day)", t, re.I)
    if not m:
        return None
    val = int(m.group(1))
    unit = m.group(2).lower()
    if unit.startswith("hour"):
        return val * 60
    if unit.startswith("day"):
        return val * 60 * 24
    return val


# ── 次级速率限制节流 ──
# 实测（2026-11-02）：GitHub 搜索 API 有"次级速率限制"——
# 即使配额充足（30/分钟、used 仅 5），连续快速请求也会随机返回 403。
# 连打 8 次的实测结果：403 403 200 200 200 200 200 200（前两次被拒后自行恢复）。
# 对策：搜索请求之间强制间隔，并缓存结果。
_SEARCH_LAST_CALL = [0.0]
_SEARCH_MIN_INTERVAL = 1.5   # 秒
_SEARCH_CACHE = {}           # {query: items} 跨轮次持久化到 reports/.search_cache.json


def _throttle_search():
    """搜索请求间强制间隔，避开 GitHub 次级速率限制。"""
    now = time.time()
    wait = _SEARCH_LAST_CALL[0] + _SEARCH_MIN_INTERVAL - now
    if wait > 0:
        time.sleep(wait)
    _SEARCH_LAST_CALL[0] = time.time()


def gh_search(query, per_page=30, token=None):
    """
    调用 GitHub Search API 搜索 issue。

    重要（2026-11-02 实测踩坑）：
    GitHub 侧规则变更——搜索 issue 时 query **必须显式包含 'is:issue' 或
    'is:pull-request'**，否则返回 HTTP 422：
        {"message": "Query must include 'is:issue' or 'is:pull-request'"}

    这个改动让原本能用的查询全部静默失败（422 时旧代码直接返回空列表，
    表现为"扫到 0 条"，一度被误判为限流）。
    因此这里统一兜底补上 is:issue，一处修改覆盖所有查询。

    另外加了降级：若仍失败，用不带 sort 的形式重试一次。
    """
    def _search(q_raw, sort=True):
        _throttle_search()
        q = urllib.parse.quote(q_raw)
        url = f"{GITHUB_API}/search/issues?q={q}&per_page={per_page}"
        if sort:
            url += "&sort=created&order=desc"
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        status, data = http_json(url, headers)
        if status != 200 or not isinstance(data, dict):
            return None, status
        return data.get("items", []) or [], status

    # 统一补 is:issue
    augmented = query if ("is:issue" in query or "is:pull-request" in query) \
        else f"{query} is:issue"

    items, status = _search(augmented, sort=True)
    if items is None:
        # 降级1：不带 sort 参数再试
        items, status = _search(augmented, sort=False)
    if items is None:
        # 降级2：去掉 stars: 这类限定符（GitHub 偶尔对组合查询更严格）
        simple = re.sub(r"stars:[><=]+\d+\s*", "", augmented)
        items, status = _search(simple, sort=False)

    if items is None:
        # 403 为主：GitHub 次级速率限制（Actions runner 是共享 IP，更易触发）。
        # 策略：退避重试 → 仍失败则回退到上一轮缓存，保证每轮报告都有内容。
        if status == 403:
            print(f"    [wait] 触发次级限速，退避 12 秒后重试…", flush=True)
            time.sleep(12)
            items, status = _search(augmented, sort=True)
        if items is None:
            cached = _SEARCH_CACHE.get(query)
            if cached:
                print(f"    [cache] 搜索失败 (HTTP {status})，使用上一轮缓存 "
                      f"{len(cached)} 条: {query[:50]}", flush=True)
                return cached
            print(f"    [warn] 搜索失败 (HTTP {status}) 且无缓存: {query[:60]}", flush=True)
            return []

    # 成功则写入缓存，供下一轮兜底使用
    _SEARCH_CACHE[query] = items
    return items


def repo_probe(owner, repo, token=None):
    """
    探针：取仓库关键信号，用于判断"这个仓库到底付不付款"。

    核心判据（按实测反作弊结论排序）：
      1. human_merged_prs —— 近期被真人合并的 PR 数。真实付费仓库必然 > 0；
         bot 农场（挂 $660/$750 标签却从不付款的仓库）该值恒为 0。
      2. contributors —— 贡献者数。bot 农场恒为 1（只有建仓人）。
      3. watchers —— 真实关注者数，bot 农场恒为 0。
      4. fork_ratio —— fork 数远高于 star 数，是"批量造仓库/刷量"的典型特征。
      5. closed_bounties —— 历史结清赏金数。注意：单独用它不可靠，
         bot 农场会批量关闭 issue 让该值虚高，必须与 1-4 联用。
    """
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    out = {"full_name": f"{owner}/{repo}"}

    st, meta = http_json(f"{GITHUB_API}/repos/{owner}/{repo}", headers)
    if st == 200 and isinstance(meta, dict):
        out.update({
            "stars": meta.get("stargazers_count", 0),
            "forks": meta.get("forks_count", 0),
            "open_issues": meta.get("open_issues_count", 0),
            "created_at": meta.get("created_at"),
            "pushed_at": meta.get("pushed_at"),
            "archived": meta.get("archived", False),
            "watchers": meta.get("subscribers_count", 0),
            "size_kb": meta.get("size", 0),
            "license": (meta.get("license") or {}).get("spdx_id"),
        })

    # 历史已关闭的赏金数（仅作辅助判据）
    # 注意：搜索 issue 必须带 is:issue，否则 GitHub 返回 422
    st2, closed = http_json(
        f"{GITHUB_API}/search/issues?q="
        + urllib.parse.quote(f"repo:{owner}/{repo} label:bounty is:closed is:issue")
        + "&per_page=1",
        headers,
    )
    if st2 == 200 and isinstance(closed, dict):
        out["closed_bounties"] = closed.get("total_count", 0)
    else:
        out["closed_bounties"] = None

    # 真人合并 PR（硬判据）：近期 closed PR 中 merged_at 非空、且作者不是机器人
    st3, pulls = http_json(
        f"{GITHUB_API}/repos/{owner}/{repo}/pulls?state=closed&per_page=100", headers)
    bot_names = {"github-actions[bot]", "bot", "dependabot[bot]",
                 "renovate[bot]", "codecov[bot]", "sonarcloud[bot]"}
    if st3 == 200 and isinstance(pulls, list):
        merged = [p for p in pulls if p.get("merged_at")]
        humans = [p for p in merged
                  if (p.get("user") or {}).get("login", "").lower() not in bot_names]
        external = [p for p in humans
                    if (p.get("user") or {}).get("login", "").lower() != owner.lower()]
        out["merged_prs"] = len(merged)
        out["human_merged_prs"] = len(humans)
        out["external_merged_prs"] = len(external)
    else:
        out["merged_prs"] = None
        out["human_merged_prs"] = None
        out["external_merged_prs"] = None

    # 贡献者数
    st4, contrib = http_json(
        f"{GITHUB_API}/repos/{owner}/{repo}/contributors?per_page=100", headers)
    out["contributors"] = len(contrib) if st4 == 200 and isinstance(contrib, list) else None

    return out


def farm_signals(info):
    """
    识别 bot 农场 / 刷量仓库。返回 (是否可疑, 命中特征列表)。
    实测样本：
      warpspeed-bounties          ($660 标签)  human_merged=0 contributors=1 watchers=0
      bounty-plaza               ($750 标签)  human_merged=0 contributors=1 watchers=0
      awesome-agent-bounties     ($3k  标签)  human_merged=0 contributors=1 watchers=0
      business-development       (真实付款)     human_merged=20 contributors=8 watchers=2
    """
    hits = []
    hmp = info.get("human_merged_prs")
    contrib = info.get("contributors")
    watchers = info.get("watchers")
    stars = info.get("stars") or 0
    forks = info.get("forks") or 0

    if hmp is not None and hmp == 0:
        hits.append("零真人合并PR")
    if contrib is not None and contrib <= 1:
        hits.append("贡献者仅1人")
    if watchers is not None and watchers == 0:
        hits.append("零关注者")
    if stars and forks >= stars * 3 and forks >= 20:
        hits.append(f"fork/star={forks}/{stars} 异常")
    if (info.get("size_kb") is not None and info.get("size_kb") <= 10
            and (info.get("created_at") or "") >= "2026-01-01"):
        hits.append("仓库体积近空且为新建")
    return (len(hits) >= 2), hits


def score_bounty(item, repo_info):
    """
    给一个赏金 issue 打分（0-100）。
    维度：金额 / 竞争度 / 仓库可信度 / 需求真实性 / 结算可行性
    """
    labels = [l.get("name", "") for l in item.get("labels", [])]
    label_text = " ".join(labels)
    body = item.get("body") or ""
    title = item.get("title") or ""
    text = f"{title}\n{body}\n{label_text}"

    amount = extract_amount(text)
    rail = detect_rail(text)
    rail_info = PAYOUT_RAILS.get(rail, PAYOUT_RAILS["unknown"])

    reasons = []
    score = 0.0

    # —— 金额（最高 30 分）——
    if amount:
        score += min(30, 8 + (amount ** 0.5) * 1.4)
        reasons.append(f"金额 ${amount:.0f}")
    else:
        reasons.append("未标注金额")

    # —— 竞争度（最高 -25 分，评论越多扣越多）——
    comments = item.get("comments", 0)
    if item.get("assignee"):
        score -= 30
        reasons.append("已被指派，直接跳过")
    elif comments == 0:
        score += 10
        reasons.append("零评论，竞品少")
    elif comments <= 3:
        score += 6
        reasons.append(f"仅 {comments} 条评论")
    elif comments <= 12:
        score -= 4
        reasons.append(f"{comments} 条评论，竞争中等")
    elif comments <= 40:
        score -= 12
        reasons.append(f"{comments} 条评论，竞争激烈")
    else:
        score -= 22
        reasons.append(f"{comments} 条评论，大概率已被抢")

    # —— 仓库可信度（最高 25 分）——
    # 硬判据：真人合并 PR
    hmp = repo_info.get("human_merged_prs")
    if hmp is None:
        pass
    elif hmp >= 20:
        score += 20
        reasons.append(f"近期有 {hmp} 个真人合并PR，仓库真实运作")
    elif hmp >= 5:
        score += 14
        reasons.append(f"有 {hmp} 个真人合并PR")
    elif hmp >= 1:
        score += 6
        reasons.append(f"有 {hmp} 个真人合并PR")
    else:
        score -= 30
        reasons.append("🚨 零真人合并PR：从未接受过任何外部代码，几乎不付款")

    closed_b = repo_info.get("closed_bounties")
    if closed_b and closed_b >= 5 and (hmp or 0) > 0:
        score += 5
        reasons.append(f"历史结清 {closed_b} 笔赏金")

    # bot 农场综合判定
    suspicious, farm_hits = farm_signals(repo_info)
    if suspicious:
        score -= 28
        reasons.append("🚨 刷量/农场特征：" + "、".join(farm_hits))

    stars = repo_info.get("stars")
    if stars is not None:
        if stars >= 1000:
            score += 7
        elif stars >= 100:
            score += 4
        elif stars < 10 and not suspicious:
            score -= 4

    pushed = repo_info.get("pushed_at")
    if pushed:
        try:
            pt = datetime.fromisoformat(pushed.replace("Z", "+00:00"))
            days = (datetime.now(timezone.utc) - pt).days
            if days <= 30:
                score += 6
                reasons.append(f"{days} 天内有提交，项目活跃")
            elif days > 180:
                score -= 10
                reasons.append(f"已 {days} 天无提交，项目停滞")
        except Exception:
            pass

    # —— 需求真实性（最高 20 分）——
    if len(body) > 400:
        score += 12
        reasons.append("需求描述详实")
    elif len(body) > 120:
        score += 6
    else:
        score -= 8
        reasons.append("需求描述过于单薄")

    if any(k in label_text.lower() for k in ("good first issue", "help wanted", "documentation", "test")):
        score += 8
        reasons.append("属低门槛友好型任务")

    # —— 诈骗特征 ——
    if SPAM_TITLE_PAT.search(title):
        score -= 60
        reasons.append("🚨 命中已知刷量标题模式")
    if repo_info.get("created_at") and repo_info.get("pushed_at"):
        try:
            cb = datetime.fromisoformat(repo_info["created_at"].replace("Z", "+00:00"))
            pb = datetime.fromisoformat(repo_info["pushed_at"].replace("Z", "+00:00"))
            if (pb - cb).days <= 3 and cb > datetime.now(timezone.utc) - timedelta(days=45):
                score -= 25
                reasons.append("🚨 仓库极新且立即挂赏金，典型钓鱼特征")
        except Exception:
            pass
    if repo_info.get("archived"):
        score -= 30
        reasons.append("🚨 仓库已归档")

    # —— 结算可行性（可调权重）——
    cn_ok = rail_info["cn"]
    if cn_ok is True:
        score += 10
        reasons.append(f"✅ 结算通道可行：{rail}（{rail_info['note']}）")
    elif cn_ok is False:
        score -= 12
        reasons.append(f"⛔ 结算通道对大陆个人不可行：{rail}（{rail_info['note']}）")

    # —— 自动适配度：这项任务能否"无人挂机"完成（额外 0~25 分）——
    minutes = detect_time_budget(label_text)
    auto_fit = None
    if minutes is not None:
        if minutes <= 15:
            score += 25
            auto_fit = "极优"
            reasons.append(f"🤖 标注 {minutes} 分钟内可完成，最适合全自动挂机")
        elif minutes <= 60:
            score += 18
            auto_fit = "优"
            reasons.append(f"🤖 标注 {minutes} 分钟内可完成，适合挂机")
        elif minutes <= 24 * 60:
            score += 8
            auto_fit = "中"
            reasons.append(f"🤖 标注 {minutes // 60} 小时内可完成")
        else:
            auto_fit = "差"
            reasons.append("⏱ 标注工时超过1天，不适合无人挂机")
    else:
        # 无时间标签：按需求规模推断
        if len(body) < 300:
            auto_fit = "中"
            score += 6
            reasons.append("🤖 需求体量小，可能适合自动化")
        else:
            auto_fit = "待判"
            reasons.append("⏱ 无工时标注，需人工判断是否可自动化")

    return {
        "score": round(max(0, min(100, score)), 1),
        "amount": amount,
        "rail": rail,
        "rail_note": rail_info["note"],
        "cn_payout_possible": cn_ok,
        "auto_fit": auto_fit,
        "time_budget_min": minutes,
        "reasons": reasons,
    }


def collect_bounties(token=None, limit_repos=30):
    """扫描 GitHub 上的赏金 issue，并对涉及的仓库做真实性探针。"""
    queries = [
        'label:"bounty" state:open no:assignee',
        'label:"💰 bounty" state:open no:assignee',
        'label:"reward" state:open no:assignee',
        'label:"Price: 400 USD" state:open',
        'label:"paid" state:open no:assignee',
    ]
    seen = {}
    for q in queries:
        for it in gh_search(q, per_page=50, token=token):
            url = it.get("html_url", "")
            if url and url not in seen:
                seen[url] = it
        # 节流已在 gh_search 内部统一处理

    # 探针顺序：先按"有明确金额标签/正文"的排前面，同时优先非 bot 农场嫌疑的仓库
    def amount_of(it):
        labels = " ".join(l.get("name", "") for l in it.get("labels", []))
        return extract_amount(f"{it.get('title','')}\n{it.get('body') or ''}\n{labels}") or 0

    ordered = sorted(seen.values(), key=amount_of, reverse=True)

    # 先确定要探针的仓库（按金额排序，最多 limit_repos 个）
    targets = []
    picked = set()
    for it in ordered:
        m = re.match(r"https://github\.com/([^/]+)/([^/]+)/issues/(\d+)", it.get("html_url", ""))
        if not m:
            continue
        key = f"{m.group(1)}/{m.group(2)}"
        if key not in picked:
            if len(picked) >= limit_repos:
                continue
            picked.add(key)
        targets.append((it, m.group(1), m.group(2), m.group(3), key))

    # 并发探针：单次 API 约 2 秒，串行 9 仓库×4 请求要 70 秒以上
    repo_cache = {}
    if targets:
        keys = list(dict.fromkeys(t[4] for t in targets))
        print(f"    [probe] 并发探针 {len(keys)} 个仓库…", flush=True)
        with ThreadPoolExecutor(max_workers=6) as ex:
            futs = {ex.submit(repo_probe, k.split("/")[0], k.split("/")[1], token): k
                    for k in keys}
            for fut, k in futs.items():
                try:
                    repo_cache[k] = fut.result()
                except Exception:
                    repo_cache[k] = {}

    results = []
    for it, owner, repo, number, key in targets:
        info = repo_cache.get(key)
        if info is None:
            continue

        sc = score_bounty(it, info)
        results.append({
            "number": number,
            "title": it.get("title"),
            "url": url,
            "repo": key,
            "repo_info": info,
            "labels": [l.get("name") for l in it.get("labels", [])],
            "created_at": it.get("created_at"),
            "updated_at": it.get("updated_at"),
            "body_excerpt": (it.get("body") or "")[:600],
            "analysis": sc,
        })
    return results


def collect_opire(token=None):
    """Opire 公开 API：无需认证，返回全部活跃赏金。"""
    status, data = http_json(OPIRE_API)
    if status != 200 or not isinstance(data, list):
        return []
    out = []
    for r in data:
        price = r.get("pendingPrice") or {}
        cents = price.get("value")
        amount = (cents / 100.0) if isinstance(cents, (int, float)) else None
        url = r.get("url") or ""
        m = re.match(r"https://github\.com/([^/]+)/([^/]+)/issues/(\d+)", url)
        if not m:
            continue
        owner, repo = m.group(1), m.group(2)
        info = repo_probe(owner, repo, token) if len(out) < 8 else {}
        trying = r.get("tryingUsers") or []
        claimers = r.get("claimerUsers") or []
        out.append({
            "title": r.get("title"),
            "url": url,
            "repo": f"{owner}/{repo}",
            "amount": amount,
            "trying_users": len(trying),
            "claimer_users": len(claimers),
            "languages": r.get("programmingLanguages") or [],
            "repo_info": info,
            "rail": "opire_crypto",
        })
    return out


def collect_signals(token=None):
    """
    需求信号：不带钱的 help wanted / good first issue / documentation。
    这是"自建数字产品"的选题来源——比抢赏金更适合大陆个人。
    """
    queries = [
        'label:"help wanted" state:open no:assignee stars:>200',
        'label:"good first issue" state:open no:assignee stars:>500',
        'label:"documentation" state:open no:assignee stars:>300',
    ]
    seen = {}
    for q in queries:
        for it in gh_search(q, per_page=20, token=token):
            u = it.get("html_url", "")
            if u and u not in seen:
                seen[u] = it

    out = []
    for it in list(seen.values())[:30]:
        out.append({
            "title": it.get("title"),
            "url": it.get("html_url"),
            "repo": it.get("repository_url", "").split("/repos/")[-1],
            "labels": [l.get("name") for l in it.get("labels", [])],
            "comments": it.get("comments", 0),
            "body_excerpt": (it.get("body") or "")[:300],
        })
    return out


def collect_pool_repos(token=None):
    """
    抓取"高可信赏金池"——经过人工验证、确实付款的仓库集合。

    实测结论：按 `label:"Price: N USD"` 搜索能精确定位 Ubiquity/DevPool 生态的
    真实付费赏金（943 条带标价 issue）。这类仓库同时带 "Time: <N Minutes" 标签，
    是全自动挂机的最优目标池。
    """
    # 查询数量刻意精简：GitHub 搜索 API 限速是 30 次/分钟，
    # 查询太多会让部分查询被 403 拒掉，反而漏数据。2 个查询已能覆盖主流标价。
    queries = [
        'label:"Price: 75 USD" state:open no:assignee',
        'label:"Price: 300 USD" state:open no:assignee',
    ]
    seen = {}
    for q in queries:
        for it in gh_search(q, per_page=25, token=token):
            u = it.get("html_url", "")
            if u and u not in seen:
                seen[u] = it


    # 先收集仓库列表，再并发探针
    targets = []
    picked = set()
    for it in seen.values():
        m = re.match(r"https://github\.com/([^/]+)/([^/]+)/issues/(\d+)", it.get("html_url", ""))
        if not m:
            continue
        key = f"{m.group(1)}/{m.group(2)}"
        if key not in picked:
            if len(picked) >= 8:
                continue
            picked.add(key)
        targets.append((it, m.group(1), m.group(2), m.group(3), key))

    repo_cache = {}
    if targets:
        keys = list(dict.fromkeys(t[4] for t in targets))
        print(f"    [probe] 并发探针 {len(keys)} 个仓库…", flush=True)
        with ThreadPoolExecutor(max_workers=6) as ex:
            futs = {ex.submit(repo_probe, k.split("/")[0], k.split("/")[1], token): k
                    for k in keys}
            for fut, k in futs.items():
                try:
                    repo_cache[k] = fut.result()
                except Exception:
                    repo_cache[k] = {}

    out = []
    for it, owner, repo, number, key in targets:
        info = repo_cache.get(key)
        if info is None:
            continue
        sc = score_bounty(it, info)
        out.append({
            "number": number,
            "title": it.get("title"),
            "url": it.get("html_url", ""),
            "repo": key,
            "repo_info": repo_cache[key],
            "labels": [l.get("name") for l in it.get("labels", [])],
            "body_excerpt": (it.get("body") or "")[:500],
            "analysis": sc,
        })
    return out


def render_markdown(payload):
    """把扫描结果渲染成人能直接看的 Markdown 报告。"""
    L = []
    L.append("# 挂机收益雷达 · 扫描报告")
    L.append("")
    L.append(f"- 生成时间：{payload['generated_at']}")
    L.append(f"- 扫描耗时：{payload['duration_sec']} 秒")
    L.append(f"- GitHub 赏金候选：**{len(payload['bounties'])}** 条")
    L.append(f"- 真实付费赏金池：**{len(payload.get('pool', []))}** 条")
    L.append(f"- Opire 平台赏金：**{len(payload['opire'])}** 条")
    L.append(f"- 需求信号：**{len(payload['signals'])}** 条")
    L.append("")
    L.append("---")
    L.append("")

    L.append("## 一、高价值赏金候选（按可信度×可行性排序）")
    L.append("")
    tops = payload["bounties"][:12]
    if not tops:
        L.append("> 本轮未发现符合条件的高价值候选。")
    for i, b in enumerate(tops, 1):
        a = b["analysis"]
        L.append(f"### {i}. [{b['title']}]({b['url']})")
        L.append("")
        L.append(f"- **可信度评分**：{a['score']}/100 ｜ 仓库：`{b['repo']}`")
        if a["amount"]:
            L.append(f"- **金额**：${a['amount']:.0f}")
        L.append(f"- **结算通道**：`{a['rail']}` — {a['rail_note']}")
        L.append(f"- **大陆可收款**：{'✅ 是' if a['cn_payout_possible'] is True else ('⛔ 否' if a['cn_payout_possible'] is False else '❓ 需确认')}")
        ri = b.get("repo_info", {})
        if ri:
            L.append(f"- 仓库信号：★{ri.get('stars', '?')} ｜ 历史结清赏金 {ri.get('closed_bounties', '?')} 笔 ｜ 提交于 {ri.get('pushed_at', '?')}")
        L.append("- 判断依据：" + "；".join(a["reasons"]))
        L.append("")

    L.append("## 二、真实付费赏金池（★ 最高价值：已验证付款 + 短工时）")
    L.append("")
    L.append("> 这批来自实测确认**真实付过款**的仓库（Ubiquity/DevPool 生态）。")
    L.append("> `Time: <N Minutes` 标签意味着单次自动运行即可完成并提交 PR，是挂机最优目标。")
    L.append("")
    if not payload.get("pool"):
        L.append("> 本轮未捕获（可能触发 API 限速，稍后重试即可）。")
    for i, b in enumerate(payload.get("pool", [])[:15], 1):
        a = b["analysis"]
        L.append(f"### P{i}. [{b['title']}]({b['url']})")
        L.append("")
        L.append(f"- 评分 **{a['score']}/100** ｜ ${a['amount'] or 0:.0f} ｜ `{b['repo']}`")
        L.append(f"- 自动适配度：**{a.get('auto_fit') or '待判'}** ｜ 结算通道：`{a['rail']}`")
        L.append(f"- 大陆可收款：{'✅ 是' if a['cn_payout_possible'] is True else ('⛔ 否' if a['cn_payout_possible'] is False else '❓ 需确认')}")
        L.append(f"- 标签：{', '.join(b['labels'])}")
        L.append("- 判断依据：" + "；".join(a["reasons"][:6]))
        L.append("")

    L.append("## 三、Opire 平台赏金")
    L.append("")
    if not payload["opire"]:
        L.append("> Opire 公开 API 本轮返回空。")
    for o in payload["opire"]:
        L.append(f"- **{o.get('title')}** — {o.get('amount')} USD ｜ `{o['repo']}` ｜ 已认领 {o.get('claimer_users', 0)} 人 ｜ 尝试中 {o.get('trying_users', 0)} 人")
        L.append(f"  - {o['url']}")
    L.append("")

    L.append("## 四、需求信号（自建数字产品的选题来源）")
    L.append("")
    L.append("> 这些是不带钱的真实需求。面向大陆个人开发者，**自己做产品 + Creem/Paddle 收款**的路径比抢赏金更可行。")
    L.append("")
    for s in payload["signals"][:12]:
        L.append(f"- {s['title'][:80]} — `{s['repo']}` ({s['comments']} 评论)")
        L.append(f"  - {s['url']}")
    L.append("")

    L.append("---")
    L.append("")
    L.append("**付款真实性判据**：`closed_bounties` = 该仓库历史上已结清的赏金笔数。真实付费过的仓库必然 > 0；")
    L.append("为 0 的仓库即使挂着 $660 的标签也从未付过钱，不应投入。")
    L.append("")
    L.append("**结算通道判据**：见 `docs/收款通道可行性.md`。Stripe 系（Algora/Polar）对大陆个人不可行，")
    L.append("Creem/Paddle 可行。这是「能不能真的收到钱」的决定性因素。")
    return "\n".join(L)


def main():
    t0 = time.time()
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    outdir = os.environ.get("REPORT_DIR", "reports")
    os.makedirs(outdir, exist_ok=True)

    # 载入上一轮搜索缓存（供 403 限速时兜底）
    cache_file = os.path.join(outdir, ".search_cache.json")
    try:
        with open(cache_file, encoding="utf-8") as f:
            _SEARCH_CACHE.update(json.load(f))
        if _SEARCH_CACHE:
            print(f"[radar] 载入缓存 {len(_SEARCH_CACHE)} 条查询结果", flush=True)
    except Exception:
        pass

    print("[radar] 抓取 GitHub 赏金…", flush=True)
    bounties = collect_bounties(token)
    print(f"[radar] 命中 {len(bounties)} 条候选", flush=True)

    print("[radar] 抓取真实付费赏金池…", flush=True)
    pool = collect_pool_repos(token)
    print(f"[radar] 赏金池 {len(pool)} 条", flush=True)

    print("[radar] 抓取 Opire 平台…", flush=True)
    opire = collect_opire(token)
    print(f"[radar] Opire {len(opire)} 条", flush=True)

    print("[radar] 抓取需求信号…", flush=True)
    signals = collect_signals(token)
    print(f"[radar] 信号 {len(signals)} 条", flush=True)

    # 只保留 score >= 45 的，避免报告被垃圾淹没
    bounties.sort(key=lambda b: b["analysis"]["score"], reverse=True)
    bounties = [b for b in bounties if b["analysis"]["score"] >= 45]
    pool.sort(key=lambda b: b["analysis"]["score"], reverse=True)

    payload = {
        "generated_at": now_iso(),
        "duration_sec": round(time.time() - t0, 1),
        "bounties": bounties,
        "pool": pool,
        "opire": opire,
        "signals": signals,
    }

    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    with open(os.path.join(outdir, "latest.json"), "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    with open(os.path.join(outdir, "latest.md"), "w", encoding="utf-8") as f:
        f.write(render_markdown(payload))
    with open(os.path.join(outdir, f"scan-{day}.json"), "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    # 保存本轮搜索缓存，供下一轮兜底
    try:
        slim = {k: [{"number": i.get("number"), "title": i.get("title"),
                     "html_url": i.get("html_url"),
                     "repository_url": i.get("repository_url"),
                     "labels": i.get("labels"), "comments": i.get("comments"),
                     "created_at": i.get("created_at"),
                     "body": (i.get("body") or "")[:600]} for i in v]
                 for k, v in _SEARCH_CACHE.items()}
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(slim, f, ensure_ascii=False)
    except Exception as e:
        print(f"[radar] 缓存保存失败: {e}", flush=True)

    print(f"[radar] 报告已写入 {outdir}/latest.md", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
