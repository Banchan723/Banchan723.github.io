# ▶ 다음 세션 이어서 할 일 (인수인계)

> 작성: 2026-06-06. 현재 블로그는 **Hugo + Stack 테마**로 라이브(https://banchan723.github.io).
> 시스템(노션→Cowork→검증→발행 파이프라인)은 완성. 정본은 `SYSTEM-SPEC.md`.

## 결정된 다음 단계: 디자인을 커스텀으로 교체

사용자가 **claude.ai Design**으로 자기 블로그 시안을 직접 만들었다. 그 시안을 **커스텀 Hugo 테마로 변환**해서 Stack을 교체하기로 합의함. (파이프라인은 그대로, 보이는 껍데기만 교체.)

### 시안 모습 (`BanChan 블로그.html`)
터미널/IDE 감성. `</> BanChan/blog` 로고. 다크.
- **왼쪽 사이드바**: 프로필(BanChan, "self-taught everything") + Home/Archive/About/RSS + POSTS/CATEGORY(dev/data-ai/frontend/design/essay/career, 숫자) + TAGS + "요즘 공부 중 now learning"(진행바)
- **본문**: `# Recent posts` 카드 목록 — 카테고리 칩, 날짜, 읽는시간, 제목 + 영문 부제, 발췌, 태그 칩, 아이콘 썸네일
- 상단 `grep posts/` 검색, 우측 Tweaks 패널(포인트컬러/다크토글/목록밀도)

## 시작하려면 (블로커)
1. **사용자가 HTML/CSS를 제공해야 함**: claude.ai Design 화면의 `BanChan 블로그.html`을 다운로드(또는 코드 복사)해서 이 폴더(`C:\LearningBlog\`)에 넣거나 채팅에 붙여넣기.
2. 받으면 → HTML/CSS를 Hugo 템플릿으로 분해:
   - `layouts/baseof.html`, `layouts/_default/list.html`(홈/카드목록), `single.html`(글), `_partials/`(사이드바, 카드, 검색)
   - `assets/`(CSS/JS), 사이드바 카테고리는 `site.Taxonomies` 동적, "now learning"은 config 데이터
   - 기존 content/taxonomy/검증 파이프라인에 배선 (front matter 스키마 유지)
3. Stack 서브모듈은 제거하거나 유지(테마=커스텀으로 전환). config의 `theme=` 변경.

## 범위 합의
- 겉모습(레이아웃·다크·카드·사이드바): 그대로 재현 가능
- 인터랙티브: 검색·진행바 OK / 실시간 Tweaks 테마토글은 추가 JS, 단계적
- 빌드 함정 기억: Hugo **0.158+ 필수**(워크플로 0.162.1 고정), `buildFuture=true`(미래날짜 글)

## 현재 상태 요약
- 라이브: Hugo+Stack, 다크, 사이드바, 카드, 검색, 글 1개(포인터)
- 검증기 `scripts/validate_posts.py`(Hugo용, Codex 강화 완료), `data/taxonomy.yaml`
- 로컬 도구: `C:\hugo2\hugo.exe`(0.162.1), python = `C:\Users\chanyoung\AppData\Local\Microsoft\WindowsApps\python3.exe`(yaml 있음)
- 사용자 미완: GitHub Settings→Pages→Source = "GitHub Actions"
