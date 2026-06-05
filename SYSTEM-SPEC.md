# 학습 블로그 자동발행 시스템 — 정본 설계서 (SYSTEM-SPEC)

> 이 문서가 시스템의 단일 정본이다. 구현(/.goal), Cowork 발행, 미래의 나(클로드) 모두 이 문서를 기준으로 한다.
> 작성: 2026-06-06 / 사용자: 프로그래밍 초보, Windows, 주제 = C++·언리얼·블렌더·Tripo 3D 등 계속 늘어남.

---

## 0. 한 줄 목표

사용자는 **공부와 노션 정리만** 한다. 나머지(글 작성·발행·목록 관리)는 AI(Cowork)가 한다. 어디서 공부했든(모바일/데스크탑) 노션에 들어가면, 집 데스크탑에서 블로그로 자동 발행된다.

## 1. 아키텍처

```
[공부]  클로드 챗 앱 (모바일·데스크탑 공용)  +  코드는 웹 컴파일러 / VS Code로 따로 실습
            │  핵심 이해를 정리
            ▼
[정리]  노션 학습 DB (만능 수신함, 어디서 공부했든 여기로)
            │  Cowork가 읽음
            ▼
[작성]  Cowork가 마크다운 초안 생성 (taxonomy·front matter 규칙 준수)
            │  사용자 검토 (5체크박스)
            ▼
[발행]  GitHub repo에 push → GitHub Actions가 클라우드 빌드 → Pages 배포
            │  발행 후 실제 URL 접속 확인
            ▼
[블로그]  {아이디}.github.io  (카테고리·태그·검색 자동)
```

**역할 분리 (중요):**
- 공부 = 챗 앱 (사용자 컴퓨터에 아무것도 설치 안 함)
- 발행 = 데스크탑 1곳(Cowork). 모바일은 git push 불가 → 공부·노션 메모만.
- 노션이 "공부 장소"와 "발행 장소"를 분리해주는 다리.

## 2. 기술 스택 결정

| 항목 | 결정 | 이유 |
|---|---|---|
| 정적 사이트 생성기 | **Jekyll** | GitHub Pages 기본 호환, 초보 자료 많음 |
| 테마 | **minimal-mistakes** (remote_theme) | 카테고리/태그/검색/시리즈 내장, 한글 OK |
| 빌드 | **GitHub Actions** (클라우드) | Windows에 Ruby/Jekyll 설치 회피 |
| 학습 기록 | **노션 DB(표)** | 발행 상태 한눈에, 까먹음 방지 |
| 발행 도구 | **Cowork** (데스크탑) | 노션 읽기 + 파일 + git push |

## 3. 폴더 구조 (repo)

```
{아이디}.github.io/
  _posts/
    cpp/      unreal/      blender/      tripo/
  _data/
    taxonomy.yml          # 허용된 카테고리·태그 사전
  assets/
    images/{slug}/001.png # 글별 폴더로 이미지 격리
  .github/workflows/
    deploy.yml            # Actions 빌드+배포
    validate.yml          # 발행 전 front matter 검증
  .gitattributes          # *.md text eol=lf  (CRLF 사고 방지)
  _config.yml
  SYSTEM-SPEC.md          # 이 문서
```

## 4. front matter 스키마 (모든 글 공통, 절대 규칙)

```yaml
---
title: "한글 제목 가능"          # 항상 따옴표 (콜론 사고 방지)
date: 2026-06-06
canonical_topic: pointer        # 개념 식별자 (영문 소문자) — 중복판정 키①
context: cpp                    # 맥락 (cpp/unreal/blender/tripo) — 중복판정 키②
category: cpp                   # taxonomy.yml에 있는 것만
tags: [pointer, memory]         # taxonomy allowed_tags 안에서만
level: beginner                 # beginner / intermediate / advanced
status: published               # draft / published / needs-review / revised
series: cpp-basics              # 선택 (시리즈일 때)
series_order: 3                 # 선택
last_reviewed: 2026-06-06       # 마지막 검토일 (오래된 틀린 글 추적)
tool_versions: {}               # 예: { unreal: "5.7" } — 도구 글일 때만
source: notion
slug: pointer-cpp               # 한번 정하면 불변. 영문 소문자. URL이 됨.
---
```

**중복 판정 키 = `canonical_topic` + `context`.**
- 같은 키 → 같은 글 (수정/추가 대상)
- 다른 키 → 새 글
- 예: `pointer`+`cpp` ≠ `pointer`+`unreal` (둘은 별개 글)

## 5. 절대 규칙 (어기면 30개에서 터짐)

1. **slug 불변** — 최초 발행 후 절대 변경 금지. 바꿔야 하면 redirect 생성.
2. **파일명·폴더·slug·이미지명 = 영문 소문자 ASCII.** 제목만 한글.
3. **카테고리·태그는 `taxonomy.yml`에 있는 것만.** 새로 필요하면 → 사용자 승인 후 taxonomy에 추가, AI 임의 추가 금지.
4. **발행 전 중복 검색 필수** — `canonical_topic`+`context`로 기존 글 검색 → 있으면 사용자에게 [신규 / 기존에 추가 / 기존 수정] 묻기.
5. **기존 글 "추가"는 하단에 `## 추가 학습 (날짜)` 섹션으로 append.** 원본 보존. 5회 넘으면 개정판/시리즈 분리 제안.
6. **코드블록의 `{{ }}` `{% %}`는 `{% raw %}`로 감싼다** (Jekyll 빌드 깨짐 방지).
7. **발행 = "성공"의 정의**: push 성공 + Actions 빌드 성공 + 실제 URL 접속 확인. 셋 다 돼야 노션 상태를 "발행완료"로.
8. **발행 전 비밀정보 스캔** — API 키·토큰·개인정보·유료강의 캡처 금지.

## 6. 노션 학습 DB 스키마

각 행 = 학습 주제 1개. 칼럼:

| 칼럼 | 값 | 용도 |
|---|---|---|
| 제목 | 한글 | 글 제목 후보 |
| canonical_topic | 영문 소문자 | 중복 판정 |
| context | cpp/unreal/blender/tripo | 맥락 |
| 난이도 | 입문/기초/중급 | level |
| 블로그行 | O / X | 발행 대상 여부 |
| 상태 | 미정리 / 정리완료 / 초안 / 검토중 / 발행완료 | 진행 추적 |
| 발행일 | 날짜 | |

**노션 본문 고정 템플릿** (자유 메모 금지):
```
오늘 배운 것 /
막혔던 부분·헷갈린 것 /
해결한 방법·비유 /
중요 개념 /
코드 예시 /
아직 헷갈리는 것
```
→ "막혔던 부분"·"헷갈린 것"이 블로그의 **"내가 헷갈렸던 점" 섹션** 재료. AI가 못 지어내는 사용자 고유 목소리. 필수 보존.

## 7. 발행 1사이클 (Cowork가 매번 따르는 절차)

1. 노션에서 `블로그行 = O` & `상태 = 정리완료`인 행을 가져온다.
2. `canonical_topic`+`context`로 기존 글 검색.
3. 기존 글 있으면 → 사용자에게 [신규/추가/수정] 묻기. 없으면 신규.
4. front matter 규칙대로 마크다운 작성. "내가 헷갈렸던 점" 섹션 포함.
5. 명백한 오류는 교정하고 교정 표시. 코드 예시는 가능하면 컴파일/문법 체크.
6. 이미지 있으면 `assets/images/{slug}/`로 복사, 경로는 `/assets/...` (슬래시).
7. 관련 기존 글 최대 3개를 하단에 링크.
8. **초안을 사용자에게 보여줌. 검토 = 5체크박스**: ①제목 ②내용 맞음 ③코드 돌아감 ④이미지 ⑤발행여부.
9. OK → push. Actions 빌드 대기 → 실패 시 로그를 "고칠 파일/줄/원인/수정안"으로 요약해 보고.
10. 빌드 성공 + URL 접속 확인 → 노션 상태 "발행완료" + 발행일 기록.

## 8. 검토 부담 최소화 (중도포기 방지)

- 사용자는 매번 **승인/거절만.** 새글/수정/태그/이미지 등 기본값은 AI가 자동 선택, 사용자는 바꿀 때만 개입.
- 공부 기록 10분, 발행은 **주 1회 배치**로 분리 (발행이 공부를 잡아먹지 않게).
- 글 성격을 "초보 학습노트"로 명시 → 완벽주의로 발행 막히는 것 방지.

## 9. 단계별 구현 범위

**v1 (지금 /.goal로 만들 것) — 나중에 고치기 비싼 것만:**
- repo 스캐폴드(폴더 구조, _config.yml, minimal-mistakes remote_theme)
- taxonomy.yml (cpp/unreal/blender/tripo + allowed_tags 초기값)
- front matter 스키마 + 예시 글 1개(포인터)
- .gitattributes (LF), .gitignore
- GitHub Actions: deploy.yml + validate.yml(front matter 검증)
- 노션 DB 스키마 정의서 + 발행 지시문(Cowork용) 파일
- README = 운영 매뉴얼

**v2 (습관으로, 코드 아님):** 5체크박스 검토, 주1회 배치, 헷갈린점 섹션 작성.

**v3 (글 100개+일 때 추가):** 사이트 내 검색 강화, 내부링크 자동추천, needs-update 재검토 워크플로, 이미지 압축 규칙.

## 10. 사용자만 할 수 있는 일 (AI 대행 불가)

- GitHub 계정 로그인
- git 인증(PAT 토큰) 1회 설정 — 만료 시 갱신
- 테마 최종 취향 결정
- 노션 ↔ Cowork 연결 권한 승인

## 11. NO-GO 신호 (이러면 시스템 접고 단순화)

- 한 달 돌려보고 "노션 정리가 공부보다 부담" → 노션 빼고 챗→초안 직행
- 한 달에 글 1개도 안 쌓임 → 자동화 문제 아님, 공부 습관부터
