# 학습 블로그 — 검증 게이트 + 자동발행

공부한 걸 **진짜 이해했는지 채점으로 검증되면, 태블릿만으로도 알아서 블로그에 글이 올라가는** 개인 시스템.
머리 쓰는 일(출제·채점·글작성)은 무료 Claude 앱이, 발행은 GitHub Actions가 한다. 집 컴퓨터 안 켜도 됨.

라이브: **https://banchan723.github.io**
스택: Hugo(커스텀 테마) + GitHub Pages. 주제 = C++·언리얼·블렌더·Tripo 3D 등.

## 전체 그림

```
[① 공부·검증]  태블릿/폰 — Claude 앱 + Notion 커넥터 (무료)
   공부 → 노션 행 추가 → 변형문제 출제 → 답안 → 엄격 채점
      ├ 통과 → 노션에 블로그 본문 작성 + 상태=발행준비 + 통과근거 기록
      └ 미달 → 약점 기록 + 상태=재학습필요 (다시 공부)
           ▼
[② 발행]  GitHub Actions (publish-from-notion.yml) — 하루 1번 자동 + 수동 버튼
   발행준비 행 폴링 → 본문 추출 → front matter 조립 → 검증 → 커밋·push  (LLM 없음)
           ▼
[③ 빌드·배포]  hugo.yml — Hugo 빌드 → GitHub Pages 배포 → banchan723.github.io
```

- 노션이 "공부 장소(어디서나)"와 "발행 장소(GitHub)"를 잇는 **다리**다. 노션 없이 블로그로 가는 길은 없다.
- 발행 파이프는 LLM을 안 쓴다 → **Claude 구독 외 비용 0원** (레포 퍼블릭 유지 조건).

## 비용

Claude 구독 빼면 전부 무료: GitHub Actions·Pages(퍼블릭 레포 무제한), Notion(무료 플랜), 발행 스크립트(LLM 미사용). 레포를 프라이빗으로 바꾸면 Actions 월 2000분 제한이 생기니 **퍼블릭 유지**.

## 문서·폴더 안내

| 경로 | 역할 |
|---|---|
| **`SYSTEM-SPEC.md`** | **단일 정본.** 아키텍처·결정·콘텐츠 원칙·채점 규칙·노션 스키마·상태머신·보안. 헷갈리면 여기부터 |
| `config/_default/` | Hugo 설정 |
| `content/post/<slug>/index.md` | 글이 쌓이는 곳 |
| `content/page/` | 소개·아카이브·검색 페이지 |
| `data/taxonomy.yaml` | 허용 카테고리·태그 사전 (정본) |
| `layouts/` | 테마 override |
| `scripts/notion_publish.py` | 노션 → 블로그 파일 작성 (CI에서 실행) |
| `scripts/validate_posts.py` | 발행 전 검증기 |
| `.github/workflows/publish-from-notion.yml` | 노션 폴링 → 발행 (cron + 수동) |
| `.github/workflows/hugo.yml` | 빌드 → Pages 배포 |
| `themes/hugo-theme-stack/` | 테마 (git 서브모듈, 직접 수정 X) |

> 노션 쪽 정본: "학습 블로그 ▸ 블로그 발행 규칙"(앱이 매번 읽음) + "학습 기록" DB + "학습 로드맵 & 진도".

## 운영 (사용자 입장)

1. **공부·발행** — 태블릿 Claude 앱의 "학습 블로그" 프로젝트에서 주제 공부 → "이거 블로그로 남기자" → 채점 통과하면 노션 행 자동 작성.
2. **발행 확인** — 하루 1번 자동. 급하면 GitHub Actions → Publish from Notion → Run workflow.
3. 로컬 점검(선택): `& "C:\Users\chanyoung\AppData\Local\Microsoft\WindowsApps\python3.exe" scripts\validate_posts.py` / 미리보기 `C:\hugo2\hugo.exe server`

## 현재 상태 (2026-06-07)

- ✅ 셋업 완료: 노션 토큰·GitHub Secrets·커넥터·자동발행 스모크 테스트 통과.
- ✅ 배포 연결 수정: 자동발행 커밋이 hugo 배포를 트리거하도록 `hugo.yml`에 `workflow_run` 추가.
- ⏳ 남은 일: 실제 글 1개로 end-to-end(공부→채점→발행) 검증. `content/post/pointer-cpp/`는 출력 placeholder라 `draft: true` — 사용자가 실제 출력 채우면 발행.

## 그만둘 신호 (정직하게)

- 한 달 해보고 "노션 정리가 공부보다 부담" → 게이트 완화 또는 시스템 축소.
- 채점을 자꾸 우회(그냥 통과) → 게이트 무의미, 강도 재조정.
- 한 달에 글 1개도 안 쌓임 → 자동화 문제 아님. 공부 습관부터.
