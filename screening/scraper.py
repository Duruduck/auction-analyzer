import os
import json
import math
import time
import requests
from datetime import datetime
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

# ── 설정 ─────────────────────────────────────────────────────
CONFIG = {
    "court": "수원지방법원",
    "court_code": "022",          # madangs 수원지방법원 코드
    "max_bid_price": 200_000_000, # 2억
    "top_n": 3,
    "score_alert": 80,            # 이 점수 이상은 무조건 포함
    "app_url": "https://duruduck.github.io/auction-analyzer/",
}

# ── 가격 파싱 ─────────────────────────────────────────────────
def parse_price(s):
    if not s:
        return 0
    s = s.replace(",", "").replace(" ", "")
    total = 0
    import re
    e = re.search(r'(\d+)억', s)
    m = re.search(r'(\d+)만', s)
    if e:
        total += int(e.group(1)) * 100_000_000
    if m:
        total += int(m.group(1)) * 10_000
    if total == 0:
        r = re.search(r'(\d{5,})', s)
        if r:
            total = int(r.group(1))
    return total

def fmt_price(n):
    if n >= 100_000_000:
        e = n // 100_000_000
        m = round((n % 100_000_000) / 10_000)
        return f"{e}억 {m:,}만원" if m else f"{e}억원"
    if n >= 10_000:
        return f"{round(n/10_000):,}만원"
    return f"{n:,}원"

# ── 낙찰가율 통계 ─────────────────────────────────────────────
STAT_RATES = {
    "서울":   {"아파트":[96,91,86,81,76,71,64,58,53],"다세대":[88,82,77,72,67,62,56,51,46],"빌라":[87,81,76,71,66,61,55,50,45],"오피스텔":[85,79,74,69,64,60,54,49,44],"상가":[79,73,67,62,58,53,48,44,40],"토지":[82,76,70,65,60,56,51,47,43]},
    "수도권": {"아파트":[91,85,80,75,70,65,58,53,48],"다세대":[82,76,71,66,61,57,51,46,42],"빌라":[81,75,70,65,60,56,50,45,41],"오피스텔":[79,74,68,64,59,55,49,45,40],"상가":[73,67,62,57,52,48,43,39,36],"토지":[76,70,65,60,55,51,46,42,38]},
    "지방":   {"아파트":[84,78,73,68,63,58,52,47,43],"다세대":[74,68,63,58,54,50,45,41,37],"빌라":[73,67,62,57,53,49,44,40,36],"오피스텔":[72,66,61,57,52,48,43,39,36],"상가":[67,61,56,51,47,44,39,36,33],"토지":[70,64,59,54,50,46,42,38,35]},
}
STAT_STD = {"아파트":5,"다세대":7,"빌라":7,"오피스텔":6,"상가":10,"토지":12}

def failed_idx(n):
    if n <= 0: return 0
    if n == 1: return 1
    if n == 2: return 2
    if n == 3: return 3
    if n == 4: return 4
    if n <= 6: return 5
    if n <= 9: return 6
    if n <= 14: return 7
    return 8

def detect_region(addr):
    if addr.startswith("서울"): return "서울"
    if addr.startswith("경기") or addr.startswith("인천"): return "수도권"
    return "지방"

# ── 채점 ─────────────────────────────────────────────────────
def calc_rights(d):
    score = 100
    items = []
    if d.get("inherited_rights"): score -= 50; items.append(("인수권리", -50, "critical"))
    if d.get("lien_claim"):       score -= 30; items.append(("유치권", -30, "critical"))
    if d.get("legal_surface"):    score -= 40; items.append(("법정지상권", -40, "critical"))
    if d.get("senior_tenant") and not d.get("waved_resistance"):
        if not d.get("requested_dividend"): score -= 30; items.append(("대항력임차인(배당요구미신청)", -30, "critical"))
        else: score -= 20; items.append(("선순위임차권", -20, "high"))
    if d.get("rent_registration") and not d.get("waved_resistance"):
        score -= 20; items.append(("임차권등기(대항력유지)", -20, "high"))
    return max(0, score), items

def calc_eviction(d):
    score = 100
    items = []
    occ = d.get("occupant", "미상")
    deduct = {"소유자": -10, "임차인": -20, "미상": -30}
    score += deduct.get(occ, -30); items.append((f"점유: {occ}", deduct.get(occ, -30), "medium"))
    if d.get("failed_count", 0) >= 10: score -= 20; items.append((f"유찰 {d['failed_count']}회", -20, "high"))
    if d.get("re_auction"): score -= 15; items.append(("재매각", -15, "medium"))
    return max(0, score), items

def calc_bid_estimate(d):
    region = detect_region(d.get("address", ""))
    ptype = d.get("property_type", "다세대")
    rates = STAT_RATES.get(region, STAT_RATES["지방"]).get(ptype, STAT_RATES["지방"]["다세대"])
    base = rates[failed_idx(d.get("failed_count", 0))] / 100
    rights_score, _ = calc_rights(d)
    evict_score, _ = calc_eviction(d)
    adj = 0
    if rights_score >= 90: adj += 3
    elif rights_score >= 70: adj += 1
    elif rights_score < 30: adj -= 12
    elif rights_score < 50: adj -= 5
    if evict_score >= 80: adj += 2
    elif evict_score < 40: adj -= 7
    elif evict_score < 60: adj -= 3
    if d.get("inherited_rights"): adj -= 15
    if d.get("lien_claim"): adj -= 20
    if d.get("re_auction"): adj -= 5
    adj_rate = max(0.25, min(1.20, base + adj / 100))
    return round(d.get("appraisal", 0) * adj_rate)

def calc_profit_score(bid, appraisal):
    if not appraisal: return 10
    rate = (appraisal - bid) / bid * 100
    if rate >= 20: return 40
    if rate >= 10: return 30
    if rate >= 5: return 20
    return 10

def calc_final(d):
    rs, _ = calc_rights(d)
    es, _ = calc_eviction(d)
    bid = calc_bid_estimate(d)
    ps = calc_profit_score(bid, d.get("appraisal", 0))
    return round(rs * 0.4 + es * 0.2 + ps), bid, rs, es, ps

# ── 스크래핑 ─────────────────────────────────────────────────
def fetch_listings(court_code):
    """경매마당에서 수원지방법원 물건 목록 수집"""
    listings = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        page = ctx.new_page()
        try:
            # 수원지방법원 목록 페이지
            url = f"https://madangs.com/list?court={court_code}&status=1"
            page.goto(url, timeout=30000, wait_until="networkidle")
            time.sleep(2)
            content = page.content()
            soup = BeautifulSoup(content, "html.parser")

            # 물건 링크 추출 (madangs 구조에 맞게)
            links = []
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if "caview" in href and "m_code" in href:
                    full = href if href.startswith("http") else "https://madangs.com" + href
                    if full not in links:
                        links.append(full)

            print(f"목록 수집: {len(links)}건")

            for link in links[:50]:  # 최대 50건
                try:
                    detail = fetch_detail(page, link)
                    if detail:
                        listings.append(detail)
                    time.sleep(1)
                except Exception as e:
                    print(f"상세 오류: {e}")
                    continue
        except Exception as e:
            print(f"목록 오류: {e}")
        finally:
            browser.close()
    return listings

def fetch_detail(page, url):
    """물건 상세 페이지 파싱"""
    import re
    page.goto(url, timeout=20000, wait_until="networkidle")
    time.sleep(1)
    text = page.inner_text("body")

    def has(kw): return kw in text
    def find(pattern): m = re.search(pattern, text); return m

    # 감정가
    apm = find(r'감정가[\s\n]*(\d[\d,억만원]+)')
    appraisal = parse_price(apm.group(1)) if apm else 0
    if not appraisal:
        return None

    # 기본 정보
    ptype = "다세대"
    if has("아파트"): ptype = "아파트"
    elif has("오피스텔"): ptype = "오피스텔"
    elif has("상가"): ptype = "상가"
    elif has("토지"): ptype = "토지"
    elif has("빌라"): ptype = "빌라"

    fm = find(r'유찰\s*(\d+)회')
    failed = int(fm.group(1)) if fm else 0

    # 주소
    addr_m = (find(r'서울[^\n]{5,60}호') or find(r'경기[^\n]{5,60}호') or
              find(r'인천[^\n]{5,60}호') or find(r'부산[^\n]{5,60}호'))
    address = addr_m.group(0).strip() if addr_m else ""

    # 사건번호
    case_m = find(r'(\d{4}타경\d+)')
    case_no = case_m.group(1) if case_m else ""

    # 최저가
    minm = find(r'최저가[\s\n]*(\d[\d,억만원]+)')
    min_price = parse_price(minm.group(1)) if minm else 0

    return {
        "url": url,
        "case_no": case_no,
        "address": address,
        "property_type": ptype,
        "appraisal": appraisal,
        "min_price": min_price,
        "failed_count": failed,
        "re_auction": has("재매각"),
        "inherited_rights": has("매수인이 인수") or has("인수함"),
        "lien_claim": has("유치권"),
        "legal_surface": has("법정지상권"),
        "rent_registration": has("임차권등기"),
        "senior_tenant": has("선순위임차인") or has("선순위 임차인"),
        "waved_resistance": has("대항력 포기") or has("대항력포기"),
        "requested_dividend": has("배당요구"),
        "occupant": "소유자" if (has("소유자") and has("점유")) else "임차인" if has("임차인") else "미상",
    }

# ── 이슈 생성 ─────────────────────────────────────────────────
def make_badge(score):
    if score >= 80: return "🟢"
    if score >= 60: return "🟡"
    return "🔴"

def build_issue(results, scanned, passed):
    today = datetime.now().strftime("%Y년 %m월 %d일")
    top3 = results[:3]
    alert = [r for r in results if r["score"] >= CONFIG["score_alert"]]

    lines = [
        f"## 🏠 수원지방법원 주간 경매 스크리닝",
        f"**실행일**: {today} | **스캔**: {scanned}건 | **조건 통과**: {passed}건 | **최고점수**: {results[0]['score'] if results else 0}점",
        f"**조건**: 예상낙찰가 2억 미만 · 경기도 수원 · 종합점수 순",
        "",
        "---",
        "",
    ]

    # 80점 이상 전체
    if alert:
        lines.append(f"### ⭐ 80점 이상 물건 ({len(alert)}건)")
        lines.append("")
        for r in alert:
            lines += [
                f"#### {make_badge(r['score'])} {r['case_no']} — {r['score']}점 ({r['rec']})",
                f"- **주소**: {r['address']}",
                f"- **용도**: {r['property_type']} | **감정가**: {fmt_price(r['appraisal'])} | **예상낙찰가**: {fmt_price(r['bid'])} | **유찰**: {r['d']['failed_count']}회",
                f"- **권리위험도**: {r['rights']}점 | **명도위험도**: {r['evict']}점 | **수익성**: {r['profit_score']}점",
                f"- 🔗 [경매마당 보기]({r['url']})",
                "",
            ]
        lines.append("---")
        lines.append("")

    # Top 3
    lines.append(f"### 🏆 TOP 3 추천 물건")
    lines.append("")
    for i, r in enumerate(top3, 1):
        medal = ["🥇","🥈","🥉"][i-1]
        lines += [
            f"#### {medal} {i}위 — {r['case_no']} ({r['score']}점)",
            f"| 항목 | 내용 |",
            f"|---|---|",
            f"| 주소 | {r['address']} |",
            f"| 용도 | {r['property_type']} |",
            f"| 감정가 | {fmt_price(r['appraisal'])} |",
            f"| 예상 낙찰가 | **{fmt_price(r['bid'])}** |",
            f"| 유찰 | {r['d']['failed_count']}회 |",
            f"| 권리위험도 | {r['rights']}점 |",
            f"| 명도위험도 | {r['evict']}점 |",
            f"| 종합 점수 | **{r['score']}점** ({r['rec']}) |",
            f"",
            f"🔗 **[경매마당 상세보기]({r['url']})**",
            f"",
        ]

    lines += [
        "---",
        "",
        "### 📋 전체 통과 물건 목록",
        "",
        "| 순위 | 사건번호 | 주소 | 용도 | 감정가 | 예상낙찰가 | 점수 | 링크 |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for i, r in enumerate(results, 1):
        lines.append(
            f"| {i} | {r['case_no']} | {r['address'][:20]}... | {r['property_type']} | "
            f"{fmt_price(r['appraisal'])} | {fmt_price(r['bid'])} | "
            f"{make_badge(r['score'])} {r['score']}점 | "
            f"[보기]({r['url']}) |"
        )

    lines += [
        "",
        "---",
        f"*다음 스크리닝: 다음 주 금요일 오전 9시 자동 실행*",
    ]
    return "\n".join(lines)

def create_github_issue(title, body):
    repo = os.environ.get("GITHUB_REPO", "Duruduck/auction-analyzer")
    token = os.environ.get("GITHUB_TOKEN", "")
    owner, repo_name = repo.split("/")
    res = requests.post(
        f"https://api.github.com/repos/{owner}/{repo_name}/issues",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
        json={"title": title, "body": body, "labels": ["스크리닝"]},
    )
    if res.status_code == 201:
        print(f"이슈 생성: {res.json()['html_url']}")
    else:
        print(f"이슈 오류: {res.status_code} {res.text}")

# ── 메인 ─────────────────────────────────────────────────────
def main():
    print(f"[{datetime.now()}] 스크리닝 시작")

    # 물건 수집
    listings = fetch_listings(CONFIG["court_code"])
    print(f"수집 완료: {len(listings)}건")

    # 채점 + 필터
    scored = []
    for d in listings:
        score, bid, rs, es, ps = calc_final(d)
        if bid > CONFIG["max_bid_price"]:
            continue  # 2억 초과 제외
        rec = "입찰 추천" if score >= 80 else "현장 확인" if score >= 60 else "패스"
        scored.append({
            "d": d,
            "url": d["url"],
            "case_no": d["case_no"],
            "address": d["address"],
            "property_type": d["property_type"],
            "appraisal": d["appraisal"],
            "bid": bid,
            "score": score,
            "rights": rs,
            "evict": es,
            "profit_score": ps,
            "rec": rec,
        })

    # 점수 내림차순 정렬
    scored.sort(key=lambda x: x["score"], reverse=True)
    print(f"조건 통과: {len(scored)}건")

    if not scored:
        print("조건 통과 물건 없음 - 이슈 미생성")
        return

    today = datetime.now().strftime("%Y-%m-%d")
    title = f"[{today}] 수원지방법원 주간 스크리닝 — 통과 {len(scored)}건 / 최고 {scored[0]['score']}점"
    body = build_issue(scored, len(listings), len(scored))
    create_github_issue(title, body)

if __name__ == "__main__":
    main()
