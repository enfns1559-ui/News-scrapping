from __future__ import annotations

from datetime import date, timedelta
from email.utils import parsedate_to_datetime
from urllib.parse import quote_plus
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

from flask import Flask, render_template, request

app = Flask(__name__)

BUSINESS_RULES = {
    "엔지니어링/기술": ("engineering", "technology", "기술", "엔지니어", "ai", "인공지능", "소프트웨어", "반도체", "로봇", "연구개발", "r&d"),
    "에너지/환경": ("energy", "에너지", "환경", "탄소", "재생에너지", "배터리", "수소", "기후"),
    "건설/인프라": ("건설", "인프라", "플랜트", "철도", "도로", "항만", "건축"),
    "산업/제조": ("제조", "산업", "공장", "생산", "자동차", "조선", "공급망"),
    "금융/투자": ("금융", "투자", "펀드", "주식", "은행", "증권", "실적", "매출"),
    "정책/공공": ("정책", "정부", "국회", "규제", "공공", "법안", "지원사업"),
}
FIELD_RULES = {
    "인공지능": ("ai", "인공지능", "생성형", "머신러닝"),
    "반도체": ("반도체", "칩", "파운드리"),
    "모빌리티": ("자동차", "전기차", "모빌리티", "자율주행"),
    "에너지": ("에너지", "배터리", "수소", "태양광", "풍력"),
    "건설": ("건설", "플랜트", "인프라", "건축"),
    "바이오/헬스": ("바이오", "의료", "헬스", "제약", "임상"),
    "디지털/IT": ("소프트웨어", "클라우드", "데이터", "디지털", "플랫폼", "보안"),
}


def classify(text: str) -> tuple[str, str]:
    lowered = text.lower()
    business = next((label for label, words in BUSINESS_RULES.items() if any(w in lowered for w in words)), "산업/비즈니스")
    field = next((label for label, words in FIELD_RULES.items() if any(w in lowered for w in words)), "종합")
    return business, field


def search_news(keyword: str, start: date, end: date, limit: int) -> list[dict]:
    # Google News RSS accepts after/before query operators; exact date filtering is also applied below.
    query = f'{keyword} after:{start.isoformat()} before:{(end + timedelta(days=1)).isoformat()}'
    url = "https://news.google.com/rss/search?q=" + quote_plus(query) + "&hl=ko&gl=KR&ceid=KR:ko"
    req = Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; NewsSearch/1.0)"})
    with urlopen(req, timeout=15) as response:
        root = ET.fromstring(response.read())

    results = []
    for item in root.findall("./channel/item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        source = (item.findtext("source") or "Google News").strip()
        description = item.findtext("description") or ""
        pub_date = item.findtext("pubDate") or ""
        try:
            published = parsedate_to_datetime(pub_date).date()
        except (TypeError, ValueError):
            continue
        if not start <= published <= end:
            continue
        business, field = classify(f"{title} {description}")
        results.append({"title": title, "link": link, "source": source, "date": published.isoformat(), "business": business, "field": field})
        if len(results) >= limit:
            break
    return results


@app.route("/", methods=["GET", "POST"])
def index():
    today = date.today()
    keyword = request.values.get("keyword", "").strip()
    start_value = request.values.get("start_date", (today - timedelta(days=7)).isoformat())
    end_value = request.values.get("end_date", today.isoformat())
    try:
        start, end = date.fromisoformat(start_value), date.fromisoformat(end_value)
        limit = max(10, min(30, int(request.values.get("limit", "10"))))
        if end < start:
            raise ValueError("종료일은 시작일보다 빠를 수 없습니다.")
    except ValueError as exc:
        return render_template("index.html", keyword=keyword, start_date=start_value, end_date=end_value, limit=10, results=[], error=str(exc), searched=False), 400

    results, error, searched = [], None, False
    if request.method == "POST":
        searched = True
        if not keyword:
            error = "검색할 키워드를 입력해 주세요."
        else:
            try:
                results = search_news(keyword, start, end, limit)
            except Exception as exc:
                app.logger.exception("News search failed")
                error = "뉴스를 가져오지 못했습니다. 잠시 후 다시 시도해 주세요. (네트워크 연결을 확인해 주세요.)"
    return render_template("index.html", keyword=keyword, start_date=start_value, end_date=end_value, limit=limit, results=results, error=error, searched=searched)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
