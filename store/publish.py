#!/usr/bin/env python3
"""
数字产品自动上架器 —— 大陆个人真正能收到钱的路径

为什么是这个？
  抢赏金（Algora/Polar/Opire）几乎都走 Stripe Connect，中国大陆个人无法开通，
  即使 PR 被合并、赏金被标记支付，钱也到不了你账上（GitHub 上有开发者
  #321 记录了被 Stripe 身份验证拦截的真实案例）。
  Ubiquity/DevPool 用 UBQ 稳定币结算，链上出入金在大陆存在合规风险。
  → 所以"自己做产品 + Creem 收款（支持大陆个人、提现到支付宝）"才是闭环路径。

工作流：
  1. 从雷达的需求信号中提炼选题（真实开发者在抱怨什么）
  2. 用模板生成产品说明 + 落地页（可接入 LLM 生成正文）
  3. 调用 Creem API 上架商品
  4. 定时更新落地页，把访问量导向已上架商品

本脚本默认 --dry-run，只做本地演练；加 --publish 并配置 CREEM_API_KEY 才真实上架。
"""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

CREEM_API = "https://api.creem.io/v1"
UA = "product-publisher/1.0"


def http_json(url, method="GET", body=None, headers=None, timeout=30):
    h = {"User-Agent": UA, "Content-Type": "application/json"}
    h.update(headers or {})
    data = json.dumps(body).encode("utf-8") if body is not None else None
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


PRODUCT_TEMPLATE = {
    "name": "",
    "description": "",
    "pricing": {"price_in_cents": 0, "currency": "USD"},
    "features": {},
}


def derive_topics(report_path, limit=8):
    """
    从雷达报告的需求信号中提炼选题。
    真实需求 → 可售卖的解决方案，这是自建产品路线的第一步。
    """
    if not os.path.exists(report_path):
        print(f"未找到报告 {report_path}")
        return []
    d = json.load(open(report_path, encoding="utf-8"))
    signals = d.get("signals", [])
    topics = []
    for s in signals:
        title = s.get("title", "")
        repo = s.get("repo", "")
        if not title:
            continue
        topics.append({
            "title": title,
            "repo": repo,
            "url": s.get("url", ""),
            "labels": s.get("labels", []),
            "keyword": re.sub(r"[^a-zA-Z0-9 ]", " ", title).split()[:3],
        })
    return topics[:limit]


def build_product(topic, price_cents=2900):
    """按选题生成一个可上架的商品定义。"""
    slug = "-".join(topic.get("keyword", ["product"])).lower()[:40] or "product"
    slug = re.sub(r"-+", "-", slug).strip("-")
    name = topic["title"][:70]
    desc = (
        f"Solution for: {topic['title']}\n\n"
        f"Derived from a real, publicly reported demand in `{topic['repo']}`.\n\n"
        "What you get:\n"
        "- A ready-to-use, documented solution package\n"
        "- Setup guide and configuration template\n"
        "- Example integration and verification script\n"
        "- Free updates for 12 months\n\n"
        "Instant download after purchase."
    )
    return {
        "slug": slug,
        "name": name,
        "description": desc,
        "pricing": {"price_in_cents": price_cents, "currency": "USD"},
        "product_id": "prod_" + hashlib.sha256(slug.encode()).hexdigest()[:16],
    }


def write_store(products, outdir="store/products"):
    os.makedirs(outdir, exist_ok=True)
    index = []
    for p in products:
        fn = os.path.join(outdir, f"{p['slug']}.json")
        with open(fn, "w", encoding="utf-8") as f:
            json.dump(p, f, ensure_ascii=False, indent=2)
        index.append(p)
    with open(os.path.join(outdir, "index.json"), "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)
    print(f"已生成 {len(products)} 个产品定义到 {outdir}/")
    return index


def creem_list_products(api_key):
    st, d = http_json(f"{CREEM_API}/products",
                      headers={"Authorization": f"Bearer {api_key}"})
    return d.get("items", []) if st == 200 and isinstance(d, dict) else []


def creem_create_product(api_key, product):
    st, d = http_json(f"{CREEM_API}/products", method="POST", body=product,
                      headers={"Authorization": f"Bearer {api_key}"})
    return st, d


def publish(products, api_key, dry_run=True):
    if dry_run:
        print("=== 演练模式（未真实上架）===")
        for p in products:
            print(f"  [产品] {p['name'][:56]}")
            print(f"          定价 ${p['pricing']['price_in_cents']/100:.2f} | slug={p['slug']}")
        print("\n加 --publish 并设置 CREEM_API_KEY 即可真实上架。")
        return 0

    existing = {p.get("slug") for p in creem_list_products(api_key)}
    ok = 0
    for p in products:
        if p["slug"] in existing:
            print(f"跳过（已上架）：{p['slug']}")
            continue
        st, d = creem_create_product(api_key, p)
        if st in (200, 201):
            print(f"✅ 已上架：{p['name'][:50]} → {d.get('id')}")
            ok += 1
        else:
            print(f"❌ 上架失败 {p['slug']}（HTTP {st}）：{d}")
    print(f"\n成功上架 {ok} 个")
    return 0


def main():
    ap = argparse.ArgumentParser(description="数字产品自动上架器")
    ap.add_argument("--report", default="reports/latest.json")
    ap.add_argument("--outdir", default="store/products")
    ap.add_argument("--limit", type=int, default=8)
    ap.add_argument("--price", type=int, default=2900, help="定价（美分），2900=$29")
    ap.add_argument("--publish", action="store_true", help="真实上架（否则仅演练）")
    args = ap.parse_args()

    topics = derive_topics(args.report, args.limit)
    if not topics:
        print("无选题。请先运行 radar/scan.py 生成报告。")
        return 1
    print(f"从需求信号中提炼 {len(topics)} 个选题：\n")
    for t in topics:
        print(f"  · {t['title'][:70]}")
        print(f"    来源：{t['repo']}")

    products = [build_product(t, args.price) for t in topics]
    write_store(products, args.outdir)

    api_key = os.environ.get("CREEM_API_KEY")
    if args.publish and not api_key:
        print("错误：--publish 需要设置 CREEM_API_KEY 环境变量")
        return 1
    return publish(products, api_key, dry_run=not args.publish)


if __name__ == "__main__":
    sys.exit(main())
