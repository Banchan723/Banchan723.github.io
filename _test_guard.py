# -*- coding: utf-8 -*-
"""임시: 새 구조 후보 가드 테스트. 실행 후 삭제."""
import sys, os, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "scripts"))
import validate_posts as v

contexts, categories = v.load_taxonomy()

# content_schema 없고 새 6골격 헤딩 다수 + 검증블록 없음 → 가드 FAIL 떠야
CANDIDATE = '''---
title: "X"
date: 2026-06-09
slug: "x-guard-test"
description: "d"
categories:
  - "C++"
tags:
  - "포인터"
modality:
  - "code"
canonical_topic: "xguard"
context: "cpp"
level: "beginner"
---

## 개념 정의
a
## 왜 필요한가
b
## 문법과 동작
c
## 직접 확인한 예제
```cpp
int a=1;
```
출력: 1
## 흔한 실수와 오해
d
## 관련 토픽과 다음 경계
e
'''

with tempfile.TemporaryDirectory() as d:
    pdir = os.path.join(d, "content", "post", "x-guard-test")
    os.makedirs(pdir)
    p = os.path.join(pdir, "index.md")
    with open(p, "w", encoding="utf-8") as f:
        f.write(CANDIDATE)
    # validate_post는 ROOT 기준 rel 경로 검사를 하므로, 위치규칙 FAIL은 무시하고
    # 가드 메시지가 errors에 들어갔는지만 본다.
    local, warn, data = v.validate_post(p, contexts, categories)
    print("FAIL 목록:")
    for x in local:
        print("  -", x)
    assert any("새 6골격 헤딩" in x for x in local), "가드가 새 구조 후보를 안 잡음"
    print("\n[OK] 가드가 '마커 누락 새 구조 후보'를 FAIL로 잡음")
