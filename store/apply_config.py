#!/usr/bin/env python3
"""
把 site-config.json 里的配置应用到全站页面。

用法：改完 site/site-config.json 后运行本脚本。
"""
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(HERE, "site")
cfg = json.load(open(os.path.join(SITE, "site-config.json"), encoding="utf-8"))

BRAND = cfg.get("brand_name") or "EduForge AI"
EMAIL = cfg.get("support_email") or "support@example.com"
CHECKOUT = cfg.get("creem_checkout_url") or ""
LAW = cfg.get("applicable_law") or "中华人民共和国法律"
COURT = cfg.get("governing_court") or "运营方所在地有管辖权的人民法院"
LEGAL = cfg.get("company_legal_name") or BRAND

changed = []
for fn in ["index.html", "privacy.html", "terms.html", "refund.html"]:
    p = os.path.join(SITE, fn)
    if not os.path.exists(p):
        continue
    s = open(p, encoding="utf-8").read()
    orig = s
    s = s.replace("support@example.com", EMAIL)
    s = s.replace("EduForge AI", BRAND)
    s = s.replace("EduForge", BRAND.split()[0] if " " in BRAND else BRAND)
    s = s.replace("https://buy.creem.io/你的产品ID", CHECKOUT)
    s = s.replace("中华人民共和国法律（不含冲突法规则）", LAW)
    s = s.replace("运营方所在地有管辖权的人民法院", COURT)
    if s != orig:
        open(p, "w", encoding="utf-8").write(s)
        changed.append(fn)

print(f"✅ 已应用配置到 {len(changed)} 个页面: {', '.join(changed) or '（无变化）'}")
print(f"   品牌名: {BRAND}")
print(f"   客服邮箱: {EMAIL}")
print(f"   结账链接: {CHECKOUT or '（未填）'}")
if CHECKOUT and "你的产品ID" not in CHECKOUT:
    # 恢复购买按钮的可点击状态
    p = os.path.join(SITE, "index.html")
    s = open(p, encoding="utf-8").read()
    s = s.replace('onclick="return false;" style="pointer-events:none;opacity:.5"', 'target="_blank" rel="noopener"')
    s = s.replace("购买按钮（待填入你的 Creem 链接）", "立即购买")
    s = s.replace("提示：教程第 5 步会告诉你如何把这个链接换成真实可用的地址。", "")
    open(p, "w", encoding="utf-8").write(s)
    print("   ✅ 购买按钮已启用")
