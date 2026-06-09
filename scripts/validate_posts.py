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
  - readability(매체별) 프록시 (SYSTEM-SPEC 4-1 (5)):
      · 필수 섹션 존재 / 권고 섹션(WARN)
      · 매체(modality)별 증거 강제 (code/visual/video)
      · 이미지 alt 텍스트 누락 (FAIL)
      · 상투어 과다 / 긴 문장·문단 (WARN)

FAIL(오류)이 하나라도 있으면 exit 1 (Actions 빌드 차단).
WARN(경고)은 출력만 하고 빌드는 막지 않는다(참고용).
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

# ── readability(매체별) 검증용 상수 (SYSTEM-SPEC 4-1 (5)) ──────────────
MODALITIES = {"code", "visual", "video"}

# 출력 자리에 아직 실제 출력을 안 채운 placeholder 표식.
# 보통 인용블록 `> ⚠️ 직접 돌린 출력 채우기...` 형태. 이 표식만 있으면
# "출력 없음(미완성 = 발행 불가)"으로 본다.
PLACEHOLDER_MARK = "직접 돌린 출력 채우기"

# 필수 섹션: (헤딩 표시명, 매칭 키워드들) — 본문 어디든 하나라도 있으면 통과
# (누적 글 "## 추가 학습"도 같은 헤딩을 다시 쓰므로 "존재"로만 판정)
REQUIRED_SECTIONS = [
    ("## 이 글에서 이해할 것", ["이 글에서 이해할 것"]),
    ("## 읽기 전 최소 배경", ["읽기 전 최소 배경"]),
    ("## 확인한 증거", ["확인한 증거"]),
    ("## 그래서 이렇게 이해했다", ["그래서 이렇게 이해했다"]),
    ("## 아직 모르는 것", ["아직 모르는 것"]),
    ("## 확인 질문", ["확인 질문"]),
]
# 권고 섹션(없으면 WARN)
# "막힌 점/틀린 가설"은 선택(2026-06-07 정본 개정): 막힌 경험이 있으면 강력하나,
# 이미 아는 개념은 강한 증거(직접 돌린 출력+변형문제 통과+자기말 설명)로 대체 가능.
# 반슬롭은 "## 확인한 증거"(필수) + 매체별 출력 강제가 지킨다.
RECOMMENDED_SECTIONS = [
    ("## 내가 막혔던 점 / 틀린 가설", ["내가 막혔던 점", "틀린 가설"]),
    ("## 다른 예시에 적용해보기", ["다른 예시에 적용해보기"]),
]

# ── 새 구조(교육 레퍼런스) 검증용 ─────────────────────────────────────
# content_schema 마커로 점진 마이그레이션: 마커 있는 글만 새 6골격 규칙으로 검사,
# 없는 글은 기존 8섹션 규칙 유지(기존 6글 CI 안 깨짐). 6글 모두 이전되면 옛 규칙 제거.
SCHEMAS = {"reference-v1"}            # 허용되는 content_schema 값
# 새 필수 섹션(교육 레퍼런스 6골격) — 헤딩에 키워드 하나라도 있으면 통과
REQUIRED_SECTIONS_V2 = [
    ("## 개념 정의", ["개념", "정의"]),
    ("## 왜 필요한가", ["왜 필요", "필요한가"]),
    ("## 문법과 동작", ["문법", "동작"]),
    ("## 직접 확인한 예제", ["직접 확인", "확인한 예제"]),
    ("## 흔한 실수와 오해", ["실수", "오해"]),
    ("## 관련 토픽", ["관련 토픽", "다음 경계", "다음 토픽"]),
]
# topic_id(선택): 트리 노드 식별자. 점 구분 소문자/숫자/하이픈. 예) cpp.pointer.basic
TOPIC_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*(?:\.[a-z0-9]+(?:-[a-z0-9]+)*)*$")

CLICHES = ["쉽게 말해", "일반적으로", "중요합니다", "효율적입니다"]
CLICHE_LIMIT = 3          # 이 횟수 "이상"이면 WARN
MAX_SENTENCE_LEN = 120    # 한 문장 글자수 초과 → WARN
MAX_PARA_SENTENCES = 5    # 한 문단 문장수 초과 → WARN

# code 매체 '실행 출력' 판정: 출력 라벨 + 실제 값 (키워드만으론 가짜통과라 라벨문법으로 제한)
OUTPUT_LABEL_RE = re.compile(
    r"(직접\s*돌린\s*출력|실행\s*결과|출력|결과|에러|output|result|error)\s*[:：\-]\s*\S",
    re.IGNORECASE)

IMG_RE = re.compile(r"!\[(?P<alt>[^\]]*)\]\((?P<url>[^)]*)\)")
URL_RE = re.compile(r"https?://\S+")
HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s")
LIST_ITEM_RE = re.compile(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)")

errors = []
warnings = []


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


def split_body(text):
    """front matter 를 제외한 본문 마크다운만 반환."""
    lines = text.split("\n")
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                return "\n".join(lines[i + 1:])
    return text  # front matter 없으면 전체가 본문


def parse_fences(body):
    """본문을 (코드펜스 밖 텍스트, 코드펜스 블록 리스트, 펜스제거 줄목록)으로 나눈다.

    반환:
      prose_lines : 코드펜스 밖 줄들의 리스트 (산문 분석용)
      fences      : 각 코드블록의 (시작줄 idx, 내용 문자열) 리스트
    """
    lines = body.split("\n")
    prose_lines = []
    fences = []
    in_fence = False
    fence_marker = None
    cur = []
    cur_start = 0
    for idx, ln in enumerate(lines):
        stripped = ln.strip()
        is_fence = stripped.startswith("```") or stripped.startswith("~~~")
        if not in_fence and is_fence:
            in_fence = True
            fence_marker = stripped[:3]
            cur = []
            cur_start = idx
            continue
        if in_fence and is_fence and stripped.startswith(fence_marker):
            in_fence = False
            fences.append((cur_start, "\n".join(cur)))
            cur = []
            continue
        if in_fence:
            cur.append(ln)
        else:
            prose_lines.append(ln)
    if in_fence:  # 닫히지 않은 펜스 — 안전하게 닫힌 것으로 취급
        fences.append((cur_start, "\n".join(cur)))
    return prose_lines, fences


def section_index(body):
    """본문을 헤딩 단위 섹션으로 쪼갠다. {정규화 헤딩텍스트: 섹션 본문} dict 반환.

    헤딩 텍스트는 소문자/공백제거 없이 원문 유지(키워드 부분일치로 매칭).
    같은 헤딩이 여러 번이면(누적 글) 본문을 이어붙인다.
    """
    lines = body.split("\n")
    sections = {}
    cur_head = None
    buf = []
    in_fence = False
    fence_marker = None
    for ln in lines:
        stripped = ln.strip()
        is_fence = stripped.startswith("```") or stripped.startswith("~~~")
        if not in_fence and is_fence:
            in_fence = True
            fence_marker = stripped[:3]
        elif in_fence and is_fence and stripped.startswith(fence_marker):
            in_fence = False
        # 펜스 안의 '#' 는 헤딩이 아님
        if not in_fence and HEADING_RE.match(ln):
            if cur_head is not None:
                sections[cur_head] = sections.get(cur_head, "") + "\n" + "\n".join(buf)
            cur_head = stripped.lstrip("#").strip()
            buf = []
        else:
            buf.append(ln)
    if cur_head is not None:
        sections[cur_head] = sections.get(cur_head, "") + "\n" + "\n".join(buf)
    return sections


def find_section(sections, keywords):
    """헤딩 텍스트에 keywords 중 하나라도 들어간 섹션 본문을 합쳐 반환. 없으면 None."""
    found = []
    for head, content in sections.items():
        if any(kw in head for kw in keywords):
            found.append(content)
    if not found:
        return None
    return "\n".join(found)


def has_heading(sections, keywords):
    return any(any(kw in head for kw in keywords) for head in sections)


def section_with_children(body, keywords):
    """keywords 와 매칭되는 헤딩의 본문을 '하위 섹션까지 포함'해서 반환.

    section_index 는 ## 와 ### 를 평면 분할하므로, '확인한 증거(##)' 아래
    '### 코드1/코드2' 의 코드펜스·placeholder 가 부모 섹션에 안 잡힌다.
    출력 유무 판정은 그 하위까지 봐야 하므로, 여기서는 매칭 헤딩 레벨부터
    다음 '같은-or-상위 레벨' 헤딩 직전까지를 한 덩어리로 묶어 돌려준다.
    여러 번 매칭되면(누적 글) 이어붙인다. 없으면 None.
    """
    lines = body.split("\n")
    chunks = []
    in_fence = False
    fence_marker = None
    i = 0
    n = len(lines)
    while i < n:
        ln = lines[i]
        stripped = ln.strip()
        is_fence = stripped.startswith("```") or stripped.startswith("~~~")
        if not in_fence and is_fence:
            in_fence = True
            fence_marker = stripped[:3]
            i += 1
            continue
        if in_fence and is_fence and stripped.startswith(fence_marker):
            in_fence = False
            i += 1
            continue
        m = (not in_fence) and re.match(r"^(\s{0,3})(#{1,6})\s", ln)
        if m:
            level = len(m.group(2))
            head_text = stripped.lstrip("#").strip()
            if any(kw in head_text for kw in keywords):
                # 이 헤딩 다음 줄부터, 같은-or-상위 레벨 헤딩 직전까지 수집
                j = i + 1
                buf = []
                inner_fence = False
                inner_marker = None
                while j < n:
                    jln = lines[j]
                    jstr = jln.strip()
                    jfence = jstr.startswith("```") or jstr.startswith("~~~")
                    if not inner_fence and jfence:
                        inner_fence = True
                        inner_marker = jstr[:3]
                        buf.append(jln)
                        j += 1
                        continue
                    if inner_fence and jfence and jstr.startswith(inner_marker):
                        inner_fence = False
                        buf.append(jln)
                        j += 1
                        continue
                    if not inner_fence:
                        jm = re.match(r"^(\s{0,3})(#{1,6})\s", jln)
                        if jm and len(jm.group(2)) <= level:
                            break
                    buf.append(jln)
                    j += 1
                chunks.append("\n".join(buf))
                i = j
                continue
        i += 1
    if not chunks:
        return None
    return "\n".join(chunks)


def split_sentences(text):
    """한국어/영어 혼합 문장 대충 분리. 마침표·물음표·느낌표 기준.

    줄바꿈으로는 쪼개지 않는다(hard-wrap 한 문장을 여러 문장으로 오인 방지).
    호출 전에 hard-wrap 을 공백으로 합쳐 넘길 것.
    """
    parts = re.split(r"(?<=[.!?。！？])\s+", text)
    return [p.strip() for p in parts if p.strip()]


def prose_paragraphs(prose_lines):
    """코드펜스 밖 줄들을 '산문 문단' 리스트로 만든다.

    - 빈 줄로 문단 구분.
    - 헤딩·리스트·표(|...)·인용(>)·이미지전용 줄은 산문에서 제외.
    - 한 문단 안의 hard-wrap 줄들은 공백 하나로 합쳐 한 덩어리로(문장 오분리 방지).
    """
    paras = []
    buf = []

    def is_prose_line(l):
        s = l.strip()
        if not s:
            return False
        if HEADING_RE.match(l) or LIST_ITEM_RE.match(l):
            return False
        if s.startswith(">") or s.startswith("|"):
            return False
        if IMG_RE.fullmatch(s):  # 이미지 단독 줄
            return False
        return True

    def flush():
        if buf:
            paras.append(" ".join(buf))

    for ln in prose_lines:
        if ln.strip() == "":
            flush()
            buf = []
        elif is_prose_line(ln):
            buf.append(ln.strip())
        else:
            # 비산문 줄(헤딩/리스트 등)은 문단을 끊는다
            flush()
            buf = []
    flush()
    return [p for p in paras if p.strip()]


def validate_readability(data, body):
    """SYSTEM-SPEC 4-1 (5) readability 프록시. (fail_list, warn_list) 반환."""
    fail = []
    warn = []

    sections = section_index(body)
    prose_lines, fences = parse_fences(body)
    prose_text = "\n".join(prose_lines)

    # ── 1. 필수 섹션 존재 ────────────────────────────────────────────
    for label, kws in REQUIRED_SECTIONS:
        if not has_heading(sections, kws):
            fail.append(f"필수 섹션 누락: `{label}`")
    for label, kws in RECOMMENDED_SECTIONS:
        if not has_heading(sections, kws):
            warn.append(f"권고 섹션 없음: `{label}`")

    # 증거 섹션 본문 (매체 검증·재현단계 판정에 공통 사용)
    evidence = find_section(sections, ["확인한 증거"]) or ""
    ev_prose_lines, ev_fences = parse_fences(evidence)
    ev_imgs = [m for ln in ev_prose_lines for m in IMG_RE.finditer(ln)]

    # ── 3. 이미지 alt 텍스트 (산문, 즉 코드펜스 밖 이미지만) ─────────
    #   코드펜스 안의 ![...] 예시는 실제 렌더 이미지가 아니므로 제외.
    imgs = [m for ln in prose_lines for m in IMG_RE.finditer(ln)]
    for m in imgs:
        if not m.group("alt").strip():
            fail.append(f"이미지 alt 텍스트 없음: ![]({m.group('url').strip()})")

    # ── 2. 매체별 증거 강제 ──────────────────────────────────────────
    modality = data.get("modality") or []
    if isinstance(modality, str):
        modality = [modality]
    modality = [str(m).strip().lower() for m in modality]

    if "code" in modality:
        if fences:
            # 출력/결과 = "확인한 증거" 섹션 안에 코드펜스(출력블록)가 있거나
            # 결과로 보이는 산문 텍스트가 있어야. 섹션이 비면 FAIL.
            # 단, placeholder(아직 출력 안 채움)는 출력으로 치지 않는다 →
            # placeholder 뿐이면 출력 없음 = 발행 불가(FAIL).
            # 증거는 '확인한 증거' 의 하위 ### 섹션(코드1/코드2 등)까지 포함해 본다.
            # 출력 있음 신호(코드펜스 밖 산문에서, placeholder 아닌 줄):
            #   (a) 인용블록('> ...') 출력, 또는
            #   (b) '직접 돌린 출력: 10', '출력: ...', 'result: ...' 같은
            #       출력 라벨 + 실제 값 (라벨 문법으로 제한 — 키워드만으론 가짜통과).
            # (소스 코드펜스·인트로 서술은 출력으로 치지 않음.)
            ev_full = section_with_children(body, ["확인한 증거"]) or ""
            ev_full_prose, _ = parse_fences(ev_full)

            def _is_real_output(line):
                s = line.strip()
                if not s or PLACEHOLDER_MARK in line:
                    return False
                if s.startswith(">") and s.lstrip(">").strip():
                    return True                       # (a) 인용블록 출력
                return bool(OUTPUT_LABEL_RE.search(s))  # (b) 출력 라벨 + 값

            ev_has_output = any(_is_real_output(l) for l in ev_full_prose)
            if not has_heading(sections, ["확인한 증거"]) or not ev_has_output:
                fail.append(
                    "modality=code: 코드펜스는 있는데 `## 확인한 증거`에 "
                    "실행 출력/결과가 없음(placeholder는 출력으로 보지 않음)")
        else:
            # 코드펜스가 아예 없으면 code 매체로 볼 증거 자체가 없음
            fail.append("modality=code: 본문에 코드펜스(```)가 없음")

    if "visual" in modality:
        has_img = bool(imgs)
        # 재현 단계 = 증거 섹션 안에 리스트, 또는 이미지 외 설명 줄이 2줄 이상.
        ev_nonimg = [l for l in ev_prose_lines
                     if l.strip() and not IMG_RE.search(l)]
        has_steps = (any(LIST_ITEM_RE.match(l) for l in ev_prose_lines)
                     or len(ev_nonimg) >= 2)
        if not has_img:
            fail.append("modality=visual: 이미지 참조(![...](...))가 없음")
        if not has_heading(sections, ["확인한 증거"]) or not has_steps:
            fail.append(
                "modality=visual: `## 확인한 증거`에 재현 단계(리스트/설정값 텍스트)가 없음")

    if "video" in modality:
        # 출처 URL 은 본문 어디든(인트로 등 허용). 재현/변형 결과는 "확인한 증거"
        # 섹션 안의 코드펜스 또는 이미지여야(다른 섹션의 무관한 이미지로 통과 방지).
        has_url = bool(URL_RE.search(body))
        has_result = bool(ev_fences) or bool(ev_imgs)
        if not has_url:
            fail.append("modality=video: 출처 URL(http...)이 본문에 없음")
        if not has_result:
            fail.append(
                "modality=video: `## 확인한 증거`에 재현/변형 결과"
                "(코드펜스 또는 이미지)가 없음")

    # ── 4. 상투어 과다 (WARN) — 산문(코드펜스 밖)만 ──────────────────
    for cliche in CLICHES:
        n = prose_text.count(cliche)
        if n >= CLICHE_LIMIT:
            warn.append(f"상투어 '{cliche}' {n}회 (권장 {CLICHE_LIMIT}회 미만)")

    # ── 5. 문장 120자 / 문단 5문장 초과 (WARN) — 산문 문단만 ─────────
    paras = prose_paragraphs(prose_lines)
    long_sentences = 0
    long_paras = 0
    for para in paras:
        sents = split_sentences(para)
        if len(sents) > MAX_PARA_SENTENCES:
            long_paras += 1
        for sent in sents:
            if len(sent) > MAX_SENTENCE_LEN:
                long_sentences += 1
    if long_sentences:
        warn.append(f"한 문장 {MAX_SENTENCE_LEN}자 초과 {long_sentences}곳")
    if long_paras:
        warn.append(f"한 문단 {MAX_PARA_SENTENCES}문장 초과 {long_paras}곳")

    return fail, warn


def extract_verification_block(body):
    """본문 코드펜스 중 `verification:` 루트키를 가진 yaml 블록을 파싱해 반환.

    검증메타블록(설계도 4절)은 글 끝 yaml 코드펜스:
        ```yaml
        verification:
          checked_claims:
            - { claim: "...", evidence: "..." }
        unknowns:
          - "..."
        ```
    여러 개면 마지막 것. 못 찾거나 파싱 실패면 None.
    """
    _, fences = parse_fences(body)
    found = None
    for _start, content in fences:
        if "verification" not in content:
            continue
        try:
            d = yaml.safe_load(content)
        except yaml.YAMLError:
            continue
        if isinstance(d, dict) and "verification" in d:
            found = d  # 마지막 것으로 갱신
    return found


def validate_readability_v2(data, body):
    """새 구조(content_schema: reference-v1) 검증. (fail_list, warn_list) 반환.

    교육 레퍼런스 6골격 + 검증메타블록 + 매체별 증거(기존 로직 재사용).
    """
    fail = []
    warn = []

    sections = section_index(body)
    prose_lines, fences = parse_fences(body)
    prose_text = "\n".join(prose_lines)

    # ── 1. 6골격 필수 섹션 ───────────────────────────────────────────
    for label, kws in REQUIRED_SECTIONS_V2:
        if not has_heading(sections, kws):
            fail.append(f"필수 섹션 누락: `{label}`")

    # ── 2. 검증메타블록(verification/unknowns) ───────────────────────
    vblock = extract_verification_block(body)
    if vblock is None:
        fail.append(
            "검증메타블록 없음: 글 끝에 ```yaml 펜스로 "
            "`verification:`(checked_claims) + `unknowns:` 를 둬야 함")
    else:
        ver = vblock.get("verification") or {}
        claims = ver.get("checked_claims") if isinstance(ver, dict) else None
        if not claims or not isinstance(claims, list):
            fail.append("검증메타블록에 verification.checked_claims(주장↔증거)가 비어 있음")
        else:
            for i, c in enumerate(claims):
                if not isinstance(c, dict) or not c.get("claim") or not c.get("evidence"):
                    fail.append(f"checked_claims[{i}]에 claim 또는 evidence 누락")
        # unknowns: 비어 있으면 WARN(학습로그 정체성 — 보통 다음 경계가 있다. 강제는 안 함)
        unknowns = vblock.get("unknowns")
        if not unknowns:
            warn.append("검증메타블록 `unknowns`가 비어 있음 (정말 더 배울 게 없나? 보통 다음 경계가 있다)")

    # ── 3. 이미지 alt 텍스트 (산문, 코드펜스 밖) ─────────────────────
    imgs = [m for ln in prose_lines for m in IMG_RE.finditer(ln)]
    for m in imgs:
        if not m.group("alt").strip():
            fail.append(f"이미지 alt 텍스트 없음: ![]({m.group('url').strip()})")

    # ── 4. 매체별 증거 강제 (증거 섹션 = "직접 확인한 예제") ──────────
    #   기존 _is_real_output 로직 재사용. 옛 구조의 "확인한 증거" → 새 "직접 확인한 예제".
    modality = data.get("modality") or []
    if isinstance(modality, str):
        modality = [modality]
    modality = [str(m).strip().lower() for m in modality]
    EVIDENCE_KW = ["직접 확인", "확인한 예제"]
    ev_section = find_section(sections, EVIDENCE_KW) or ""
    ev_prose_lines, ev_fences = parse_fences(ev_section)
    ev_imgs = [m for ln in ev_prose_lines for m in IMG_RE.finditer(ln)]

    if "code" in modality:
        if fences:
            ev_full = section_with_children(body, EVIDENCE_KW) or ""
            ev_full_prose, _ = parse_fences(ev_full)

            def _is_real_output(line):
                s = line.strip()
                if not s or PLACEHOLDER_MARK in line:
                    return False
                if s.startswith(">") and s.lstrip(">").strip():
                    return True
                return bool(OUTPUT_LABEL_RE.search(s))

            ev_has_output = any(_is_real_output(l) for l in ev_full_prose)
            if not has_heading(sections, EVIDENCE_KW) or not ev_has_output:
                fail.append(
                    "modality=code: 코드펜스는 있는데 `## 직접 확인한 예제`에 "
                    "실행 출력/결과가 없음(placeholder는 출력으로 보지 않음)")
        else:
            fail.append("modality=code: 본문에 코드펜스(```)가 없음")

    if "visual" in modality:
        ev_nonimg = [l for l in ev_prose_lines
                     if l.strip() and not IMG_RE.search(l)]
        has_steps = (any(LIST_ITEM_RE.match(l) for l in ev_prose_lines)
                     or len(ev_nonimg) >= 2)
        if not imgs:
            fail.append("modality=visual: 이미지 참조(![...](...))가 없음")
        if not has_heading(sections, EVIDENCE_KW) or not has_steps:
            fail.append(
                "modality=visual: `## 직접 확인한 예제`에 재현 단계(리스트/설정값)가 없음")

    if "video" in modality:
        has_url = bool(URL_RE.search(body))
        has_result = bool(ev_fences) or bool(ev_imgs)
        if not has_url:
            fail.append("modality=video: 출처 URL(http...)이 본문에 없음")
        if not has_result:
            fail.append(
                "modality=video: `## 직접 확인한 예제`에 재현/변형 결과(코드펜스/이미지)가 없음")

    # ── 5. 상투어·긴 문장/문단 (WARN) — 기존과 동일 ──────────────────
    for cliche in CLICHES:
        n = prose_text.count(cliche)
        if n >= CLICHE_LIMIT:
            warn.append(f"상투어 '{cliche}' {n}회 (권장 {CLICHE_LIMIT}회 미만)")
    for para in prose_paragraphs(prose_lines):
        sents = split_sentences(para)
        if len(sents) > MAX_PARA_SENTENCES:
            warn.append(f"한 문단 {MAX_PARA_SENTENCES}문장 초과")
        for sent in sents:
            if len(sent) > MAX_SENTENCE_LEN:
                warn.append(f"한 문장 {MAX_SENTENCE_LEN}자 초과")

    return fail, warn


def validate_post(path, contexts, categories):
    rel = os.path.relpath(path, ROOT).replace("\\", "/")
    local = []
    warn = []

    # 위치 규칙: content/post/<폴더>/index.md
    if not rel.startswith("content/post/") or not rel.endswith("/index.md"):
        local.append("글은 content/post/<폴더>/index.md 형식이어야 함")

    with open(path, "r", encoding="utf-8") as f:
        text = f.read()

    data, raw = split_front_matter(text)
    if data is None:
        local.append("front matter(--- 블록)가 없음")
        return local, warn, None
    if isinstance(data, str) and data.startswith("YAML_ERROR:"):
        local.append("front matter YAML 파싱 실패: " + data[len("YAML_ERROR:"):])
        return local, warn, None

    # draft 글은 검증 대상에서 제외(Hugo 관례: draft 는 사이트·CI 에서 빠짐).
    # 통과로 카운트하지 않고 'skip' 으로 알린다.
    if data.get("draft") is True:
        return local, warn, "SKIP"

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

    # modality(매체) — 있으면 허용값만 (없으면 readability 매체검증은 건너뜀)
    modality = data.get("modality")
    if modality not in (None, "", []):
        mvals = modality if isinstance(modality, list) else [modality]
        for mv in mvals:
            if str(mv).strip().lower() not in MODALITIES:
                local.append(
                    f"modality '{mv}' 허용 안 됨 (허용: {sorted(MODALITIES)})")

    # content_schema(선택) — 새 구조 마커. 있으면 허용값만.
    schema = data.get("content_schema")
    if schema not in (None, "", []):
        if str(schema).strip() not in SCHEMAS:
            local.append(f"content_schema '{schema}' 허용 안 됨 (허용: {sorted(SCHEMAS)})")

    # topic_id(선택) — 트리 노드 식별자. 있으면 형식만 검사.
    tid = data.get("topic_id")
    if tid not in (None, "", []):
        if not TOPIC_ID_RE.match(str(tid)):
            local.append(
                f"topic_id '{tid}' 형식 오류 (점 구분 소문자/숫자/하이픈, 예: cpp.pointer.basic)")

    # ── readability(매체별) 검증 — content_schema 마커로 새/옛 규칙 분기 ──
    body = split_body(text)
    if str(schema).strip() == "reference-v1":
        r_fail, r_warn = validate_readability_v2(data, body)   # 새 6골격
    else:
        # 새 구조 후보 가드 (Codex 권고 — "위험한 누락" 방어):
        # 마커가 없는데 새 6골격 헤딩이 다수면, 새 구조로 쓰려다 검증메타블록을
        # 빠뜨려 옛 규칙으로 새는 것이다. 옛 규칙을 우연히 통과해 슬쩍 발행되지
        # 않게 FAIL 시킨다. (옛 8섹션 글은 새 골격 키워드와 거의 안 겹쳐 오탐 적음.)
        sec = section_index(body)
        v2_hits = sum(1 for _lbl, kws in REQUIRED_SECTIONS_V2 if has_heading(sec, kws))
        if v2_hits >= 4:
            local.append(
                f"새 6골격 헤딩이 {v2_hits}개 감지되는데 content_schema/검증메타블록이 "
                "없음 — 새 구조 글이면 글 끝에 ```yaml `verification:` 블록을 넣어라"
                "(발행 파이프가 마커를 자동 주입). 옛 구조면 헤딩을 옛 8섹션으로.")
        r_fail, r_warn = validate_readability(data, body)      # 기존 8섹션
    local.extend(r_fail)
    warn.extend(r_warn)

    return local, warn, data


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
    skipped = []
    for path in sorted(md_files):
        rel = os.path.relpath(path, ROOT).replace("\\", "/")
        local, warn, data = validate_post(path, contexts, categories)
        if data == "SKIP":
            skipped.append(rel)
            continue
        checked += 1
        if local:
            errors.append((rel, local))
        if warn:
            warnings.append((rel, warn))
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
    if skipped:
        print(f"건너뛴 글(draft): {len(skipped)}개 — " + ", ".join(skipped))

    # WARN — 빌드는 막지 않음(참고용). FAIL 과 분리해 항상 먼저 출력.
    if warnings:
        print(f"\n[WARN] 경고 {sum(len(w[1]) for w in warnings)}건 (빌드 차단 안 함)\n")
        for where, msgs in warnings:
            print(f"  [{where}]")
            for m in msgs:
                print(f"     - {m}")

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
