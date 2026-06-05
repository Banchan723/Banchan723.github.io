#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
validate_posts.py — 발행 전 글 검증기 (Hugo + Stack / SYSTEM-SPEC 절대규칙 강제)

검사 항목:
  - front matter 필수 필드 존재
  - categories / tags 가 data/taxonomy.yaml 안에 있는지
  - context 가 category 에 묶인 값과 일치하는지
  - level 허용값, slug / canonical_topic 영문 소문자 ASCII
  - title 따옴표 (YAML 콜론 사고 방지)
  - 글 파일 위치(content/post/<폴더>/index.md) 규칙
  - 중복: 같은 (canonical_topic + context) 글이 두 개 이상인지

오류 하나라도 있으면 exit 1 (Actions 빌드 차단).
사용: python scripts/validate_posts.py
"""

import os
import re
import sys
import datetime

try:
    import yaml
except ImportError:
    print("[FATAL] PyYAML 이 필요합니다. (Actions: pip install pyyaml)")
    sys.exit(2)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POSTS_DIR = os.path.join(ROOT, "content", "post")
TAXONOMY = os.path.join(ROOT, "data", "taxonomy.yaml")

REQUIRED = ["title", "date", "slug", "categories", "tags",
            "description", "canonical_topic", "context", "level"]
LEVELS = {"beginner", "intermediate", "advanced"}
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}")

errors = []


def load_taxonomy():
    with open(TAXONOMY, "r", encoding="utf-8") as f:
        tax = yaml.safe_load(f)
    contexts = set(tax.get("contexts", []))
    categories = tax.get("categories", {}) or {}
    return contexts, categories


def split_front_matter(text):
    # 줄 단위로 단독인 '---' 만 구분자로 인정 (본문 수평선·값 내 --- 오인 방지)
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return None, None
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return None, None
    raw = "\n".join(lines[1:end])
    try:
        return yaml.safe_load(raw), raw
    except yaml.YAMLError as e:
        return ("YAML_ERROR:" + str(e)), raw


def date_ok(v):
    # YAML이 날짜/시각 객체로 파싱했으면 통과
    if isinstance(v, (datetime.date, datetime.datetime)):
        return True
    s = str(v)
    # 문자열은 정확히 YYYY-MM-DD 이고 실제 존재하는 날짜여야 함
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        return False
    try:
        datetime.date.fromisoformat(s)
        return True
    except ValueError:
        return False


def as_date_str(v):
    if isinstance(v, (datetime.date, datetime.datetime)):
        return v.strftime("%Y-%m-%d")
    return str(v)


def validate_post(path, contexts, categories):
    rel = os.path.relpath(path, ROOT).replace("\\", "/")
    local = []

    # 위치 규칙: content/post/<폴더>/index.md
    if not rel.startswith("content/post/") or not rel.endswith("/index.md"):
        local.append("글은 content/post/<폴더>/index.md 형식이어야 함")

    with open(path, "r", encoding="utf-8") as f:
        text = f.read()

    data, raw = split_front_matter(text)
    if data is None:
        local.append("front matter(--- 블록)가 없음")
        return local, None
    if isinstance(data, str) and data.startswith("YAML_ERROR:"):
        local.append("front matter YAML 파싱 실패: " + data[len("YAML_ERROR:"):])
        return local, None

    for k in REQUIRED:
        if k not in data or data[k] in (None, "", []):
            local.append(f"필수 필드 누락/빈값: {k}")

    # title 따옴표
    title_line = next((ln for ln in raw.splitlines() if ln.strip().startswith("title:")), None)
    if title_line:
        val = title_line.split("title:", 1)[1].strip()
        if not ((val.startswith('"') and val.endswith('"')) or
                (val.startswith("'") and val.endswith("'"))):
            local.append("title 은 따옴표로 감싸야 함 (콜론 파싱 사고 방지)")

    # context
    ctx = data.get("context")
    if ctx is not None and ctx not in contexts:
        local.append(f"context '{ctx}' 가 taxonomy.contexts 에 없음 (허용: {sorted(contexts)})")

    # categories + tags
    cats = data.get("categories") or []
    if cats and not isinstance(cats, list):
        local.append("categories 는 리스트여야 함")
        cats = []
    allowed_tags = set()
    for cat in cats:
        if cat not in categories:
            local.append(f"category '{cat}' 가 taxonomy 에 없음 (허용: {sorted(categories)})")
        else:
            meta = categories[cat]
            allowed_tags |= set(meta.get("allowed_tags", []))
            # context ↔ category 일치
            if ctx is not None and meta.get("context") and meta["context"] != ctx:
                local.append(
                    f"context '{ctx}' 가 category '{cat}'의 context '{meta['context']}'와 불일치")

    tags = data.get("tags") or []
    if tags and not isinstance(tags, list):
        local.append("tags 는 리스트여야 함")
    elif cats:
        for t in tags:
            if t not in allowed_tags:
                local.append(f"tag '{t}' 가 category {cats} 의 allowed_tags 에 없음")

    # level
    if "level" in data and data.get("level") not in LEVELS:
        local.append(f"level '{data.get('level')}' 허용 안 됨 (허용: {sorted(LEVELS)})")

    # slug / canonical_topic
    for key in ("slug", "canonical_topic"):
        v = data.get(key)
        if v is not None and not SLUG_RE.match(str(v)):
            local.append(f"{key} '{v}' 는 영문 소문자/숫자/하이픈만 (한글·대문자·공백 금지)")

    # 날짜
    if "date" in data and data["date"] not in (None, ""):
        if not date_ok(data["date"]):
            local.append(f"date 는 실제 존재하는 YYYY-MM-DD 여야 함: {data['date']}")

    return local, data


def main():
    if not os.path.isdir(POSTS_DIR):
        print(f"[FATAL] content/post 폴더 없음: {POSTS_DIR}")
        sys.exit(2)

    contexts, categories = load_taxonomy()

    md_files = []
    for dirpath, _, filenames in os.walk(POSTS_DIR):
        for fn in filenames:
            if fn.endswith(".md"):
                md_files.append(os.path.join(dirpath, fn))

    dedup = {}
    slugs = {}
    checked = 0
    for path in sorted(md_files):
        rel = os.path.relpath(path, ROOT).replace("\\", "/")
        local, data = validate_post(path, contexts, categories)
        checked += 1
        if local:
            errors.append((rel, local))
        if data and data.get("canonical_topic") and data.get("context"):
            key = (str(data["canonical_topic"]), str(data["context"]))
            dedup.setdefault(key, []).append(rel)
        if data and data.get("slug"):
            slugs.setdefault(str(data["slug"]), []).append(rel)

    for key, paths in dedup.items():
        if len(paths) > 1:
            errors.append((
                f"중복 (canonical_topic={key[0]}, context={key[1]})",
                [f"같은 키의 글 {len(paths)}개: " + ", ".join(paths) +
                 "  → 신규가 아니라 기존 글 수정/추가여야 함"]))

    # slug 전역 중복 → /p/{slug}/ URL 충돌
    for slug, paths in slugs.items():
        if len(paths) > 1:
            errors.append((
                f"slug 중복 '{slug}'",
                [f"같은 slug 글 {len(paths)}개: " + ", ".join(paths) +
                 "  → URL(/p/{slug}/) 충돌. slug는 글마다 고유해야 함"]))

    print(f"검사한 글: {checked}개")
    if errors:
        print(f"\n[FAIL] 검증 실패 — 오류 {sum(len(e[1]) for e in errors)}건\n")
        for where, msgs in errors:
            print(f"  [{where}]")
            for m in msgs:
                print(f"     - {m}")
        sys.exit(1)
    print("[OK] 모든 글이 규칙을 통과했습니다.")
    sys.exit(0)


if __name__ == "__main__":
    main()
