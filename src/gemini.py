import os
import json
import time
import requests

from pathlib import Path
from dotenv import load_dotenv


# =====================================================
# 1. 환경변수 불러오기
# =====================================================

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(
    BASE_DIR / ".env"
)

GEMINI_API_KEY = os.getenv(
    "GEMINI_API_KEY"
)


# =====================================================
# 2. 기사 분석
# =====================================================

def analyze_article(
    title,
    article_text,
    matched_terms
):

    if not GEMINI_API_KEY:
        raise ValueError(
            "Gemini API 키를 찾지 못했습니다."
        )

    gemini_url = (
        "https://generativelanguage.googleapis.com/v1beta/"
        "models/gemini-3.5-flash-lite:generateContent"
        f"?key={GEMINI_API_KEY}"
    )

    candidate_text = (
        ", ".join(matched_terms)
        if matched_terms
        else "없음"
    )

    # =================================================
    # 프롬프트
    # =================================================

    prompt = f"""
아래 뉴스의 제목과 본문을 읽고
'3줄경제' 카드에 들어갈 내용을 작성해주세요.


[기사 제목]

{title}


[기사 본문]

{article_text}


[기사 본문에서 경제용어 사전과 매칭된 용어]

{candidate_text}


[작업 1: 무슨 일이야?]

1. 기사에서 실제로 확인되는 핵심 사건이나 변화를 설명하세요.
2. 가장 중요한 내용을 1~2문장으로 작성하세요.
3. 기사에 없는 내용을 추가하지 마세요.
4. 너무 전문적인 표현은 피하고 쉽게 작성하세요.
5. 기사 내용을 단순히 줄여 쓰기보다,
   독자가 핵심 상황을 빠르게 이해할 수 있게 설명하세요.


[작업 2: 왜 중요해?]

1. 이 사건이 경제·사회·정책의 어떤 흐름을 보여주는지 설명하세요.
2. 독자가 "그래서 이 뉴스를 왜 알아두면 좋은가?"를
   이해할 수 있게 작성하세요.
3. 기사 속 결정을 내린 이유만 단순 반복하지 마세요.
4. "앞으로 지켜봐야 해요", "주목할 필요가 있어요"처럼
   미래 관전 포인트만 제시하는 문장으로 끝내지 마세요.
5. 기사 본문에서 확인할 수 있는 사실과 의미를 바탕으로 작성하세요.
6. 근거 없는 전망이나 추측은 하지 마세요.
7. 1~2문장으로 작성하세요.


[작업 3: 핵심 키워드]

1. 반드시 위의 '매칭된 용어' 안에서만 선택하세요.
2. 이 뉴스를 읽기 전에 알아두면
   기사 이해에 도움이 되는 용어를 최대 3개 선택하세요.
3. 단순히 기사에 등장했다는 이유만으로 선택하지 마세요.
4. 기관명이나 단순 등장 용어보다
   해당 뉴스의 핵심 내용이나 배경을 이해하는 데 필요한
   경제·사회·정책 개념을 우선하세요.
5. 후보 용어가 기사에 등장하더라도
   기사 이해에 별 도움이 되지 않는다면 선택하지 마세요.
6. 적절한 용어가 1개뿐이면 1개만 반환하세요.
7. 반드시 3개를 채울 필요는 없습니다.
8. 후보에 없는 새로운 용어를 만들지 마세요.
9. 적절한 용어가 없으면 빈 배열을 반환하세요.


[말투]

1. 뉴스 기사체를 그대로 따라 쓰지 마세요.
2. 어려운 표현은 일상적인 말로 풀어 설명하세요.
3. 독자에게 설명하듯 자연스럽게 작성하세요.
4. 지나치게 가볍거나 유행어를 사용하지 마세요.
5. "~했습니다", "~때문입니다" 같은 딱딱한 기사체보다
   "~했어요", "~라고 볼 수 있어요",
   "~에 영향을 줄 수 있어요"처럼
   이해하기 쉬운 설명체를 사용하세요.
6. 기사 내용을 과장하거나 단정하지 마세요.


반드시 아래 JSON 형식으로만 응답하세요.

{{
  "what_happened": "무슨 일이야?",
  "why_important": "왜 중요해?",
  "keywords": [
    "키워드1",
    "키워드2",
    "키워드3"
  ]
}}
"""

    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "text": prompt
                    }
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.1,
            "responseMimeType": "application/json"
        }
    }

    # =================================================
    # 3. Gemini 호출
    #    429 / 503 / 연결 오류 / timeout 재시도
    # =================================================

    max_retries = 3

    response = None


    for attempt in range(
        1,
        max_retries + 1
    ):

        try:

            print(
                f"Gemini 호출 시도: "
                f"{attempt}/{max_retries}"
            )

            response = requests.post(
                gemini_url,
                headers={
                    "Content-Type":
                    "application/json"
                },
                json=payload,
                timeout=60
            )

            print(
                "Gemini 응답코드:",
                response.status_code
            )

            # -----------------------------------------
            # 성공
            # -----------------------------------------

            if response.status_code == 200:
                break


            # -----------------------------------------
            # 429 / 503
            # -----------------------------------------

            if response.status_code in [
                429,
                503
            ]:

                if attempt < max_retries:

                    wait_time = (
                        attempt * 5
                    )

                    print(
                        f"Gemini "
                        f"{response.status_code} 오류 - "
                        f"{wait_time}초 후 재시도"
                    )

                    time.sleep(
                        wait_time
                    )

                    continue


            # -----------------------------------------
            # 기타 HTTP 오류
            # -----------------------------------------

            response.raise_for_status()


        except (
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout
        ) as error:

            if attempt < max_retries:

                wait_time = (
                    attempt * 5
                )

                print(
                    "Gemini 연결 오류 - "
                    f"{wait_time}초 후 재시도"
                )

                print(
                    "오류 내용:",
                    error
                )

                time.sleep(
                    wait_time
                )

                continue

            raise


    # =================================================
    # 4. 최종 실패
    # =================================================

    if (
        response is None
        or response.status_code != 200
    ):

        raise RuntimeError(
            "Gemini API 호출에 최종 실패했습니다."
        )


    # =================================================
    # 5. Gemini 응답 파싱
    # =================================================

    result = response.json()

    if (
        "candidates" not in result
        or not result["candidates"]
    ):

        raise RuntimeError(
            "Gemini 응답에 candidates가 없습니다."
        )


    raw_text = (
        result["candidates"][0]
        ["content"]
        ["parts"][0]
        ["text"]
        .strip()
    )


    try:

        parsed = json.loads(
            raw_text
        )

    except json.JSONDecodeError:

        print(
            "Gemini 원본 응답:"
        )

        print(
            raw_text
        )

        raise RuntimeError(
            "Gemini JSON 응답 파싱에 실패했습니다."
        )


    # =================================================
    # 6. 응답값 정리
    # =================================================

    what_happened = (
        parsed.get(
            "what_happened",
            ""
        )
        .strip()
    )

    why_important = (
        parsed.get(
            "why_important",
            ""
        )
        .strip()
    )

    keywords = parsed.get(
        "keywords",
        []
    )


    if not isinstance(
        keywords,
        list
    ):
        keywords = []


    # =================================================
    # 7. 키워드 검증
    #    Gemini가 후보 밖 단어를 만들 경우 제거
    # =================================================

    valid_keywords = []

    for keyword in keywords:

        if (
            keyword in matched_terms
            and keyword not in valid_keywords
        ):

            valid_keywords.append(
                keyword
            )


    valid_keywords = (
        valid_keywords[:3]
    )


    return {
        "what_happened":
            what_happened,

        "why_important":
            why_important,

        "keywords":
            valid_keywords
    }


# =====================================================
# 8. 단독 테스트
# =====================================================

if __name__ == "__main__":

    sample_title = (
        "한국은행, 기준금리 동결"
    )

    sample_article = """
    한국은행 금융통화위원회는 기준금리를
    현 수준에서 유지하기로 결정했다.

    물가 상승률이 둔화되고 있지만
    가계대출 증가와 부동산 시장 상황을
    추가로 지켜볼 필요가 있다고 설명했다.
    """

    sample_terms = [
        "기준금리",
        "물가",
        "가계대출"
    ]

    result = analyze_article(
        sample_title,
        sample_article,
        sample_terms
    )

    print()
    print(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2
        )
    )