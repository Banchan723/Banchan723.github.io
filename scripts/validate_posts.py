#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
validate_posts.py — 발행 전 글 검증기 (SYSTEM-SPEC 5절 절대규칙 강제)

검사 항목:
  - front matter 필수 필드 존재
  - category / context / tags 가 taxonomy.yml 안에 있는지
  - level / status 가 허용값인지
  - slug / canonical_topic 가 영문 소문자 ASCII 인지 (slug 불변 규칙의 기반)
  - title 이 따옴표로 감싸졌는지 (YAML 콜론 사고 방지)
  - 파일명이 YYYY-MM-DD-*.md 형식인지
  - 중복: 같은 (canonical_topic + context) 글이 두 개 이상인지

오류가 하나라도 있으면 exit code 1 (Actions 빌드/검증 실패).
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
POSTS_DIR = os.path.join(ROOT, "_posts")
TAXONOMY = os.path.join(ROOT, "_data", "taxonomy.yml")

REQUIRED = ["title", "date", "canonical_topic", "context",
            "category", "tags", "level", "status", "last_reviewed", "slug"]
LEVELS = {"beginner", "intermediate", "advanced"}
STATUSES = {"draft", "published", "needs-review", "revised"}
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
FILENAME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-.+\.md$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

errors = []
warnings = []


def load_taxonomy():
    with open(TAXONOMY, "r", encoding="utf-8") as f:
        tax = yaml.safe_load(f)
    contexts = set(tax.get("contexts", []))
    categories = tax.get("categories", {}) or {}
    return contexts, categories


def split_front_matter(text):
    """('---\\n...\\n---' 블록의 dict, raw front matter 문자열) 반환. 없으면 (None, None)."""
    if not text.startswith("---"):
        return None, None
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None, None
    raw = parts[1]
    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError as e:
        return "YAML_ERROR:" + str(e), raw
    return data, raw


def as_date_str(v):
    if isinstance(v, (datetime.date, datetime.datetime)):
        return v.strftime("%Y-%m-%d")
    return str(v)


def validate_post(path, contexts, categories):
    rel = os.path.relpath(path, ROOT)
    fname = os.path.basename(path)
    local = []

    if not FILENAME_RE.match(fname):
        local.append(f"파일명이 'YYYY-MM-DD-제목.md' 형식이 아님: {fname}")

    with open(path, "r", encoding="utf-8") as f:
        text = f.read()

    data, raw = split_front_matter(text)
    if data is None:
        local.append("front matter(--- 블록)가 없음")
        return local
    if isinstance(data, str) and data.startswith("YAML_ERROR:"):
        local.append("front matter YAML 파싱 실패: " + data[len("YAML_ERROR:"):])
        return local

    # 필수 필드
    for k in REQUIRED:
        if k not in data or data[k] in (None, "", []):
            local.append(f"필수 필드 누락/빈값: {k}")

    # title 따옴표 검사 (raw 에서)
    title_line = next((ln for ln in raw.splitlines() if ln.strip().startswith("title:")), None)
    if title_line:
        val = title_line.split("title:", 1)[1].strip()
        if not (val.startswith('"') and val.endswith('"')) and \
           not (val.startswith("'") and val.endswith("'")):
            local.append("title 은 따옴표로 감싸야 함 (콜론 파싱 사고 방지)")

    # context
    ctx = data.get("context")
    if ctx is not None and ctx not in contexts:
        local.append(f"context '{ctx}' 가 taxonomy.contexts 에 없음 (허용: {sorted(contexts)})")

    # category + tags
    cat = data.get("category")
    if cat is not None:
        if cat not in categories:
            local.append(f"category '{cat}' 가 taxonomy 에 없음 (허용: {sorted(categories)})")
        else:
            allowed = set(categories[cat].get("allowed_tags", []))
            tags = data.get("tags") or []
            if not isinstance(tags, list):
                local.append("tags 는 리스트여야 함")
            else:
                for t in tags:
                    if t not in allowed:
                        local.append(f"tag '{t}' 가 category '{cat}' 의 allowed_tags 에 없음")

    # level / status
    if data.get("level") not in LEVELS and "level" in data:
        local.append(f"level '{data.get('level')}' 허용 안 됨 (허용: {sorted(LEVELS)})")
    if data.get("status") not in STATUSES and "status" in data:
        local.append(f"status '{data.get('status')}' 허용 안 됨 (허용: {sorted(STATUSES)})")

    # slug / canonical_topic 형식
    for key in ("slug", "canonical_topic"):
        v = data.get(key)
        if v is not None and not SLUG_RE.match(str(v)):
            local.append(f"{key} '{v}' 는 영문 소문자/숫자/하이픈만 허용 (한글·대문자·공백 금지)")

    # 날짜 형식
    for key in ("date", "last_reviewed"):
        if key in data and data[key] not in (None, ""):
            if not DATE_RE.match(as_date_str(data[key])):
                local.append(f"{key} 는 YYYY-MM-DD 형식이어야 함: {data[key]}")

    return local, data


def main():
    if not os.path.isdir(POSTS_DIR):
        print(f"[FATAL] _posts 폴더 없음: {POSTS_DIR}")
        sys.exit(2)

    contexts, categories = load_taxonomy()

    md_files = []
    for dirpath, _, filenames in os.walk(POSTS_DIR):
        for fn in filenames:
            if fn.endswith(".md"):
                md_files.append(os.path.join(dirpath, fn))

    dedup = {}  # (canonical_topic, context) -> [rel paths]
    checked = 0

    for path in sorted(md_files):
        rel = os.path.relpath(path, ROOT)
        result = validate_post(path, contexts, categories)
        if isinstance(result, list):
            local, data = result, None
        else:
            local, data = result
        checked += 1
        if local:
            errors.append((rel, local))
        if data and data.get("canonical_topic") and data.get("context"):
            key = (str(data["canonical_topic"]), str(data["context"]))
            dedup.setdefault(key, []).append(rel)

    # 중복 검사
    for key, paths in dedup.items():
        if len(paths) > 1:
            errors.append((
                f"중복 (canonical_topic={key[0]}, context={key[1]})",
                [f"같은 키의 글이 {len(paths)}개: " + ", ".join(paths) +
                 "  → 신규가 아니라 기존 글 수정/추가여야 함 (SPEC 5절 규칙4)"]
            ))

    print(f"검사한 글: {checked}개")
    if errors:
        print(f"\n❌ 검증 실패 — 오류 {sum(len(e[1]) for e in errors)}건\n")
        for where, msgs in errors:
            print(f"  [{where}]")
            for m in msgs:
                print(f"     - {m}")
        sys.exit(1)
    else:
        print("✅ 모든 글이 규칙을 통과했습니다.")
        sys.exit(0)


if __name__ == "__main__":
    main()
