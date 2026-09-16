import time
import json
import requests

from pathlib import Path
from datetime import datetime
from bs4 import BeautifulSoup

from gemini import analyze_article
from term_matcher import (
    load_terms,
    find_matched_terms,
    save_glossary_json
)


# =====================================================
# 프로젝트 경로
# =====================================================

BASE_DIR = Path(__file__).resolve().parent.parent

NEWS_JSON_PATH = (
    BASE_DIR
    / "data"
    / "news.json"
)

FAILURES_DIR = (
    BASE_DIR
    / "data"
    / "failures"
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


# =====================================================
# 재시도 설정
# =====================================================

RETRY_DELAYS = [5, 10]


# =====================================================
# 실패 코드
# =====================================================

FAIL_REASONS = {
    "ARTICLE_BODY_FAILED": "기사 본문 수집 실패",
    "SUMMARY_FAILED": "기사 요약 실패",
    "OTHER": "기타 실패"
}


# =====================================================
# 공통 웹 요청 함수
# =====================================================

def request_with_retry(url, label):

    max_attempts = 3
    last_error = None

    for attempt in range(
        1,
        max_attempts + 1
    ):

        try:

            response = requests.get(
                url,
                headers=HEADERS,
                timeout=10
            )

            response.raise_for_status()

            response.encoding = "utf-8"

            return response, None

        except requests.RequestException as error:

            last_error = error

            print(
                f"{label} 요청 실패 "
                f"({attempt}/{max_attempts}):",
                error
            )

            if attempt < max_attempts:

                wait_seconds = (
                    RETRY_DELAYS[
                        attempt - 1
                    ]
                )

                print(
                    f"{wait_seconds}초 후 "
                    f"재시도합니다."
                )

                time.sleep(
                    wait_seconds
                )

    return None, last_error


# =====================================================
# 뉴스 목록 수집
# =====================================================

def get_news_list():

    url = (
        "https://news.daum.net/economy"
    )

    response, error = request_with_retry(
        url,
        "뉴스 목록"
    )

    if response is None:

        raise RuntimeError(
            "뉴스 목록 수집에 최종 실패했습니다."
        ) from error

    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )

    news_items = []

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


# =====================================================
# 기사 본문 수집
# =====================================================

def get_article_body(article_url):

    response, error = request_with_retry(
        article_url,
        "기사 본문"
    )

    if response is None:
        return "", error

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

    return article_text, None


# =====================================================
# 실패 기록 생성
# =====================================================

def make_failed_item(
    item,
    stage,
    reason_code,
    detail=None
):

    failed_item = {
        "title": item["title"],
        "url": item["url"],
        "stage": stage,
        "reason_code": reason_code,
        "reason": FAIL_REASONS[
            reason_code
        ]
    }

    if detail:
        failed_item["detail"] = str(
            detail
        )

    return failed_item


# =====================================================
# MAIN
# =====================================================

if __name__ == "__main__":

    today = datetime.now().strftime(
        "%Y-%m-%d"
    )

    terms = load_terms()

    save_glossary_json(
        terms
    )

    news_items = get_news_list()

    print(
        f"수집 기사 수: "
        f"{len(news_items)}"
    )

    results = []
    failed_articles = []


    # =================================================
    # 기사별 처리
    # =================================================

    for index, item in enumerate(
        news_items,
        start=1
    ):

        print()
        print("=" * 60)

        print(
            f"[{index}] "
            f"{item['title']}"
        )

        print(
            "URL:",
            item["url"]
        )


        try:

            # -----------------------------------------
            # 기사 본문 수집
            # -----------------------------------------

            body, body_error = (
                get_article_body(
                    item["url"]
                )
            )

            print(
                f"본문 글자 수: "
                f"{len(body)}"
            )


            if not body:

                print(
                    "기사 본문 수집 실패 "
                    "- 해당 기사 제외"
                )

                failed_articles.append(
                    make_failed_item(
                        item=item,
                        stage="article_body",
                        reason_code=(
                            "ARTICLE_BODY_FAILED"
                        ),
                        detail=body_error
                    )
                )

                time.sleep(2)

                continue


            # -----------------------------------------
            # 경제용어 매칭
            # -----------------------------------------

            matched = find_matched_terms(
                body,
                terms
            )

            print(
                f"매칭된 용어 수: "
                f"{len(matched)}"
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


            # -----------------------------------------
            # Gemini 기사 요약
            # -----------------------------------------

            try:

                result = analyze_article(
                    item["title"],
                    body,
                    matched_term_names
                )

            except Exception as error:

                print(
                    "기사 요약 실패:",
                    error
                )

                failed_articles.append(
                    make_failed_item(
                        item=item,
                        stage="summary",
                        reason_code=(
                            "SUMMARY_FAILED"
                        ),
                        detail=error
                    )
                )

                time.sleep(2)

                continue


            # -----------------------------------------
            # Gemini 결과 확인
            # -----------------------------------------

            print()
            print("[Gemini 결과]")

            print(
                "무슨 일이야?:",
                result[
                    "what_happened"
                ]
            )

            print(
                "왜 중요해?:",
                result[
                    "why_important"
                ]
            )

            print(
                "핵심 키워드:",
                result[
                    "keywords"
                ]
            )


            # -----------------------------------------
            # 성공 기사 저장
            # -----------------------------------------

            results.append({
                "title":
                    item["title"],

                "url":
                    item["url"],

                "what_happened":
                    result[
                        "what_happened"
                    ],

                "why_important":
                    result[
                        "why_important"
                    ],

                "keywords":
                    result[
                        "keywords"
                    ]
            })


        except Exception as error:

            print(
                "기타 처리 실패:",
                error
            )

            failed_articles.append(
                make_failed_item(
                    item=item,
                    stage="other",
                    reason_code="OTHER",
                    detail=error
                )
            )


        # 다음 기사 요청 전 2초 대기
        time.sleep(2)


    # =================================================
    # news.json 저장
    # =================================================

    output_data = {
        "date": today,
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


    # =================================================
    # 실패 기록 저장
    # 실패가 있을 때만 날짜별 JSON 생성
    # =================================================

    if failed_articles:

        FAILURES_DIR.mkdir(
            parents=True,
            exist_ok=True
        )

        failed_json_path = (
            FAILURES_DIR
            / f"{today}.json"
        )

        failed_output_data = {
            "date": today,
            "failed_articles":
                failed_articles
        }

        with open(
            failed_json_path,
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(
                failed_output_data,
                file,
                ensure_ascii=False,
                indent=2
            )

        print(
            f"실패 기록 저장 완료: "
            f"{len(failed_articles)}건"
        )

        print(
            failed_json_path
        )

    else:

        print(
            "실패 기사 없음 "
            "- 실패 JSON 생성 안 함"
        )


    # =================================================
    # 결과 출력
    # =================================================

    print()
    print("=" * 60)

    print(
        f"news.json 저장 완료: "
        f"{len(results)}건"
    )

    print(
        NEWS_JSON_PATH
    )