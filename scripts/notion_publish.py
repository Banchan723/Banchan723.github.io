#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
notion_publish.py — 노션 "학습 기록" DB → Hugo 블로그 자동발행 (CI 전용, LLM 없음)

동작 요약 (SYSTEM-SPEC 4-1·5·6·9, NOTION-DB 참고):
  1) Notion REST API(api.notion.com)로 상태=발행준비 행을 폴링한다.
  2) 처리 시작 직전 그 행을 상태=처리중으로 PATCH 한다 (중복발행 락).
  3) 페이지 본문 블록을 GET 하고(100개 단위 pagination), "블로그 본문" 섹션의
     코드블록에서 마크다운을 RAW 로 추출한다.
       - BLOG_MD_BEGIN / BLOG_MD_END 마커가 있으면 그 사이 코드블록.
       - 없으면 "블로그 본문" 헤딩 다음의 첫 code 블록.
       - 코드블록 rich_text 가 2000자 단위로 쪼개져 있으면 모두 이어붙인다.
       - 노션 → 마크다운 변환은 하지 않는다 (규칙 7: 변환 없이 그대로).
  4) DB 속성에서 front matter 를 조립한다 (validate_posts.py 계약과 일치).
       - 난이도→level, context→categories(taxonomy.yaml), 매체→modality.
       - 제목은 항상 따옴표 처리.
  5) 안전 검사:
       - 본문에 이미지/외부 첨부 블록이 있으면 발행하지 않고 발행실패 처리
         (v1 은 텍스트 전용 — "이미지 포함 — 집에서 처리").
       - 위험 콘텐츠(script/iframe 등) 스캔, 있으면 발행실패.
  6) 파일 작성:
       - 처리방식=기존글추가 → content/post/{slug}/index.md 본문 끝에
         '## 추가 학습 (YYYY-MM-DD)' + 추출 본문 append (멱등: 동일 내용이면 skip).
       - 그 외(신규) → content/post/{slug}/index.md 신규 작성 (멱등).
  7) 상태 마감:
       - 성공 → 발행완료 + 발행일 + 발행URL(+발행커밋 placeholder).
       - 실패 → 발행실패 + 오류요약. 본문 자동수정은 절대 하지 않는다 (규칙 9).

환경변수: NOTION_TOKEN, NOTION_DB_ID. (CI Secrets 로만 주입, 로그 노출 금지.)

자기검증 한계: 이 스크립트는 형식·추적성만 본다. 사실성·이해도는 검증하지 않는다.
"""

import os
import re
import sys
import time
import datetime

try:
    import requests
except ImportError:  # pragma: no cover - CI 에서 pip install requests
    print("[FATAL] requests 가 필요합니다. (Actions: pip install requests)")
    sys.exit(2)

try:
    import yaml
except ImportError:  # pragma: no cover
    print("[FATAL] PyYAML 이 필요합니다. (Actions: pip install pyyaml)")
    sys.exit(2)


# ----------------------------------------------------------------------------
# 설정 / 상수
# ----------------------------------------------------------------------------

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POSTS_DIR = os.path.join(ROOT, "content", "post")
TAXONOMY = os.path.join(ROOT, "data", "taxonomy.yaml")

NOTION_API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"

# 사이트 베이스 (SYSTEM-SPEC: 라이브 URL, /p/{slug}/)
SITE_BASE = "https://banchan723.github.io"

# 노션 속성명 (한글 그대로)
P_TITLE = "제목"
P_CANONICAL = "canonical_topic"
P_CONTEXT = "context"
P_MEDIA = "매체"
P_TAGS = "태그"
P_LEVEL = "난이도"
P_SLUG = "slug"
P_DESC = "description"
P_STATUS = "상태"
P_MODE = "처리방식"
P_PUBDATE = "발행일"
P_COMMIT = "발행커밋"
P_URL = "발행URL"
P_PASS = "통과근거"
P_ERROR = "오류요약"

# 상태값
ST_READY = "발행준비"
ST_PROCESSING = "처리중"
ST_DONE = "발행완료"
ST_FAILED = "발행실패"

# 난이도 → level
LEVEL_MAP = {
    "입문": "beginner",
    "기초": "beginner",
    "중급": "intermediate",
    "고급": "advanced",
}

# 본문에 절대 들어오면 안 되는 위험 패턴 (대소문자 무시)
# HTML 엔티티 인코딩 변형(&lt;script&gt;, java&#x73;cript:)과 핸들러 공백도 잡는다.
DANGER_PATTERNS = [
    re.compile(r"<\s*script\b", re.IGNORECASE),
    re.compile(r"</\s*script\s*>", re.IGNORECASE),
    re.compile(r"<\s*iframe\b", re.IGNORECASE),
    re.compile(r"<\s*object\b", re.IGNORECASE),
    re.compile(r"<\s*embed\b", re.IGNORECASE),
    re.compile(r"javascript\s*:", re.IGNORECASE),
    # onXxx= 인라인 핸들러: = 앞뒤 공백 허용, 따옴표 없는 형태도(onXxx=alert) 잡음
    re.compile(r"\bon\w+\s*=", re.IGNORECASE),
    # HTML 엔티티로 인코딩한 < > (예: &lt;script&gt;, &lt;iframe ...)
    re.compile(r"&lt;\s*/?\s*(script|iframe|object|embed)\b", re.IGNORECASE),
    # 엔티티로 난독화한 javascript: 스킴 (예: java&#x73;cript:, &#106;avascript:).
    # 'javascript:' 처럼 글자 또는 HTML 숫자/16진 엔티티가 이어지다 콜론으로
    # 끝나는 토큰 중, 엔티티가 최소 1회 끼어 있는 경우만(평범한 'javascript:'는
    # 위의 javascript\s*: 패턴이 이미 잡으므로 여기선 난독화형 전용).
    # 'jscript' 류 짧은 토큰까지 닿도록 글자/엔티티 조각 4개 이상 + 엔티티 1회 요구.
    re.compile(
        r"(?:[a-z]|&#x?[0-9a-f]+;?){0,12}"   # 앞쪽 글자/엔티티
        r"&#x?[0-9a-f]+;?"                    # 엔티티 최소 1회
        r"(?:[a-z]|&#x?[0-9a-f]+;?){0,12}"   # 뒤쪽 글자/엔티티
        r"\s*:",                              # 콜론으로 끝
        re.IGNORECASE,
    ),
]

# 본문에 이미지/외부첨부가 있으면 v1 은 발행 보류 (집에서 처리)
IMAGE_BLOCK_TYPES = {"image", "file", "pdf", "video", "embed"}

# 마커
MARK_BEGIN = "BLOG_MD_BEGIN"
MARK_END = "BLOG_MD_END"
BLOG_HEADING = "블로그 본문"

# HTTP 재시도
MAX_RETRY = 5
BACKOFF_BASE = 1.5


class PublishError(Exception):
    """발행 불가 — 노션에 오류요약을 남기고 그 행만 건너뛴다. 본문 수정 없음."""


# ----------------------------------------------------------------------------
# Notion API 래퍼 (재시도 + 백오프)
# ----------------------------------------------------------------------------

def _headers(token):
    return {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


def _short_error(resp):
    """4xx 응답에서 Notion 에러코드/짧은 메시지만 뽑는다 (원문 전체 노출 회피).

    토큰·헤더는 절대 포함하지 않는다 (body 만, 그것도 축약).
    """
    try:
        data = resp.json()
        code = data.get("code", "")
        msg = (data.get("message", "") or "")[:150]
        return f"{code}: {msg}".strip(": ").strip() or "(no body)"
    except Exception:
        # JSON 이 아니면 본문 일부만 (짧게)
        return (resp.text or "")[:120].replace("\n", " ").strip() or "(no body)"


def notion_request(method, url, token, json_body=None):
    """429/5xx 에 지수 백오프 재시도. 그 외 4xx 는 즉시 실패."""
    last_exc = None
    for attempt in range(MAX_RETRY):
        try:
            resp = requests.request(
                method, url, headers=_headers(token), json=json_body, timeout=30
            )
        except requests.RequestException as e:
            last_exc = e
            wait = BACKOFF_BASE ** attempt
            print(f"[WARN] 네트워크 오류({e.__class__.__name__}), {wait:.1f}s 후 재시도 "
                  f"({attempt + 1}/{MAX_RETRY})")
            time.sleep(wait)
            continue

        if resp.status_code == 429 or 500 <= resp.status_code < 600:
            retry_after = resp.headers.get("Retry-After")
            wait = float(retry_after) if retry_after else BACKOFF_BASE ** attempt
            print(f"[WARN] Notion {resp.status_code}, {wait:.1f}s 후 재시도 "
                  f"({attempt + 1}/{MAX_RETRY})")
            time.sleep(wait)
            continue

        if resp.status_code >= 400:
            # 토큰/헤더는 절대 로그 금지. 본문 원문도 길게 노출하지 않고
            # 상태코드 + Notion 에러코드/짧은 메시지만 남긴다.
            raise RuntimeError(
                f"Notion API {method} 실패: {resp.status_code} {_short_error(resp)}"
            )
        return resp.json()

    if last_exc:
        raise RuntimeError(f"Notion API 재시도 소진: {last_exc}")
    raise RuntimeError("Notion API 재시도 소진(429/5xx)")


def query_ready_pages(token, db_id):
    """상태=발행준비 인 행을 모두 반환 (pagination)."""
    url = f"{NOTION_API}/databases/{db_id}/query"
    results = []
    cursor = None
    while True:
        body = {
            "filter": {"property": P_STATUS, "select": {"equals": ST_READY}},
            "page_size": 100,
        }
        if cursor:
            body["start_cursor"] = cursor
        data = notion_request("POST", url, token, body)
        results.extend(data.get("results", []))
        if data.get("has_more"):
            cursor = data.get("next_cursor")
        else:
            break
    return results


def get_block_children(token, page_id):
    """페이지 본문 블록을 모두 반환 (100개 단위 pagination)."""
    url = f"{NOTION_API}/blocks/{page_id}/children"
    blocks = []
    cursor = None
    while True:
        q = url + "?page_size=100"
        if cursor:
            q += f"&start_cursor={cursor}"
        data = notion_request("GET", q, token)
        blocks.extend(data.get("results", []))
        if data.get("has_more"):
            cursor = data.get("next_cursor")
        else:
            break
    return blocks


def get_page(token, page_id):
    """단일 페이지 GET (상태 재확인용)."""
    url = f"{NOTION_API}/pages/{page_id}"
    return notion_request("GET", url, token)


def update_page_props(token, page_id, properties):
    url = f"{NOTION_API}/pages/{page_id}"
    return notion_request("PATCH", url, token, {"properties": properties})


# ----------------------------------------------------------------------------
# 노션 속성 추출 헬퍼
# ----------------------------------------------------------------------------

def _rich_text_plain(rich):
    """rich_text 배열 → 평문 (2000자 분할 조각 이어붙이기 포함)."""
    if not rich:
        return ""
    return "".join(seg.get("plain_text", "") for seg in rich)


def get_prop(props, name):
    return props.get(name, {}) if props else {}


def prop_title(props, name):
    return _rich_text_plain(get_prop(props, name).get("title", [])).strip()


def prop_text(props, name):
    return _rich_text_plain(get_prop(props, name).get("rich_text", [])).strip()


def prop_select(props, name):
    sel = get_prop(props, name).get("select")
    return sel.get("name", "").strip() if sel else ""


def prop_multi(props, name):
    items = get_prop(props, name).get("multi_select", []) or []
    return [it.get("name", "").strip() for it in items if it.get("name")]


# ----------------------------------------------------------------------------
# 본문 추출
# ----------------------------------------------------------------------------

def block_plain_text(block):
    """텍스트 계열 블록의 평문."""
    btype = block.get("type")
    payload = block.get(btype, {})
    rich = payload.get("rich_text", [])
    return _rich_text_plain(rich)


def is_heading(block):
    return block.get("type") in ("heading_1", "heading_2", "heading_3")


def extract_blog_markdown(blocks):
    """
    "블로그 본문" 섹션의 코드블록에서 raw 마크다운을 추출.
    우선순위:
      1) BLOG_MD_BEGIN / BLOG_MD_END 마커 사이의 code 블록 (마커는 본문/주석/코드 어디든)
      2) "블로그 본문" 헤딩 다음에 나오는 첫 code 블록
    code 블록의 rich_text 2000자 분할은 _rich_text_plain 이 이미 이어붙인다.
    """
    # --- 1) 마커 기반: 마커가 보이는 구간 안의 code 블록을 모두 모은다 ---
    in_marker = False
    marker_seen = False
    marker_closed = False
    collected = []
    for block in blocks:
        text = block_plain_text(block)
        btype = block.get("type")

        if not in_marker and MARK_BEGIN in text:
            in_marker = True
            marker_seen = True
            # 같은 블록에 BEGIN/END가 함께 있고 code 블록이면 그 사이만 — 드문 케이스
            if btype == "code" and MARK_END in text:
                inner = _between_markers(text)
                if inner.strip():
                    collected.append(inner)
                in_marker = False
                marker_closed = True
                continue
            # BEGIN 과 본문이 같은 code 블록에 있는 경우: BEGIN 뒤 본문도 수집
            # (한 줄에 BEGIN만 있는 게 정상 경로지만, 본문이 붙어와도 잃지 않게)
            if btype == "code":
                inner = text.split(MARK_BEGIN, 1)[1]
                if inner.strip():
                    collected.append(inner)
            continue

        if in_marker:
            if MARK_END in text:
                in_marker = False
                marker_closed = True
                # END 가 code 블록 안에 있고 코드 일부면 잘라 담는다
                if btype == "code":
                    inner = text.split(MARK_END, 1)[0]
                    if inner.strip():
                        collected.append(inner)
                continue
            if btype == "code":
                collected.append(text)

    if marker_seen:
        # BEGIN 을 봤는데 END 를 끝까지 못 만남 → 엉뚱한 블록까지 발행 위험 → 명시 실패
        if not marker_closed:
            raise PublishError(
                f"{MARK_BEGIN} 마커는 있으나 {MARK_END} 마커를 찾지 못함 "
                f"(마커가 닫히지 않음 — 본문 작성 확인 필요)"
            )
        md = "\n".join(c for c in collected).strip("\n")
        if md.strip():
            return md
        # 마커는 있는데 코드블록이 비었음 → 작성 실수로 본다
        raise PublishError("BLOG_MD 마커는 있으나 그 사이 코드블록 본문이 비어 있음")

    # --- 2) 헤딩 기반: "블로그 본문" 헤딩 다음 첫 code 블록 ---
    after_heading = False
    for block in blocks:
        if is_heading(block):
            htext = block_plain_text(block)
            after_heading = (BLOG_HEADING in htext)
            continue
        if after_heading and block.get("type") == "code":
            md = block_plain_text(block).strip("\n")
            if md.strip():
                return md
            raise PublishError("'블로그 본문' 헤딩 다음 코드블록이 비어 있음")

    raise PublishError(
        "본문에서 블로그 마크다운을 찾지 못함 "
        "(BLOG_MD_BEGIN/END 마커나 '블로그 본문' 헤딩+코드블록 필요)"
    )


def _between_markers(text):
    if MARK_BEGIN in text and MARK_END in text:
        return text.split(MARK_BEGIN, 1)[1].split(MARK_END, 1)[0]
    return ""


def scan_blocks_for_media(blocks):
    """이미지/외부 첨부 블록이 있으면 그 타입 목록을 반환."""
    found = []
    for block in blocks:
        btype = block.get("type")
        if btype in IMAGE_BLOCK_TYPES:
            found.append(btype)
    return found


def scan_danger(markdown):
    """위험 콘텐츠 패턴 매칭. 있으면 첫 패턴 설명 반환, 없으면 None."""
    # 이미지 마크다운(![]()) 도 v1 텍스트 전용 정책상 차단 — 외부 URL 삽입 금지
    if re.search(r"!\[[^\]]*\]\([^)]+\)", markdown):
        return "본문에 이미지 마크다운(![](...)) 포함 — v1 텍스트 전용"
    for pat in DANGER_PATTERNS:
        if pat.search(markdown):
            return f"위험 콘텐츠 패턴 감지: {pat.pattern}"
    return None


# ----------------------------------------------------------------------------
# front matter 조립
# ----------------------------------------------------------------------------

def load_taxonomy():
    with open(TAXONOMY, "r", encoding="utf-8") as f:
        tax = yaml.safe_load(f)
    contexts = set(tax.get("contexts", []))
    categories = tax.get("categories", {}) or {}
    # context → 카테고리 표시명 역매핑
    ctx_to_cat = {}
    for cat_name, meta in categories.items():
        ctx = meta.get("context")
        if ctx:
            ctx_to_cat[ctx] = cat_name
    return contexts, categories, ctx_to_cat


def yaml_quote(s):
    """YAML 더블쿼트 단일라인 문자열로 안전 인코딩.

    백슬래시/큰따옴표뿐 아니라 개행·탭·기타 제어문자도 이스케이프해서
    front matter 한 줄이 깨지지 않게 한다. (단일 라인 필드 가정.)
    """
    out = []
    for ch in str(s):
        if ch == "\\":
            out.append("\\\\")
        elif ch == '"':
            out.append('\\"')
        elif ch == "\n":
            out.append("\\n")
        elif ch == "\r":
            out.append("\\r")
        elif ch == "\t":
            out.append("\\t")
        elif ord(ch) < 0x20 or ord(ch) == 0x7F:
            # 기타 제어문자 → YAML \xXX 이스케이프 (한 줄 유지)
            out.append("\\x{:02x}".format(ord(ch)))
        else:
            out.append(ch)
    return '"' + "".join(out) + '"'


def yaml_list(items):
    if not items:
        return "  []"
    return "\n".join(f"  - {yaml_quote(it)}" for it in items)


def today_seoul():
    """Asia/Seoul 기준 오늘 날짜 (CI 는 UTC 라 +9h)."""
    return (datetime.datetime.utcnow() + datetime.timedelta(hours=9)).date()


def build_front_matter(props, ctx_to_cat, pub_date):
    """DB 속성 → front matter dict + 직렬화 문자열. 실패하면 PublishError."""
    title = prop_title(props, P_TITLE)
    slug = prop_text(props, P_SLUG)
    canonical = prop_text(props, P_CANONICAL)
    context = prop_select(props, P_CONTEXT)
    description = prop_text(props, P_DESC)
    tags = prop_multi(props, P_TAGS)
    modality = prop_multi(props, P_MEDIA)
    level_kr = prop_select(props, P_LEVEL)

    # 필수값 검사
    missing = []
    if not title:
        missing.append(P_TITLE)
    if not slug:
        missing.append(P_SLUG)
    if not canonical:
        missing.append(P_CANONICAL)
    if not context:
        missing.append(P_CONTEXT)
    if not description:
        missing.append(P_DESC)
    if not level_kr:
        missing.append(P_LEVEL)
    if not tags:
        missing.append(P_TAGS)
    if not modality:
        missing.append(P_MEDIA)
    if missing:
        raise PublishError(f"필수 속성 누락/빈값: {', '.join(missing)}")

    # context → categories
    if context not in ctx_to_cat:
        raise PublishError(f"context '{context}' 가 taxonomy 에 없음")
    categories = [ctx_to_cat[context]]

    # 난이도 → level
    level = LEVEL_MAP.get(level_kr)
    if not level:
        raise PublishError(f"난이도 '{level_kr}' → level 매핑 불가 (입문/기초/중급/고급)")

    # slug / canonical 형식 (validate_posts 와 동일 규칙)
    slug_re = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    if not slug_re.match(slug):
        raise PublishError(f"slug '{slug}' 는 영문 소문자/숫자/하이픈만 허용")
    if not slug_re.match(canonical):
        raise PublishError(f"canonical_topic '{canonical}' 는 영문 소문자/숫자/하이픈만 허용")

    fm_lines = [
        "---",
        f"title: {yaml_quote(title)}",
        f"date: {pub_date.isoformat()}",
        f"slug: {yaml_quote(slug)}",
        f"description: {yaml_quote(description)}",
        "categories:",
        yaml_list(categories),
        "tags:",
        yaml_list(tags),
        "modality:",
        yaml_list(modality),
        f"canonical_topic: {yaml_quote(canonical)}",
        f"context: {yaml_quote(context)}",
        f"level: {yaml_quote(level)}",
        "---",
    ]
    fm = "\n".join(fm_lines) + "\n"
    return {
        "title": title, "slug": slug, "canonical_topic": canonical,
        "context": context, "categories": categories, "tags": tags,
        "modality": modality, "level": level, "description": description,
    }, fm


# ----------------------------------------------------------------------------
# 파일 작성 (멱등)
# ----------------------------------------------------------------------------

def post_path(slug):
    return os.path.join(POSTS_DIR, slug, "index.md")


def write_new_post(slug, front_matter, body_md):
    """신규 글 작성. 이미 동일 내용이면 skip(멱등). 반환: 'written' | 'skip'."""
    path = post_path(slug)
    content = front_matter + "\n" + body_md.rstrip("\n") + "\n"
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            existing = f.read()
        if existing == content:
            return "skip"
        # 이미 다른 내용으로 존재 — 신규인데 충돌. 덮어쓰지 않고 실패.
        raise PublishError(
            f"신규 발행인데 content/post/{slug}/index.md 가 이미 다른 내용으로 존재 "
            f"(중복판정 누락 의심 — 처리방식 확인 필요)"
        )
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return "written"


def _extract_section(existing, section_header):
    """
    existing 본문에서 section_header('## 추가 학습 (DATE)') 로 시작하는 섹션의
    전체 텍스트(헤딩 ~ 다음 '## ' 헤딩 직전 또는 EOF)를 반환. 없으면 None.

    부분문자열이 아니라 줄 단위로 헤딩을 정확히 식별한다 (오탐 방지).
    """
    lines = existing.splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.strip() == section_header:
            start = i
            break
    if start is None:
        return None
    # 다음 '## ' (혹은 그 이상 상위) 헤딩 또는 EOF 까지가 이 섹션
    end = len(lines)
    for j in range(start + 1, len(lines)):
        if lines[j].startswith("## "):
            end = j
            break
    return "\n".join(lines[start:end]).strip("\n")


def append_to_post(slug, body_md, pub_date):
    """
    기존 글 본문 끝에 '## 추가 학습 (YYYY-MM-DD)' + body append.

    멱등성은 같은 날짜 추가 학습 섹션을 경계(다음 '## ' 헤딩)로 잘라
    블록 전체 동일성으로 판정한다 (부분문자열 비교 아님):
      - 같은 날짜 섹션이 없으면 → append
      - 있고 내용이 동일하면 → skip
      - 있는데 내용이 다르면 → 실패 (같은 날 중복추가 방지, 사람 판단 필요)
    반환: 'appended' | 'skip'.
    """
    path = post_path(slug)
    if not os.path.exists(path):
        raise PublishError(
            f"기존글추가인데 content/post/{slug}/index.md 가 없음 "
            f"(처리방식=신규여야 하거나 slug 오류)"
        )
    with open(path, "r", encoding="utf-8") as f:
        existing = f.read()

    section_header = f"## 추가 학습 ({pub_date.isoformat()})"
    block = section_header + "\n\n" + body_md.strip("\n")

    existing_section = _extract_section(existing, section_header)
    if existing_section is not None:
        if existing_section.strip() == block.strip():
            return "skip"
        raise PublishError(
            f"같은 날짜 추가 학습 섹션('{section_header}')이 이미 있으나 내용이 다름 "
            f"(같은 날 중복추가 방지 — 사람 확인 필요)"
        )

    new_content = existing.rstrip("\n") + "\n\n" + block + "\n"
    with open(path, "w", encoding="utf-8") as f:
        f.write(new_content)
    return "appended"


# ----------------------------------------------------------------------------
# 상태 마감 PATCH
# ----------------------------------------------------------------------------

def acquire_processing_lock(token, page_id):
    """
    상태 락 획득 (방어적 TOCTOU 축소).

    Notion 에는 조건부(CAS) PATCH 가 없으므로 완전 원자성은 불가.
    워크플로 concurrency 직렬화가 정상 경로지만, 방어로:
      1) PATCH 직전 페이지를 재 GET 해서 상태가 여전히 '발행준비'인지 확인
      2) 아니면(이미 다른 실행이 잡았거나 상태 변경) 락 미획득 → False
      3) '발행준비'면 '처리중'으로 PATCH → True
    경합 윈도는 좁아지지만 0 은 아님(외부 락 없이 Notion 만으론 한계).
    반환: 락 획득 성공 여부(bool).
    """
    page = get_page(token, page_id)
    props = page.get("properties", {})
    cur_status = prop_select(props, P_STATUS)
    if cur_status != ST_READY:
        print(f"[SKIP] 락 미획득: 현재 상태가 '{cur_status or '?'}' "
              f"(기대 '{ST_READY}') — 다른 실행이 선점했거나 상태 변경됨")
        return False

    update_page_props(token, page_id, {
        P_STATUS: {"select": {"name": ST_PROCESSING}},
    })
    return True


def set_done(token, page_id, slug, pub_date, commit_placeholder):
    url = f"{SITE_BASE}/p/{slug}/"
    props = {
        P_STATUS: {"select": {"name": ST_DONE}},
        P_PUBDATE: {"date": {"start": pub_date.isoformat()}},
        P_URL: {"url": url},
        P_COMMIT: {"rich_text": [{"text": {"content": commit_placeholder}}]},
    }
    update_page_props(token, page_id, props)


def set_failed(token, page_id, reason):
    reason = (reason or "")[:1900]  # 노션 rich_text 안전 길이
    props = {
        P_STATUS: {"select": {"name": ST_FAILED}},
        P_ERROR: {"rich_text": [{"text": {"content": reason}}]},
    }
    try:
        update_page_props(token, page_id, props)
    except Exception as e:  # 마감 PATCH 실패해도 전체 잡이 죽지 않도록
        print(f"[ERROR] 발행실패 상태 기록도 실패(page={page_id}): {e}")


# ----------------------------------------------------------------------------
# 한 행 처리
# ----------------------------------------------------------------------------

def process_page(token, page, ctx_to_cat):
    """단일 행 발행. 성공하면 'published'/'skip', 실패하면 PublishError."""
    page_id = page["id"]
    props = page.get("properties", {})
    title = prop_title(props, P_TITLE) or "(제목없음)"
    slug = prop_text(props, P_SLUG)
    mode = prop_select(props, P_MODE) or "신규"

    print(f"\n=== 처리 시작: '{title}' (slug={slug or '?'}, 처리방식={mode}) ===")

    # 락: 처리중으로 전환 (중복발행 방지). 재확인 후 PATCH (방어적).
    # 락 미획득(다른 실행 선점 등)이면 이 행은 건너뛴다.
    if not acquire_processing_lock(token, page_id):
        return "skip"

    pub_date = today_seoul()

    # 기존글추가 판정: 신규일 때만 front matter 전체 조립·필수검증을 한다.
    # '기존글추가'는 slug 로 기존 파일을 찾아 본문만 append (최소 속성만 요구).
    is_append = (mode == "기존글추가")

    if is_append:
        # 최소 속성만 요구: slug. (신규 메타 전부 요구하던 버그 수정)
        if not slug:
            raise PublishError(f"기존글추가인데 {P_SLUG} 가 비어 있음")
        # 기존 파일이 없으면 신규로 폴백 (front matter 필요) — 아래에서 분기
        if not os.path.exists(post_path(slug)):
            print(f"[INFO] 기존글추가지만 {slug}/index.md 가 없음 → 신규 발행으로 폴백")
            is_append = False

    if not is_append:
        # 신규(또는 폴백): front matter 조립 (속성 검증 포함)
        fm_data, front_matter = build_front_matter(props, ctx_to_cat, pub_date)
        slug = fm_data["slug"]

    # 본문 블록 가져오기 + 미디어/마크다운 추출
    blocks = get_block_children(token, page_id)

    media = scan_blocks_for_media(blocks)
    if media:
        raise PublishError(
            f"이미지 포함 — 집에서 처리 (감지된 블록: {', '.join(sorted(set(media)))})"
        )

    body_md = extract_blog_markdown(blocks)

    danger = scan_danger(body_md)
    if danger:
        raise PublishError(danger)

    # 파일 작성
    if is_append:
        result = append_to_post(slug, body_md, pub_date)
    else:
        result = write_new_post(slug, front_matter, body_md)

    # 발행커밋은 워크플로가 커밋 후 채우는 게 정확하지만,
    # 스크립트 단계에선 placeholder 를 남긴다 (규칙 8: 실제 마감은 커밋·URL).
    commit_placeholder = os.environ.get("GITHUB_SHA", "")[:7] or "pending"
    set_done(token, page_id, slug, pub_date, commit_placeholder)

    print(f"--- 완료: {result} → content/post/{slug}/index.md "
          f"(URL {SITE_BASE}/p/{slug}/)")
    return result


# ----------------------------------------------------------------------------
# main
# ----------------------------------------------------------------------------

def main():
    token = os.environ.get("NOTION_TOKEN")
    db_id = os.environ.get("NOTION_DB_ID")
    if not token or not db_id:
        # 시크릿 미설정 = 아직 셋업 전. cron이 매일 실패하지 않게 조용히 통과(no-op).
        print("[SKIP] NOTION_TOKEN / NOTION_DB_ID 미설정 — 발행 건너뜀(셋업 전).")
        sys.exit(0)

    if not os.path.isdir(POSTS_DIR):
        os.makedirs(POSTS_DIR, exist_ok=True)

    _, _, ctx_to_cat = load_taxonomy()

    try:
        pages = query_ready_pages(token, db_id)
    except Exception as e:
        print(f"[FATAL] 발행준비 행 조회 실패: {e}")
        sys.exit(1)

    if not pages:
        print("발행준비 상태의 행이 없습니다. 종료.")
        sys.exit(0)

    print(f"발행준비 행: {len(pages)}개")

    published = 0
    failed = 0
    skipped = 0
    for page in pages:
        page_id = page["id"]
        try:
            result = process_page(token, page, ctx_to_cat)
            if result == "skip":
                skipped += 1
            else:
                published += 1
        except PublishError as e:
            failed += 1
            print(f"[FAIL] 발행실패: {e}")
            set_failed(token, page_id, str(e))
        except Exception as e:
            # 예기치 못한 오류도 그 행만 실패 처리하고 다음 행 계속
            failed += 1
            print(f"[ERROR] 예기치 못한 오류: {e}")
            set_failed(token, page_id, f"예기치 못한 오류: {e}")

    print(f"\n요약: 발행 {published} / 멱등skip {skipped} / 실패 {failed}")

    # 실패가 있어도 정상 발행분은 커밋되어야 하므로 exit 0.
    # (검증·커밋은 워크플로의 다음 스텝이 담당. 형식 오류는 validate_posts 가 또 막는다.)
    sys.exit(0)


if __name__ == "__main__":
    main()
