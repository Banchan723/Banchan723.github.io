# ▶ 다음 세션 이어서 할 일 (인수인계)

> 갱신: 2026-06-06. **검증 게이트 + 자동발행 시스템**을 설계 확정하고 문서화까지 마침. 다음 = 실제 구현.
> 블로그는 라이브: https://banchan723.github.io (Hugo 커스텀 테마). 레포: github.com/Banchan723/Banchan723.github.io (퍼블릭).

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

## 4. 남은 빌드 단계 (다음 세션, 순서대로)

> 페어 미세스텝 아님 — 차분히 구현. 코드 수정 후 Codex 교차검증(codex-gate) 필수.

1. **노션 "학습 기록" DB 생성** (Notion MCP `notion-create-database`). NOTION-DB.md 스키마대로. 부모 페이지 = 사용자에게 어디 둘지 확인(현재 노션엔 TwinProject 페이지들만 존재).
2. **노션 "블로그 발행 규칙" 페이지 생성** — taxonomy(data/taxonomy.yaml 복제)·front matter 스키마·4-1 글 구조·템플릿. Claude 앱이 글 쓸 때 매번 읽을 단일 규칙판.
3. **`scripts/notion_publish.py` 작성** (CI에서 실행):
   - Notion REST API로 상태=`발행준비` 행 폴링 → 락(`처리중`).
   - 페이지 본문에서 `BLOG_MD_BEGIN`/`BLOG_MD_END` 사이 코드블록 **그대로 추출**(변환 X). 100블록 pagination·2000자 rich_text 이어붙이기 처리.
   - DB 속성에서 front matter 조립(제목 따옴표, context→categories 매핑, 난이도→level).
   - 이미지: v1은 텍스트 전용(이미지 있으면 `발행실패`로 빼고 집에서). (이미지 자동 다운로드는 후순위 TODO.)
   - 처리방식=`기존글추가`면 기존 slug 파일에 `## 추가 학습 (날짜)` append, 아니면 신규 파일.
   - `content/post/{slug}/index.md` 작성 → 멱등(이미 같으면 skip).
   - 성공: 상태=`발행완료` + 발행일/커밋/URL 기록. 실패: 상태=`발행실패` + 오류요약(본문 자동수정 금지).
4. **`.github/workflows/publish-from-notion.yml` 작성**: `schedule`(하루 1번, Asia/Seoul 고려 cron) + `workflow_dispatch`. `permissions: contents: write`. 단계: checkout → setup python → pip install requests pyyaml → notion_publish.py → validate_posts.py → 변경 있으면 commit+push(=hugo.yml 트리거). 시크릿 `NOTION_TOKEN`,`NOTION_DB_ID`.
5. **`scripts/validate_posts.py`에 readability 체크 추가** — SYSTEM-SPEC 4-1 (5): 필수 섹션 존재, 코드블록 있는데 `## 결과 / 동작` 비면 실패(cpp 등), 상투어·문장길이 경고.
6. **포인터 글 새 구조로 재작성** — 4-1 (3) 구조(이 글에서 이해할 것/읽기 전 배경/.../확인 질문). **레퍼런스 예시**. 단 `## 결과 / 동작`은 사용자가 직접 코드 돌려 진짜 출력 채워야 완성(현재 비어 있어 새 규칙상 발행 불가).
7. **전체 한 바퀴 테스트** — 노션 토큰·시크릿 세팅(아래 사용자 작업) 후, 작은 글감 1개로 공부→채점→발행 end-to-end.
8. 다 되면 **커밋·푸시**.

## 5. 사용자만 할 수 있는 일 (블로킹 — 같이 해야 함)

- **[#1] 노션 Internal Integration 발급** — notion.so/my-integrations → New integration → 토큰 복사. (이번 세션에 안내했으나 미완.)
- **[#2] 위 DB 생성 후, 그 DB를 #1 통합에 공유** (DB 우상단 ··· → Connections → 통합 추가).
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
