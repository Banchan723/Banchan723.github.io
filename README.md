# 독학 노트 — 학습 블로그 시스템

혼자 공부한 걸(C++·언리얼·블렌더·3D) **차곡차곡 블로그에 쌓는** 개인 시스템.
나는 **공부와 노션 정리만** 하고, 나머지(글쓰기·발행·목록 관리)는 AI(Cowork)가 한다.

## 전체 그림

```
공부 (클로드 챗, 어디서든)
  └ 코드는 웹 컴파일러 / VS Code로 따로 실습
        │  핵심을 노션에 정리
        ▼
노션 '학습 기록' DB  ← 어디서 공부했든 여기로 (모바일·데스크탑 공용)
        │  집 데스크탑에서 Cowork가 읽음
        ▼
Cowork가 마크다운 글 작성 → 내가 5체크박스 검토 → push
        │
        ▼
GitHub Actions가 클라우드에서 빌드 → Pages 배포
        ▼
{내아이디}.github.io  (카테고리·태그·검색 자동)
```

**핵심 규칙 3개:**
- 공부는 아무 데서나, **발행은 집 데스크탑에서만** (모바일은 git push 불가)
- 글이 쌓여도 안 터지게 → **카테고리/태그는 `_data/taxonomy.yml`에 있는 것만**
- 같은 주제 또 배우면 새 글이 아니라 **기존 글에 추가** (중복 판정 = canonical_topic + context)

## 폴더 안내

| 경로 | 역할 |
|---|---|
| `SYSTEM-SPEC.md` | **단일 정본.** 헷갈리면 여기부터 |
| `NOTION-DB.md` | 노션 학습 DB 만드는 법 + 본문 템플릿 |
| `COWORK-PUBLISH.md` | Cowork가 발행할 때 따르는 절차 (복붙용 지시문 포함) |
| `_posts/{cpp,unreal,blender,tripo}/` | 글이 쌓이는 곳 |
| `_data/taxonomy.yml` | 허용된 카테고리·태그 사전 |
| `assets/images/{slug}/` | 글별 이미지 |
| `scripts/validate_posts.py` | 발행 전 글 규칙 검사기 |
| `.github/workflows/` | 클라우드 빌드(deploy) + 검증(validate) |

## 평소 운영 루틴

1. **공부 (매일, 10분 기록)** — 주제 하나 끝나면 노션에 정리. 형식은 NOTION-DB.md의 6칸.
   - 특히 **"막혔던 부분·헷갈린 것"**을 꼭 적는다. AI가 못 지어내는, 가장 값진 부분.
2. **발행 (주 1회, 몰아서)** — 집에서 Cowork에게: "정리완료된 글들 발행해줘."
   - 발행이 공부 시간을 잡아먹지 않게 **배치로**.
3. **검토는 5체크박스만** — 제목 / 내용 맞음 / 코드 돌아감 / 이미지 / 발행여부.

## 글 직접 검증 (선택)

push 전에 글이 규칙을 지켰는지 직접 보고 싶으면:

```powershell
& "C:\Users\chanyoung\AppData\Local\Microsoft\WindowsApps\python3.exe" scripts\validate_posts.py
```

(어차피 push하면 GitHub Actions가 자동으로 같은 검사를 한다.)

## 도구 분담

- **공부** = 클로드 챗 앱 (모바일·데스크탑)
- **발행** = Cowork (데스크탑) — 노션 읽고 글 써서 push
- **빌드** = GitHub Actions (클라우드) — 내 컴퓨터엔 Ruby/Jekyll 설치 안 함

## 그만둘 신호 (정직하게)

- 한 달 해보고 "노션 정리가 공부보다 부담" → 노션 빼고 챗→초안 직행으로 단순화
- 한 달에 글 1개도 안 쌓임 → 자동화 문제 아님. 공부 습관부터.
