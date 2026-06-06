# ▶ 다음 세션 이어서 할 일 (인수인계)

> 갱신: 2026-06-06 (3차 세션). **콘텐츠 모델 v3 + 노션 DB·발행규칙 페이지 + 발행 스크립트/워크플로/검증기 + 포인터 글 재작성까지 완료.** 코드 전부 커밋·푸시됨.
> 블로그는 라이브: https://banchan723.github.io (Hugo 커스텀 테마). 레포: github.com/Banchan723/Banchan723.github.io (퍼블릭).

---

## ▶▶ "이어서 가자" 하면 = 지금 여기부터

빌드는 거의 끝. **남은 건 사용자 셋업(토큰·시크릿) + end-to-end 테스트뿐.** 순서:

1. **사용자가 해야 막힘 (아래 5절)**: 노션 Integration 토큰 발급 → "학습 기록" DB를 그 통합에 공유 → GitHub Secrets에 `NOTION_TOKEN`,`NOTION_DB_ID`(=`77557a111e934f4cbfb363b0e9746894`) 등록. 모바일 Claude 앱에 노션 커넥터 연결.
2. 셋업되면 **작은 글감 1개로 end-to-end 테스트** (4절 7번): 노션에 행 추가→공부정리→채점통과→블로그본문→상태 발행준비 → Actions 수동 실행(workflow_dispatch) → 발행완료·URL 확인.
3. **포인터 글 출력 채우기**: `content/post/pointer-cpp/index.md`는 지금 `draft: true`(출력 placeholder뿐이라 발행 불가·라이브 제외 상태). 사용자가 g++로 코드 2~3개 직접 돌려 `⚠️ 직접 돌린 출력 채우기` 자리 채우고 draft 제거하면 발행됨. (이 환경엔 컴파일러 없어서 못 채움.)

> ⚠️ 현재 cron(publish-from-notion.yml)은 매일 돌지만 토큰 없으면 `[SKIP]`로 조용히 통과(no-op) — 실패 안 남. 토큰 넣는 순간부터 실제 발행 시작.

---

## 0. 한 줄

**공부한 걸 Claude가 엄격 채점해서 "진짜 이해했다" 통과하면, 태블릿만으로도 알아서 블로그에 글이 올라가는 시스템.** 머리 쓰는 일(출제·채점·글작성)은 무료 Claude 앱, 발행은 GitHub Actions(공짜). 집 컴퓨터 불필요.

## 1. 먼저 읽을 정본 (순서대로)

1. **SYSTEM-SPEC.md** — 시스템 단일 정본(아키텍처·결정·한계·상태머신·콘텐츠 철학 4-1).
2. **GRADING-PROTOCOL.md** — 엄격 채점 규칙(Claude 앱이 따름).
3. **NOTION-DB.md** — 노션 DB 스키마·상태·본문 섹션(아직 안 만듦, 여기 보고 생성).
4. (참고) COWORK-PUBLISH.md — 옛 수동 발행. **대체됨.** 예외 수동발행 때만.

## 2. 확정된 설계 (2026-06-06 사용자 승인)

- **B1 방식**: 채점·글작성 = 무료 Claude 앱 세션. 발행만 GitHub Actions가 자동. Claude API 안 씀 → 공짜.
- **3구역**: ①공부·검증(태블릿, Claude앱+Notion커넥터) → ②발행(Actions, 노션→파일→커밋, LLM없음) → ③빌드·배포(기존 hugo.yml).
- **엄격 채점**: 변형문제 + **직접 돌린 출력** 제시해야 통과. 통과근거 노션 기록.
- **통과=바로 발행**(별도 승인 없음). **같은 개념=기존 글 누적**. **하루 1번 자동 + 수동 버튼**.
- **콘텐츠 철학 개정**(4-1): "설명 금지" → "**근거 없는 설명만 금지**". 본문은 독자 순서, 로그는 증거. 채점 통과 답변이 readability 원재료.

## 3. 이번 세션에 한 일 ✅ (전부 미커밋 — 문서만 수정)

- 검증 게이트 설계를 적대적 검증(Codex 3회: 설계/실패모드 36개/콘텐츠품질)까지 거쳐 확정.
- **SYSTEM-SPEC.md 전면 개정** — v2(게이트+자동발행+상태머신+보안) + 4-1 콘텐츠 철학 개정.
- **NOTION-DB.md 전면 개정** — v2 스키마(검증 필드)·상태머신·본문 섹션(BLOG_MD 마커).
- **GRADING-PROTOCOL.md 신규** — 엄격 채점 규칙.
- **COWORK-PUBLISH.md** — 대체됨 배너.
- ⚠️ **노션엔 아직 아무것도 안 만듦.** 코드(스크립트·워크플로)도 아직 안 만듦.

## 3b. 2026-06-06 (2차 세션) 추가로 한 일 ✅

- **콘텐츠 모델 v3 일반화** (Codex 교차검증 + 사용자 승인). 매체별 글 분리 ❌ → **공통 골격 1개 + 증거블록(매체=노션 필드)**. C++/블렌더/언리얼/유튜브 다 커버.
  - SYSTEM-SPEC 4-1 전면 개정: 매체(code/visual/video) 개념, 새 본문 골격(확인한 증거 통합 + "다른 예시에 적용해보기" 추가), 매체별 CI 강제 규칙, 스크린샷 조작·영상 베끼기 방어.
  - 확정값: 구조=공통골격+증거블록 / 스크린샷=중간(스샷+재현단계+설정값, 단독불가) / 영상=재현·변형 결과물 필수.
- **노션 생성 완료** (Notion MCP):
  - 부모 페이지 "학습 블로그" = `377fe331-8817-81f0-8c59-dde33a38968c`
  - **"학습 기록" DB** = `https://app.notion.com/p/77557a111e934f4cbfb363b0e9746894`
    - **NOTION_DB_ID(깃헙 시크릿용)** = `77557a111e934f4cbfb363b0e9746894`
    - data source(collection) = `3041c1b9-b0b3-4104-8e4c-ee6e3d8a703c`
    - 스키마: 제목·canonical_topic·context·**매체(multi)**·**영상출처**·태그(multi)·난이도·slug·description·상태·처리방식·발행일·발행커밋·발행URL·통과근거·오류요약. 전부 NOTION-DB.md v2 + 매체 반영.
## 3c. 2026-06-06 (3차 세션) 한 일 ✅ — 코드 전부 커밋·푸시됨

- **노션 "블로그 발행 규칙" 페이지 생성** = `377fe331-8817-811f-aef2-c49a41febdca` (학습 블로그 밑). Claude 앱이 글 쓸 때 읽는 단일 규칙판 + 행 본문 템플릿 포함.
- **`scripts/notion_publish.py` 작성** (667줄). Codex 적대적 리뷰 8건 전부 반영(마커 미닫힘 실패처리·append 멱등 섹션경계·기존글추가 메타요구 버그·YAML 제어문자 이스케이프·락 re-GET 방어·위험콘텐츠 엔티티 변형·에러로그 축소). 토큰 없으면 `[SKIP]` exit 0(no-op).
- **`.github/workflows/publish-from-notion.yml` 작성** — cron 07:00 KST + workflow_dispatch, concurrency 직렬화, contents:write, validate 후 변경시 commit+push.
- **`scripts/validate_posts.py` 매체별 readability 강화** — 필수 섹션·매체별 증거강제(code=출력/visual=이미지+재현/video=출처+재현)·이미지 alt·상투어/길이 경고. **draft 글 skip** + **placeholder 출력은 출력없음=FAIL**(엄격 결정). Codex 교차검증 완료.
- **포인터 글 v3 재작성** + `draft: true`(출력 placeholder뿐이라 미완성→라이브 제외). 레퍼런스 예시.
- 검증: py_compile OK, validate_posts.py exit 0(포인터 draft skip).

## 4. 남은 단계 (= "이어서 가자" 시작점, 위 ▶▶ 와 동일)

> 빌드 거의 끝. 남은 건 사용자 셋업 + e2e 테스트.

1~6. ✅ 완료 (3b·3c 참고).
7. **end-to-end 테스트** — 사용자 셋업(5절) 후 작은 글감 1개로 공부→채점→발행 한 바퀴. workflow_dispatch로 수동 1회 먼저.
8. **포인터 글 출력 채우고 draft 제거** — 사용자가 g++로 실행해 실제 출력 붙이면 발행됨.

## 5. 사용자만 할 수 있는 일 (블로킹 — 같이 해야 함)

- **[#1] 노션 Internal Integration 발급** — notion.so/my-integrations → New integration → 토큰 복사. (이번 세션에 안내했으나 미완.)
- **[#2] "학습 기록" DB(이미 생성됨)를 #1 통합에 공유** — 노션에서 학습 블로그 ▸ 학습 기록 DB 열고 우상단 ··· → Connections → 통합 추가.
- **[#3] GitHub repo Secrets 등록** — Settings → Secrets and variables → Actions: `NOTION_TOKEN`(=#1 토큰), `NOTION_DB_ID`(=생성된 DB ID, 내가 알려줌).
- **[#4] GitHub Settings → Actions → Workflow permissions** = Read and write (또는 워크플로 permissions로 지정 — 본 설계는 후자라 불필요할 수도).
- **[#5] 모바일/태블릿 Claude 앱에 Notion 커넥터 연결** 확인.

## 6. 주의 / 한계 (SYSTEM-SPEC 3절)

- 자가채점 관대편향(엄격모드+통과근거로 완화, 완전제거 X), 코드출력 환각(직접 돌린 출력 요구로 방어), 사용량 한도, 통과=바로발행이라 글 오류는 사후 수정.
- 드리프트 방지: 코드↔정본 충돌 시 코드/실제 노션 상태 신뢰. 정본 임의 변경 금지(사용자 확정만).

## 7. 빌드/도구 메모

- Hugo: `C:\hugo2\hugo.exe` (0.162.1, ≥0.158). 빌드 `hugo --gc --minify`.
- Python(검증): `C:\Users\chanyoung\AppData\Local\Microsoft\WindowsApps\python3.exe scripts/validate_posts.py` (로컬 `python`은 Store stub라 깨짐).
- 로컬 C++ 컴파일러 없음 — 코드 출력은 사용자가 직접 실행해 채움.
- notion_publish.py는 CI(Linux)에서 `requests`로 Notion API 호출. 로컬 테스트엔 사용자 토큰 필요.
- gh CLI 이 환경 bash에 없음 — 시크릿은 GitHub 웹 UI로.
