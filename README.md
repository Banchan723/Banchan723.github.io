# 독학 노트 — 학습 블로그 시스템 (Hugo + Stack)

혼자 공부한 걸(C++·언리얼·블렌더·3D) **차곡차곡 블로그에 쌓는** 개인 시스템.
나는 **공부와 노션 정리만** 하고, 나머지(글쓰기·발행·목록 관리)는 AI(Cowork)가 한다.

라이브: **https://banchan723.github.io**

## 전체 그림

```
공부 (클로드 챗, 어디서든)  →  노션 '학습 기록' DB  →  Cowork가 글 작성
   →  내가 5체크박스 검토  →  push  →  Actions(검증→Hugo 빌드→배포)  →  블로그
```

**핵심 규칙 3개:**
- 공부는 어디서나, **발행은 집 데스크탑에서만** (모바일은 git push 불가)
- 카테고리/태그는 **`data/taxonomy.yaml`에 있는 것만** (글 쌓여도 안 지저분)
- 같은 주제 또 배우면 새 글이 아니라 **기존 글에 추가** (중복키 = canonical_topic + context)

## 폴더 안내

| 경로 | 역할 |
|---|---|
| `SYSTEM-SPEC.md` | **단일 정본.** 헷갈리면 여기부터 |
| `NOTION-DB.md` | 노션 학습 DB 만드는 법 + 본문 템플릿 |
| `COWORK-PUBLISH.md` | Cowork 발행 절차 (복붙 지시문 포함) |
| `config/_default/` | Hugo + Stack 설정 |
| `content/post/<slug>/index.md` | 글이 쌓이는 곳 |
| `content/page/` | 소개·아카이브·검색 페이지 |
| `data/taxonomy.yaml` | 허용 카테고리·태그 사전 |
| `layouts/` | 테마 일부 override (푸터 등) |
| `scripts/validate_posts.py` | 발행 전 검증기 |
| `themes/hugo-theme-stack/` | Stack 테마 (git 서브모듈, 직접 수정 X) |
| `.github/workflows/hugo.yml` | 검증 + 클라우드 빌드 + 배포 |

## 평소 운영 루틴

1. **공부 (매일, 10분 기록)** — 주제 하나 끝나면 노션에 정리(NOTION-DB.md 6칸). 특히 **"막혔던 부분"**을 꼭.
2. **발행 (주 1회, 몰아서)** — 집에서 Cowork에게 "정리완료된 글 발행해줘".
3. **검토는 5체크박스만** — 제목 / 내용 / 코드 / 이미지 / 발행여부.

## 로컬에서 직접 해보기 (선택)

검증:
```powershell
& "C:\Users\chanyoung\AppData\Local\Microsoft\WindowsApps\python3.exe" scripts\validate_posts.py
```
미리보기 (로컬 서버, http://localhost:1313):
```powershell
C:\hugo2\hugo.exe server
```

## 도구·버전

- 공부 = 클로드 챗 / 발행 = Cowork / 빌드 = GitHub Actions(클라우드)
- Hugo **0.162.1 고정** (Stack v4는 0.158+ 필수 — 0.157은 빌드 실패함)
- 테마 업데이트: `git submodule update --remote themes/hugo-theme-stack` (호환 버전 확인 후)

## 그만둘 신호 (정직하게)

- 한 달 해보고 "노션 정리가 공부보다 부담" → 노션 빼고 챗→초안 직행
- 한 달에 글 1개도 안 쌓임 → 자동화 문제 아님. 공부 습관부터.
