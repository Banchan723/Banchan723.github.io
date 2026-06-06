# ▶ 다음 세션 이어서 할 일 (인수인계)

> 갱신: 2026-06-06. 블로그는 **Hugo + 커스텀 테마**로 라이브(https://banchan723.github.io).
> 시스템(노션→Cowork→검증→발행 파이프라인) 정본은 `SYSTEM-SPEC.md`.

---

## 이번 세션에 한 일 (2026-06-06)

### 1. Stack 테마 → 커스텀 테마 전면 교체 ✅ (라이브 반영 완료)
claude.ai Design 시안(`design_handoff_banchan_blog`, 터미널/IDE 감성)을 Hugo 커스텀 테마로 변환.
- `layouts/`: baseof·home·single·list·page + 사이드바/헤더/카드 partial, 코드블록 render hook(Chroma+신호등바+copy), TIL 숏코드
- `assets/`: 디자인 토큰 CSS(다크+라이트) + 클라이언트 JS(검색/카테고리·태그 필터/정렬/테마토글/TOC active/copy)
- `config`: `theme=` 제거(자체 layouts), Chroma highlight·TOC 설정, `[profile]` params
- `data/taxonomy.yaml`: 카테고리별 색(C++ #5aa2ff · Unreal #4dd5d5 · Blender #ffa65c · Tripo 3D #b98cff)
- 검증: Hugo 0.162.1 빌드 22p, validate_posts 통과, 홈/글 시각 확인, **커밋·푸시·Actions 배포 성공** (커밋 79cd3f6)

### 2. 콘텐츠 작성 원칙 확정 ✅ (정본 문서 갱신, 미커밋)
첫 글이 "AI가 쓴 일반 튜토리얼"처럼 읽힌다는 문제 → Codex 교차검증 후 원칙 정립.
- **제목 = 개념명 그 자체** ("C++ 포인터"). 같은 개념 재학습 → 기존 글에 누적(중복판정 시스템과 정합). 감성 비유/과장 제목 금지.
- **본문 = 디버깅 로그 골격**: 막힌 점 → 확인한 코드 → 결과/동작 → 그래서 이렇게 이해했다 → 아직 모르는 것
- **정확성 방어**: 단정 일반론 줄이기(범위 한정), 모르는 것 명시, 노션에 없는 지식 임의 추가 금지, 환경값(주소 등) 지어내지 않기
- 반영처: `SYSTEM-SPEC.md` 4-1절(신규), `NOTION-DB.md` 2절(경험 데이터 9칸으로 보강), `COWORK-PUBLISH.md`(발행 전 콘텐츠 체크리스트)

### 3. 첫 글(포인터) 디버깅 로그로 재작성 ✅ (미커밋)
`content/post/pointer-cpp/index.md`. title "C++ 포인터"(감성 부제 제거). 사용자 실제 막힌 점 3개(8바이트 의문/`*p`vs`p`/`->`) 살림. slug·canonical_topic·context 불변 유지. 검증기 통과.
- **미완**: `## 결과 / 동작`에 실제 컴파일 출력값이 비어 있음(로컬에 컴파일러 없어 안 지어냄, 표준 보장 관계만 기술). → **사용자가 직접 코드 돌려 진짜 출력 채우면 완성.**

### 4. '요즘 공부 중' 위젯 구조 정비 ✅
디자인 더미값(Unreal C++ 45% 등) 제거. 위젯 데이터를 `data/learning.yaml`로 분리(클로드 갱신/노션 동기화의 목적지). 사이드바가 그 파일을 읽음. 항목 0개면 위젯 자동 숨김.
- 결정된 운영 방식: **노션 학습 진행 DB → 발행 때 동기화 → learning.yaml → 위젯**. 진행도는 **% 진행바(체감 이해도, 주관 수치)** 유지.

### 5. 코드블록 가독성 + 줄번호 거터 ✅
사용자 디자인 값 반영. 주석 밝게(#7f8da3 이탤릭), 코드블록 배경 분리(#161d27 + 보더 #2e3a48 + radius 10 + 옅은 그림자), 본문 글자 #dbe3ef / 줄간격 1.85, 전체 배경 완화(#0c1118).
- **줄번호 거터**: config `lineNos=true, lineNumbersInTable=true`. 거터 살짝 어둡게 + 우측 보더, 줄번호색 #65728a.
- **신호등 점 제거** → cbar에 파일명 + copy만. 파일명은 코드펜스 `title="..."` 정보스트링 우선(없으면 언어별 기본명).
- **copy JS 수정**: lineNumbersInTable이면 코드가 마지막 칼럼 `<pre>`라, `.lntable td.lntd:last-child pre`를 복사(줄번호 제외).
- 코드블록은 라이트 모드에서도 다크 패널 유지(밝은 글자 상속).

---

## 커밋 상태
- 커스텀 테마 교체(79cd3f6) + 위 2~5(글 재작성·작성원칙 정본·위젯 구조·코드블록 가독성) **전부 커밋·푸시·배포 완료.**
- 라이브(https://banchan723.github.io) 반영됨.

## 다음 할 일 (우선순위)
1. **'요즘 공부 중' 채우기** — 사용자가 지금 실제 공부 중인 항목 2~3개(라벨+체감 정도) 주면 `data/learning.yaml`에 입력.
2. **노션 학습 진행 DB 생성** — 사용자 워크스페이스에 만들어 노션 연동의 소스로. (현재 노션엔 블로그 학습DB가 없음 — TwinProject 페이지들만 존재.)
3. **포인터 글 출력값 채우기** — 사용자가 VS Code/웹컴파일러로 코드 실행 → 진짜 주소·출력값을 `## 결과 / 동작`에.
4. **미커밋 변경 커밋·푸시** — 위 1~3 정리되면.
5. (선택) Stack 서브모듈(`themes/hugo-theme-stack`) 제거 — 테마 교체 끝났으니.
6. (확인) 프로필 일부 더미 가능성 — `config/_default/params.toml` `[profile]`(name/role/bio/location/since). 실제값 맞는지 점검.

## 빌드/도구 메모
- Hugo: `C:\hugo2\hugo.exe` (0.162.1, ≥0.158 필수). 빌드 `hugo --gc --minify`.
- Python(검증): `C:\Users\chanyoung\AppData\Local\Microsoft\WindowsApps\python3.exe scripts/validate_posts.py`
- 로컬 컴파일러 없음(C++ 출력 검증 불가) — 코드 출력은 사용자가 직접 실행해 채움.
- 디자인 원본: `C:\Users\chanyoung\Downloads\깃 블로그\design_handoff_banchan_blog\`
