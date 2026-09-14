import time
import json
import requests

from pathlib import Path
from datetime import datetime
from bs4 import BeautifulSoup

from gemini import analyze_article
from term_matcher import (load_terms, find_matched_terms, save_glossary_json)

# =====================================================
# 프로젝트 경로
# =====================================================

BASE_DIR = Path(__file__).resolve().parent.parent

NEWS_JSON_PATH = (
    BASE_DIR
    / "data"
    / "news.json"
)


# =====================================================
# 웹 요청 헤더
# =====================================================

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "Chrome/151 Safari/537.36"
    )
}


def get_news_list():
    url = "https://news.daum.net/economy"

    response = requests.get(
        url,
        headers=HEADERS,
        timeout=10
    )

    response.raise_for_status()

    response.encoding = "utf-8"

    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )

    news_items = []

    # 경제 주요뉴스 목록
    news_list = soup.select(
        "ul.list_newsheadline2 li"
    )

    for item in news_list:

        link = item.select_one(
            'a[href*="v.daum.net/v/"]'
        )

        title_tag = item.select_one(
            ".tit_txt"
        )

        if not link or not title_tag:
            continue

        news_items.append({
            "title": title_tag.get_text(
                " ",
                strip=True
            ),
            "url": link.get("href")
        })


    return news_items


def get_article_body(article_url):

    response = requests.get(
        article_url,
        headers=HEADERS,
        timeout=10
    )

    response.raise_for_status()

    response.encoding = "utf-8"

    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )

    paragraphs = soup.select(
        'section p[dmcf-ptype="general"]'
    )

    article_text = "\n".join(
        p.get_text(
            " ",
            strip=True
        )
        for p in paragraphs
    )

    return article_text


if __name__ == "__main__":

    terms = load_terms()
    save_glossary_json(terms)
    news_items = get_news_list()

    print(
        f"수집 기사 수: {len(news_items)}"
    )

    results = []

    for index, item in enumerate(
        news_items,
        start=1
    ):

        print()
        print("=" * 60)

        print(
            f"[{index}] {item['title']}"
        )

        print(
            "URL:",
            item["url"]
        )

        body = get_article_body(
            item["url"]
        )

        print(
            f"본문 글자 수: {len(body)}"
        )

        if not body:
            print("본문 수집 실패")

            time.sleep(2)
            continue

        matched = find_matched_terms(
            body,
            terms
        )

        print(
            f"매칭된 용어 수: {len(matched)}"
        )

        for matched_item in matched:
            print(
                "-",
                matched_item["term"],
                "/",
                matched_item["topic"]
            )

        matched_term_names = [
            matched_item["term"]
            for matched_item in matched
        ]

        try:

            result = analyze_article(
                item["title"],
                body,
                matched_term_names
            )

        except Exception as error:

            print(
                "Gemini 최종 실패:",
                error
            )

            time.sleep(2)
            continue

        print()
        print("[Gemini 결과]")

        print(
            "무슨 일이야?:",
            result["what_happened"]
        )

        print(
            "왜 중요해?:",
            result["why_important"]
        )

        print(
            "핵심 키워드:",
            result["keywords"]
        )

        # -----------------------------------------
        # JSON 저장용 결과 누적
        # -----------------------------------------

        results.append({
            "title": item["title"],
            "url": item["url"],
            "what_happened":
                result["what_happened"],
            "why_important":
                result["why_important"],
            "keywords":
                result["keywords"]
        })

        # 다음 기사 요청 전 2초 대기
        time.sleep(2)

    # =================================================
    # news.json 저장
    # =================================================

    output_data = {
        "date": datetime.now().strftime(
            "%Y-%m-%d"
        ),
        "news": results
    }

    with open(
        NEWS_JSON_PATH,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            output_data,
            file,
            ensure_ascii=False,
            indent=2
        )

    print()
    print("=" * 60)

    print(
        f"news.json 저장 완료: "
        f"{len(results)}건"
    )

    print(
        NEWS_JSON_PATH
    )