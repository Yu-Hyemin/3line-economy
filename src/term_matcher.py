import re
import csv
import json
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
CSV_PATH = BASE_DIR / "data" / "terms.csv"


def load_terms():
    terms = []

    with open(
        CSV_PATH,
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as file:

        reader = csv.DictReader(file)

        for row in reader:

            original_term = row["용어"].strip()
            description = row["설명"].strip()
            topic = row["주제"].strip()

            if not original_term:
                continue

            # 괄호를 제거한 대표 용어
            clean_term = re.sub(
                r"\([^)]*\)|（[^）]*）",
                "",
                original_term
            ).strip()

            # 괄호 안 내용
            bracket_matches = re.findall(
                r"\((.*?)\)|（(.*?)）",
                original_term
            )

            english_aliases = []

            for match in bracket_matches:

                bracket_text = (
                    match[0] or match[1]
                ).strip()

                # 영문자가 포함된 괄호만 별칭으로 사용
                if re.search(
                    r"[A-Za-z]",
                    bracket_text
                ):
                    english_aliases.append(
                        bracket_text
                    )

            terms.append({
                "term": clean_term,
                "original_term": original_term,
                "english_aliases": english_aliases,
                "topic": topic,
                "description": description
            })

    return terms


def find_matched_terms(article_text, terms):

    matched = []
    seen = set()

    article_lower = article_text.lower()

    # 한글 용어의 띄어쓰기 차이를 비교하기 위한 버전
    article_no_space = re.sub(
        r"\s+",
        "",
        article_lower
    )

    for item in terms:

        term = item["term"]

        if len(term) < 2:
            continue

        is_matched = False

        term_lower = term.lower()

        # ---------------------------------
        # 1. 대표 용어
        # ---------------------------------

        # 영문자가 포함된 용어
        if re.search(r"[A-Za-z]", term):

            pattern = (
                r"(?<![A-Za-z0-9])"
                + re.escape(term_lower)
                + r"(?![A-Za-z0-9])"
            )

            if re.search(pattern, article_lower):
                is_matched = True

        # 한글/숫자 중심 용어
        # 한글/숫자 중심 용어
        else:

            # 띄어쓰기가 있는 용어는
            # "2차 시장", "2차시장" 둘 다 허용
            term_pattern = re.escape(term_lower).replace(
                r"\ ",
                r"\s*"
            )

            # 뒤에 붙을 수 있는 조사
            particle_pattern = (
                r"(?:은|는|이|가|을|를|의|에|에서|에게|께|"
                r"으로|로|와|과|도|만|부터|까지|보다|처럼)?"
            )

            pattern = (
                    r"(?<![가-힣A-Za-z0-9])"
                    + term_pattern
                    + particle_pattern
                    + r"(?![가-힣A-Za-z0-9])"
            )

            if re.search(
                    pattern,
                    article_lower
            ):
                is_matched = True

        # ---------------------------------
        # 2. 괄호 안 영문 별칭
        # ---------------------------------

        if not is_matched:

            for alias in item["english_aliases"]:

                alias_lower = alias.lower()

                pattern = (
                    r"(?<![A-Za-z0-9])"
                    + re.escape(alias_lower)
                    + r"(?![A-Za-z0-9])"
                )

                if re.search(
                    pattern,
                    article_lower
                ):
                    is_matched = True
                    break

        # ---------------------------------
        # 중복 제거
        # ---------------------------------

        if (
            is_matched
            and term not in seen
        ):
            matched.append(item)
            seen.add(term)

    return matched


def save_glossary_json(terms):

    base_dir = Path(__file__).resolve().parent.parent
    output_path = base_dir / "data" / "glossary.json"

    glossary = {}

    for item in terms:

        term = item.get("term")
        description = item.get("description")

        if not term or not description:
            continue

        glossary[term] = description

    with open(
        output_path,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            glossary,
            file,
            ensure_ascii=False,
            indent=2
        )

    print(
        f"glossary.json 저장 완료: {len(glossary)}개"
    )



if __name__ == "__main__":

    terms = load_terms()

    print(
        f"불러온 용어 수: {len(terms)}"
    )