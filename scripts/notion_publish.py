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
  7) 상태 마감 (3단계 — 거짓 발행완료 방지):
       - 성공한 행은 ._publish_state.json 에 기록만 하고 '처리중'으로 둔다.
         git push 성공 후 `--finalize` 모드가 발행완료 + 발행일 + 발행URL +
         발행커밋(실제 SHA)을 마감한다. push 실패 시 행은 처리중으로 남고,
         다음 실행의 고아 락 회수가 발행준비로 되돌려 재시도한다.
       - 실패 → 즉시 발행실패 + 오류요약. 본문 자동수정은 절대 하지 않는다 (규칙 9).
       - `--check-failures` 모드: 실패가 1건이라도 있으면 exit 1 → 워크플로가
         빨간불이 되어 GitHub 실패 알림이 간다 (조용한 실패 금지).
  8) 고아 락 회수: 이전 실행이 크래시하면 행이 '처리중'으로 영구 방치된다
     (발행준비 폴링에 영영 안 잡힘). 매 실행 시작 시 last_edited_time 이
     STALE_PROCESSING_HOURS 를 넘긴 처리중 행을 발행준비로 되돌린다.

실행 모드: (없음)=발행 / --finalize=push 후 마감 / --check-failures=실패 시 exit 1
환경변수: NOTION_TOKEN, NOTION_DB_ID, PUBLISH_COMMIT_SHA(finalize).
(CI Secrets 로만 주입, 로그 노출 금지.)

자기검증 한계: 이 스크립트는 형식·추적성만 본다. 사실성·이해도는 검증하지 않는다.
"""

import json
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

# 발행 스텝 → finalize/check 스텝 간 전달용 상태파일 (커밋 금지 — .gitignore)
STATE_FILE = os.path.join(ROOT, "._publish_state.json")

# 처리중 행이 이 시간을 넘기면 고아 락으로 보고 발행준비로 회수
# (정상 실행은 분 단위로 끝남. 같은 실행 안의 락은 절대 이보다 어릴 수 없음)
STALE_PROCESSING_HOURS = 2

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


def query_pages_by_status(token, db_id, status):
    """상태={status} 인 행을 모두 반환 (pagination)."""
    url = f"{NOTION_API}/databases/{db_id}/query"
    results = []
    cursor = None
    while True:
        body = {
            "filter": {"property": P_STATUS, "select": {"equals": status}},
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


def query_ready_pages(token, db_id):
    """상태=발행준비 인 행을 모두 반환."""
    return query_pages_by_status(token, db_id, ST_READY)


def is_stale_processing(page, now_utc, max_age_hours=STALE_PROCESSING_HOURS):
    """처리중 행이 고아 락인지 판정 — last_edited_time 이 임계보다 오래됐는가.

    락 PATCH 가 last_edited_time 을 갱신하므로, 진행 중인 실행의 락은 항상
    임계(시간 단위)보다 어리다. 타임스탬프가 없거나 못 읽으면 False(보수적)."""
    ts = page.get("last_edited_time")
    if not ts:
        return False
    try:
        edited = datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return False
    if edited.tzinfo is None:
        edited = edited.replace(tzinfo=datetime.timezone.utc)
    return (now_utc - edited) >= datetime.timedelta(hours=max_age_hours)


def recover_stale_processing(token, db_id):
    """고아 락 회수: 이전 실행이 크래시해 '처리중'으로 영구 방치된 행을
    발행준비로 되돌린다 (발행준비 폴링에 다시 잡히게).

    반환: (회수 건수, 실패 건수). 실패는 조용히 넘기지 않고 상태파일에 기록돼
    --check-failures 가 워크플로를 빨간불로 만든다 (침묵 실패 금지)."""
    try:
        pages = query_pages_by_status(token, db_id, ST_PROCESSING)
    except Exception as e:
        print(f"[ERROR] 처리중 행 조회 실패(고아 락 회수 불가): {e}")
        return 0, 1
    if not pages:
        return 0, 0
    now = datetime.datetime.now(datetime.timezone.utc)
    recovered = 0
    errors = 0
    for page in pages:
        if not is_stale_processing(page, now):
            continue  # 최근 락 — 다른 실행이 진행 중일 수 있으니 건드리지 않음
        title = prop_title(page.get("properties", {}), P_TITLE) or "(제목없음)"
        note = ("처리중 고아 락 자동 회수(이전 실행 비정상 종료 추정) — "
                "발행준비로 되돌려 재시도")
        try:
            update_page_props(token, page["id"], {
                P_STATUS: {"select": {"name": ST_READY}},
                P_ERROR: {"rich_text": [{"text": {"content": note}}]},
            })
            recovered += 1
            print(f"[RECOVER] 고아 락 회수: '{title}' 처리중 → 발행준비")
        except Exception as e:
            errors += 1
            print(f"[ERROR] 고아 락 회수 실패('{title}'): {e}")
    return recovered, errors


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


# 노션 코드블록 language → Hugo/chroma 친화 토큰
CODE_LANG_MAP = {
    "c++": "cpp",
    "c#": "csharp",
    "plain text": "",
    "plain_text": "",
    "": "",
}


def _rich_text_md(rich):
    """rich_text 배열 → 인라인 마크다운(코드/볼드/이탤릭/취소선/링크 보존).
    인라인 코드는 다른 강조와 겹치지 않게 백틱만 적용."""
    out = []
    for seg in rich or []:
        t = seg.get("plain_text", "")
        if t == "":
            continue
        ann = seg.get("annotations", {}) or {}
        href = seg.get("href")
        if ann.get("code"):
            t = f"`{t}`"
        else:
            if ann.get("bold"):
                t = f"**{t}**"
            if ann.get("italic"):
                t = f"*{t}*"
            if ann.get("strikethrough"):
                t = f"~~{t}~~"
        if href:
            t = f"[{t}]({href})"
        out.append(t)
    return "".join(out)


def render_block_md(block):
    """노션 블록 1개 → 마크다운 문자열 (지원: 헤딩/문단/코드/리스트/인용/구분선/이미지).
    바깥 코드블록 래퍼 없이 블록 구조를 그대로 마크다운으로 옮긴다(펜스 충돌 원천 제거)."""
    btype = block.get("type")
    payload = block.get(btype, {}) or {}
    rich = payload.get("rich_text", [])

    if btype == "heading_1":
        return "# " + _rich_text_md(rich)
    if btype == "heading_2":
        return "## " + _rich_text_md(rich)
    if btype == "heading_3":
        return "### " + _rich_text_md(rich)
    if btype == "paragraph":
        return _rich_text_md(rich)
    if btype == "code":
        lang = (payload.get("language") or "").lower()
        lang = CODE_LANG_MAP.get(lang, lang)
        body = _rich_text_plain(rich)   # 코드 내부는 raw (인라인 md 적용 안 함)
        return f"```{lang}\n{body}\n```"
    if btype == "bulleted_list_item":
        return "- " + _rich_text_md(rich)
    if btype == "numbered_list_item":
        return "1. " + _rich_text_md(rich)
    if btype == "quote":
        return "> " + _rich_text_md(rich)
    if btype == "divider":
        return "---"
    if btype == "image":
        src = payload.get("external") or payload.get("file") or {}
        url = src.get("url", "")
        cap = _rich_text_plain(payload.get("caption", []))
        return f"![{cap}]({url})"
    # 미지원 블록: 평문이라도 있으면 살리고, 없으면 건너뜀
    return _rich_text_md(rich)


def extract_blog_markdown(blocks):
    """
    BLOG_MD_BEGIN / BLOG_MD_END 마커 사이의 노션 블록을 마크다운으로 변환해 반환.
    (옛 방식인 '바깥 코드블록 래핑'은 노션 마크다운 import가 4백틱도 3백틱으로
     정규화해 안쪽 ``` 펜스와 충돌하므로 폐기. 이제 본문은 평범한 마크다운으로
     쓰고, 여기서 블록 구조를 그대로 변환한다.)
    마커가 없으면 "블로그 본문" 헤딩 뒤 ~ 페이지 끝을 변환(fallback).
    """
    # --- 1) 마커 기반 ---
    in_marker = False
    marker_seen = False
    marker_closed = False
    collected = []
    for block in blocks:
        text = block_plain_text(block)
        if not in_marker:
            if MARK_BEGIN in text:
                in_marker = True
                marker_seen = True
            continue
        if MARK_END in text:
            in_marker = False
            marker_closed = True
            break
        rendered = render_block_md(block)
        if rendered and rendered.strip():
            collected.append(rendered)

    if marker_seen:
        if not marker_closed:
            raise PublishError(
                f"{MARK_BEGIN} 마커는 있으나 {MARK_END} 마커를 찾지 못함 "
                f"(마커가 닫히지 않음 — 본문 작성 확인 필요)"
            )
        md = "\n\n".join(collected).strip("\n")
        if md.strip():
            return md
        raise PublishError("BLOG_MD 마커는 있으나 그 사이 본문이 비어 있음")

    # --- 2) 헤딩 기반 fallback: "블로그 본문" 헤딩 다음 ~ 끝 ---
    after_heading = False
    collected = []
    for block in blocks:
        if is_heading(block) and BLOG_HEADING in block_plain_text(block):
            after_heading = True
            continue
        if after_heading:
            rendered = render_block_md(block)
            if rendered and rendered.strip():
                collected.append(rendered)
    if after_heading:
        md = "\n\n".join(collected).strip("\n")
        if md.strip():
            return md
        raise PublishError("'블로그 본문' 헤딩 다음 본문이 비어 있음")

    raise PublishError(
        "본문에서 블로그 마크다운을 찾지 못함 "
        "(BLOG_MD_BEGIN/END 마커 또는 '블로그 본문' 헤딩 필요)"
    )


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


def has_verification_block(body_md):
    """본문에 유효한 검증메타블록(verification:/checked_claims yaml 펜스)이 있으면 True.

    새 6골격(교육 레퍼런스) 글은 검증메타블록을 반드시 갖는다(validate_posts 가 강제).
    따라서 이게 있으면 새 구조 글로 보고 content_schema=reference-v1 을 주입한다.
    앱 작성자는 본문만 쓰면 되고(노션 속성 추가 불필요), 파이프가 마커를 붙인다.
    """
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import validate_posts as vp
        return vp.extract_verification_block(body_md) is not None
    except Exception:
        return False


def inject_content_schema(front_matter, schema):
    """front matter 문자열의 닫는 '---' 바로 앞에 content_schema 줄을 끼운다.

    이미 content_schema 가 있으면 그대로 둔다(멱등). front matter 형식
    (맨 앞/끝이 '---')을 가정 — build_front_matter 가 만든 문자열에만 쓴다.
    """
    if re.search(r"(?m)^content_schema\s*:", front_matter):
        return front_matter
    lines = front_matter.split("\n")
    for i in range(len(lines) - 1, -1, -1):
        if lines[i].strip() == "---":
            lines.insert(i, f'content_schema: "{schema}"')
            break
    return "\n".join(lines)


# ----------------------------------------------------------------------------
# 파일 작성 (멱등)
# ----------------------------------------------------------------------------

def post_path(slug):
    return os.path.join(POSTS_DIR, slug, "index.md")


def _strip_fm_date(text):
    """front matter 의 date: 줄만 제거한 본문 반환 (크로스데이 재시도 비교용).

    push 는 됐는데 finalize 가 실패한 행을 다음날 재처리하면 pub_date 만 달라진다.
    그때 '이미 다른 내용으로 존재' 오류 대신 동일 글로 인식해 skip 하기 위함."""
    lines = text.splitlines()
    out = []
    fm_delims = 0
    for ln in lines:
        if ln.strip() == "---" and fm_delims < 2:
            fm_delims += 1
            out.append(ln)
            continue
        if fm_delims == 1 and ln.startswith("date:"):
            continue
        out.append(ln)
    return "\n".join(out)


def write_new_post(slug, front_matter, body_md):
    """신규 글 작성. 이미 동일 내용이면 skip(멱등). 반환: 'written' | 'skip'."""
    path = post_path(slug)
    content = front_matter + "\n" + body_md.rstrip("\n") + "\n"
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            existing = f.read()
        if existing == content:
            return "skip"
        if _strip_fm_date(existing) == _strip_fm_date(content):
            # 날짜만 다름 = 이전 실행이 push 까지 끝낸 글의 크로스데이 재시도.
            # 기존 파일(원래 발행일)을 보존하고 마감만 다시 한다.
            print(f"[INFO] {slug}: 날짜만 다른 동일 글 존재(이전 실행 발행분) → skip")
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

    # 크로스데이 재시도 방어: 같은 본문이 *다른 날짜의* 추가 학습 섹션으로 이미
    # 들어가 있으면(어제 push 후 finalize 실패 → 오늘 재처리) 이중 append 금지.
    for m in re.finditer(r"(?m)^## 추가 학습 \(\d{4}-\d{2}-\d{2}\)\s*$", existing):
        sec = _extract_section(existing, m.group(0).strip())
        if sec is None:
            continue
        sec_body = sec.split("\n", 1)[1] if "\n" in sec else ""
        if sec_body.strip() == body_md.strip():
            print(f"[INFO] {slug}: 동일 본문의 추가 학습 섹션이 이미 존재"
                  f"({m.group(0).strip()}) → skip")
            return "skip"

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


def validate_written_post(slug):
    """방금 쓴 글을 '발행완료' 마킹 전에 검증한다 (규칙 8: 형식 불량을 발행완료로
    만들지 않는다). validate_posts.validate_post 를 재사용. 반환: (ok, reason)."""
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import validate_posts as vp
        contexts, categories = vp.load_taxonomy()
        local, _warn, data = vp.validate_post(post_path(slug), contexts, categories)
        if data == "SKIP":
            return False, "draft 상태라 발행 불가 (draft 제거 필요)"
        if local:
            return False, "; ".join(local)
        return True, ""
    except Exception as e:
        return False, f"검증 실행 오류: {e}"


def remove_post(slug):
    """검증 실패한 신규 글 파일/번들을 지운다 (커밋되지 않게)."""
    path = post_path(slug)
    try:
        if os.path.exists(path):
            os.remove(path)
        d = os.path.dirname(path)
        if os.path.isdir(d) and not os.listdir(d):
            os.rmdir(d)
    except OSError as e:
        print(f"[WARN] 검증 실패 글 제거 중 오류({slug}): {e}")


# ----------------------------------------------------------------------------
# 한 행 처리
# ----------------------------------------------------------------------------

def process_page(token, page, ctx_to_cat):
    """단일 행 발행. 락 미획득이면 'lockskip', 성공하면 finalize 용 dict 반환
    (행은 '처리중'으로 남음 — push 후 --finalize 가 발행완료로 마감),
    실패하면 PublishError."""
    page_id = page["id"]
    props = page.get("properties", {})
    title = prop_title(props, P_TITLE) or "(제목없음)"
    slug = prop_text(props, P_SLUG)
    mode = prop_select(props, P_MODE) or "신규"

    print(f"\n=== 처리 시작: '{title}' (slug={slug or '?'}, 처리방식={mode}) ===")

    # 락: 처리중으로 전환 (중복발행 방지). 재확인 후 PATCH (방어적).
    # 락 미획득(다른 실행 선점 등)이면 이 행은 건너뛴다.
    if not acquire_processing_lock(token, page_id):
        return "lockskip"

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

    # 파일 작성 (append 는 검증 실패 시 원복하려고 원본을 백업)
    append_backup = None
    if is_append:
        _p = post_path(slug)
        if os.path.exists(_p):
            with open(_p, "r", encoding="utf-8") as f:
                append_backup = f.read()
        result = append_to_post(slug, body_md, pub_date)
    else:
        # 새 구조(검증메타블록 있음) 글이면 content_schema 마커 자동 주입 →
        # validate_posts 가 새 6골격 규칙으로 검사한다(없으면 옛 8섹션 규칙).
        if has_verification_block(body_md):
            front_matter = inject_content_schema(front_matter, "reference-v1")
            print("[INFO] 검증메타블록 감지 → content_schema: reference-v1 주입")
        result = write_new_post(slug, front_matter, body_md)

    # 발행완료 마킹 전 검증 (규칙 8 — 형식 불량을 발행완료로 만들지 않는다).
    # 실패면 발행실패로: 신규는 파일 제거, append 는 원본 복원 (working tree 오염·중복 append 방지).
    ok, reason = validate_written_post(slug)
    if not ok:
        if is_append:
            if append_backup is not None:
                with open(post_path(slug), "w", encoding="utf-8") as f:
                    f.write(append_backup)
        else:
            remove_post(slug)
        raise PublishError(f"작성된 글 검증 실패(발행 차단): {reason}")

    # 발행완료 마감은 여기서 하지 않는다 — git push 성공 후 --finalize 단계가
    # 실제 커밋 SHA 와 함께 마감한다 (push 실패 시 거짓 발행완료 방지).
    # 그때까지 행은 '처리중' (push 실패 시 다음 실행의 고아 락 회수가 재시도).
    print(f"--- 작성 완료: {result} → content/post/{slug}/index.md "
          f"(URL {SITE_BASE}/p/{slug}/ — 마감은 push 후 finalize)")
    return {
        "page_id": page_id,
        "slug": slug,
        "pub_date": pub_date.isoformat(),
        "result": result,
    }


# ----------------------------------------------------------------------------
# main
# ----------------------------------------------------------------------------

def write_state(state):
    # 실행 식별자 — 다른 실행의 잔존 상태파일을 finalize 가 신뢰하는 사고 방지
    state["run_id"] = os.environ.get("GITHUB_RUN_ID", "")
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def read_state():
    """상태파일 읽기. 없으면 None. CI 에선 같은 실행(run_id)의 파일만 신뢰."""
    if not os.path.exists(STATE_FILE):
        return None
    with open(STATE_FILE, "r", encoding="utf-8") as f:
        state = json.load(f)
    my_run = os.environ.get("GITHUB_RUN_ID", "")
    if my_run and state.get("run_id", "") != my_run:
        print(f"[ERROR] 상태파일의 run_id 가 현재 실행과 다름 "
              f"(잔존 파일 의심) — 무시함")
        return "STALE"
    return state


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

    # 고아 락 회수: 크래시로 '처리중'에 갇힌 행을 발행준비로 (아래 조회에 잡히게)
    _, recover_errors = recover_stale_processing(token, db_id)

    try:
        pages = query_ready_pages(token, db_id)
    except Exception as e:
        print(f"[FATAL] 발행준비 행 조회 실패: {e}")
        sys.exit(1)

    if not pages:
        print("발행준비 상태의 행이 없습니다. 종료.")
        write_state({"to_finalize": [], "published": 0, "failed": 0,
                     "skipped": 0, "recover_errors": recover_errors})
        sys.exit(0)

    print(f"발행준비 행: {len(pages)}개")

    to_finalize = []
    published = 0
    failed = 0
    skipped = 0
    for page in pages:
        page_id = page["id"]
        try:
            result = process_page(token, page, ctx_to_cat)
            if result == "lockskip":
                skipped += 1
            else:
                published += 1
                to_finalize.append(result)
        except PublishError as e:
            failed += 1
            print(f"[FAIL] 발행실패: {e}")
            set_failed(token, page_id, str(e))
        except Exception as e:
            # 예기치 못한 오류도 그 행만 실패 처리하고 다음 행 계속
            failed += 1
            print(f"[ERROR] 예기치 못한 오류: {e}")
            set_failed(token, page_id, f"예기치 못한 오류: {e}")

    write_state({
        "to_finalize": to_finalize,
        "published": published,
        "failed": failed,
        "skipped": skipped,
        "recover_errors": recover_errors,
    })
    print(f"\n요약: 작성 {published} / 락skip {skipped} / 실패 {failed}"
          f" (마감은 push 후 finalize 단계)")

    # 실패가 있어도 정상 발행분은 커밋되어야 하므로 여기선 exit 0.
    # 실패 알림은 마지막 --check-failures 스텝이 워크플로를 빨간불로 만들어 처리.
    sys.exit(0)


def run_finalize():
    """push 성공 후 마감: 상태파일의 성공 행들을 발행완료 + 실제 커밋 SHA 로 PATCH.

    여기 도달했다 = push 까지 성공. 마감 PATCH 가 실패한 행은 '처리중'으로 남고
    다음 실행의 고아 락 회수 → 재시도(멱등 작성이라 중복 없음)로 자연 복구된다."""
    token = os.environ.get("NOTION_TOKEN")
    if not token:
        print("[SKIP] NOTION_TOKEN 미설정 — finalize 건너뜀.")
        return 0
    state = read_state()
    if state is None:
        print("[SKIP] 상태파일 없음 — 발행 스텝이 안 돌았거나 행이 없었음.")
        return 0
    if state == "STALE":
        return 1  # 다른 실행의 잔존 파일 — 마감 거부 (행은 고아 락 회수가 처리)
    items = state.get("to_finalize", [])
    if not items:
        print("마감할 행 없음.")
        return 0

    sha = (os.environ.get("PUBLISH_COMMIT_SHA")
           or os.environ.get("GITHUB_SHA") or "")[:7] or "pending"
    if os.environ.get("PUBLISH_PUSHED") == "false":
        # 새 커밋 없이 마감 = 이전 실행이 push 까지 끝낸 행의 멱등 재시도
        print("[INFO] 이번 실행은 새 커밋 없음 — 기존 발행분 재마감(멱등 재시도)")
    errors = 0
    for it in items:
        slug = it.get("slug", "?")
        try:
            pub_date = datetime.date.fromisoformat(it["pub_date"])
            set_done(token, it["page_id"], slug, pub_date, sha)
            print(f"[DONE] 발행완료 마감: {slug} (발행커밋 {sha})")
        except Exception as e:
            errors += 1
            print(f"[ERROR] 마감 실패({slug}): {e}")
            # 빠른 자가복구 시도: 발행준비로 되돌려 다음 실행이 즉시 재시도하게
            # (작성은 멱등 + 크로스데이 방어 있음). 이것도 실패하면 처리중으로
            # 남고 2시간 뒤 고아 락 회수가 처리.
            try:
                update_page_props(token, it["page_id"], {
                    P_STATUS: {"select": {"name": ST_READY}},
                    P_ERROR: {"rich_text": [{"text": {"content":
                        "발행완료 마감 PATCH 실패 — 발행준비로 복귀, 다음 실행이 재시도"}}]},
                })
                print(f"        ({slug} 발행준비로 복귀 — 다음 실행이 재마감)")
            except Exception as e2:
                print(f"        (복귀도 실패: {e2} — 처리중으로 남음, "
                      f"고아 락 회수가 처리)")
    return 1 if errors else 0


def run_check_failures():
    """발행실패가 1건이라도 있으면 exit 1 — 워크플로를 빨간불로 만들어
    GitHub 실패 알림(메일)을 유도한다. 조용한 실패 금지."""
    state = read_state()
    if state is None:
        print("상태파일 없음 — 발행 스텝 미실행. 통과.")
        return 0
    if state == "STALE":
        return 1
    failed = int(state.get("failed", 0))
    recover_errors = int(state.get("recover_errors", 0))
    if failed > 0 or recover_errors > 0:
        print(f"[RED] 발행실패 {failed}건 / 고아 락 회수 실패 {recover_errors}건 — "
              f"노션 DB 의 발행실패·처리중 행을 확인하라. "
              f"(정상 발행분은 이미 커밋·마감됨. 이 빨간불은 알림용)")
        return 1
    print("발행실패 0건.")
    return 0


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode == "--finalize":
        sys.exit(run_finalize())
    elif mode == "--check-failures":
        sys.exit(run_check_failures())
    else:
        main()
