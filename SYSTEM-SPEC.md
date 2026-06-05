# 학습 블로그 자동발행 시스템 — 정본 설계서 (SYSTEM-SPEC)

> 이 문서가 시스템의 단일 정본이다. 구현·Cowork 발행·미래의 나(클로드) 모두 이 문서를 기준으로 한다.
> 스택: **Hugo + Stack 테마 + GitHub Pages**. (2026-06-06 Jekyll→Hugo 전환 완료.)
> 사용자: 프로그래밍 초보, Windows, 주제 = C++·언리얼·블렌더·Tripo 3D 등 계속 늘어남.

---

## 0. 한 줄 목표

사용자는 **공부와 노션 정리만** 한다. 나머지(글 작성·발행·목록 관리)는 AI(Cowork)가 한다. 어디서 공부했든 노션에 들어가면, 집 데스크탑에서 블로그로 자동 발행된다.

## 1. 아키텍처

```
[공부]  클로드 챗 앱 (모바일·데스크탑)  +  코드는 웹 컴파일러 / VS Code로 따로 실습
            │  핵심 이해를 노션에 정리
            ▼
[정리]  노션 학습 DB (만능 수신함)
            │  Cowork가 읽음
            ▼
[작성]  Cowork가 마크다운 글 생성 (taxonomy·front matter 규칙 준수)
            │  사용자 검토 (5체크박스)
            ▼
[발행]  git push → GitHub Actions가 검증 → Hugo 빌드 → Pages 배포
            │  발행 후 실제 URL 접속 확인
            ▼
[블로그]  banchan723.github.io  (다크 + 사이드바 + 카드 + 카테고리/태그/검색)
```

- 공부 = 챗 앱(어디서나). 발행 = 데스크탑 1곳(Cowork). 모바일은 git push 불가.
- 노션이 "공부 장소"와 "발행 장소"를 잇는 다리.

## 2. 기술 스택 결정

| 항목 | 결정 | 이유 |
|---|---|---|
| 정적 사이트 생성기 | **Hugo (extended)** | 빠름, Stack 테마 사용 |
| 테마 | **Stack** (CaiJimmy/hugo-theme-stack, 서브모듈) | 다크·사이드바·카드·태그칩·검색 기본 내장 (minyeamer 룩) |
| Hugo 버전 | **0.162.1 고정** (≥0.158 필수) | Stack v4가 0.158+ 요구. 0.157은 빌드 실패 |
| 빌드 | **GitHub Actions** (클라우드) | 로컬 Hugo 설치 불필요 |
| 학습 기록 | **노션 DB(표)** | 발행 상태 한눈에 |
| 발행 도구 | **Cowork** (데스크탑) | 노션 읽기 + 파일 + git push |

## 3. 폴더 구조 (repo)

```
banchan723.github.io/
  config/_default/
    hugo.toml         # 메인 설정 (baseURL, locale, buildFuture, languages)
    params.toml       # Stack 파라미터 (다크, 사이드바, 위젯)
    menu.toml         # 소셜 링크
  content/
    post/<slug>/index.md   # 글 (페이지 번들)
    page/about|archives|search/index.md  # 특수 페이지
  data/taxonomy.yaml  # 허용 카테고리·태그 사전 (검증 기준)
  layouts/_partials/footer/footer.html   # 푸터 크레딧 제거 override
  scripts/validate_posts.py              # 발행 전 검증기
  themes/hugo-theme-stack/               # Stack 테마 (git 서브모듈)
  .github/workflows/hugo.yml             # 검증 + 빌드 + 배포
  SYSTEM-SPEC.md / COWORK-PUBLISH.md / NOTION-DB.md / README.md
```

## 4. 글 front matter 스키마 (모든 글 공통, 절대 규칙)

`content/post/<slug>/index.md` 상단:

```yaml
---
title: "한글 제목 가능"          # 항상 따옴표 (콜론 사고 방지)
date: 2026-06-06
slug: "pointer-cpp"             # 영문 소문자. 한번 정하면 불변. URL = /p/{slug}/
description: "목록에 보일 한 줄 요약"
categories:                    # taxonomy.yaml 의 카테고리(표시명)만
  - "C++"
tags:                          # 해당 category 의 allowed_tags 안에서만
  - "포인터"
  - "메모리"
# --- 검증/중복판정용 커스텀 필드 (Stack 테마는 무시) ---
canonical_topic: "pointer"     # 개념 식별자(영문 소문자) — 중복판정 키①
context: "cpp"                 # 맥락 — 중복판정 키②
level: "beginner"             # beginner / intermediate / advanced
# image: "cover.png"           # 선택: 카드 커버(번들 내 파일)
---
```

**중복 판정 키 = `canonical_topic` + `context`.** 같은 키 → 같은 글(수정/추가), 다른 키 → 새 글.
예: `pointer`+`cpp` ≠ `pointer`+`unreal`.

## 5. 절대 규칙 (어기면 글 쌓일 때 터짐)

1. **slug 불변** — 최초 발행 후 변경 금지(주소 깨짐). 영문 소문자.
2. **categories·tags 는 `data/taxonomy.yaml` 에 있는 것만.** 새로 필요하면 사용자 승인 후 추가.
3. **context 는 category 에 묶인 값과 일치.** (검증기가 강제.)
4. **발행 전 중복 검색** — `canonical_topic`+`context`로 기존 글 검색 → 있으면 [신규/추가/수정] 선택.
5. **기존 글 "추가"는 하단에 `## 추가 학습 (날짜)` 섹션 append**, 원본 보존. 5회 넘으면 시리즈 분리.
6. **title 은 항상 따옴표.** 코드의 `{{ }}`는 Hugo도 충돌 가능 → 코드펜스로 감싸거나 `{{</* */>}}` 처리.
7. **발행 성공 = push + Actions 빌드 성공 + 실제 URL 접속 확인.** 셋 다 돼야 노션 "발행완료".
8. **발행 전 비밀정보·유료자료 스캔.**

## 6. 노션 학습 DB → front matter 매핑

노션 칼럼/본문 → Hugo front matter (자세한 건 NOTION-DB.md):

| 노션 | front matter |
|---|---|
| 제목 | title |
| canonical_topic | canonical_topic |
| context (cpp/unreal/blender/tripo) | context + categories |
| 난이도(입문/기초/중급) | level (beginner/intermediate/…) |
| 본문 "막힌 부분" | 글의 "## 내가 헷갈렸던 점" 섹션 (필수, AI가 못 지어냄) |

## 7. 발행 1사이클

Cowork가 매번 따르는 절차는 **COWORK-PUBLISH.md** 참조. 요약:
노션 읽기 → 중복검색 → 마크다운 작성(헷갈린점 포함) → 검증 통과 확인 → 5체크박스 검토 → push → Actions 빌드 → URL 확인 → 노션 상태 마감.

## 8. 검증·빌드

- **검증**: `python scripts/validate_posts.py` (front matter·taxonomy·중복). Actions가 빌드 전에 자동 실행 → 실패면 배포 차단.
- **빌드**: GitHub Actions에서 Hugo 0.162.1로 빌드 후 Pages 배포. 로컬 설치 불필요.
- **로컬 확인(선택)**: `C:\hugo2\hugo.exe server`로 미리보기 가능.

## 9. 디자인 (사용자 확정)

Stack 테마, **다크 기본**, 왼쪽 사이드바(소개/아카이브/검색 + 다크 토글), 카드형 글 목록(카테고리 칩·태그·읽는시간), 오른쪽 위젯(검색/보관함/카테고리/태그), 푸터 테마 크레딧 제거. 레퍼런스 = minyeamer.github.io 의 룩.

**미완(폴리시 대기)**: 글 카드 커버 이미지(썸네일), 사이드바 아바타.

## 10. 사용자만 할 수 있는 일

- GitHub Settings → Pages → Source = "GitHub Actions" (1회)
- git 인증, 테마 취향 결정, 노션↔Cowork 권한 승인

## 11. NO-GO 신호

- 한 달 돌려보고 "노션 정리가 공부보다 부담" → 노션 빼고 챗→초안 직행
- 한 달에 글 1개도 안 쌓임 → 자동화 문제 아님, 공부 습관부터
