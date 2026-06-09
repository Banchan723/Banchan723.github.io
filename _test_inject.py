# -*- coding: utf-8 -*-
"""임시 테스트: content_schema 자동 주입. 실행 후 삭제."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "scripts"))
import notion_publish as np

FM = '---\ntitle: "C++ 포인터"\ndate: 2026-06-09\nslug: "cpp-pointer"\nlevel: "beginner"\n---\n'

body_new = """## 개념 정의
...
```yaml
verification:
  checked_claims:
    - { claim: "x", evidence: "y" }
unknowns:
  - "z"
```
"""
body_old = "## 이 글에서 이해할 것\n포인터는 주소다.\n"

print("=== 새 구조 본문(검증블록 있음) → 감지 ===")
print("has_verification_block:", np.has_verification_block(body_new))
assert np.has_verification_block(body_new) is True

print("=== 옛 구조 본문(검증블록 없음) → 미감지 ===")
print("has_verification_block:", np.has_verification_block(body_old))
assert np.has_verification_block(body_old) is False

print("\n=== 주입 결과 ===")
injected = np.inject_content_schema(FM, "reference-v1")
print(injected)
assert 'content_schema: "reference-v1"' in injected
assert injected.strip().endswith("---")  # 닫는 --- 앞에 들어가야

print("=== 멱등(두 번 주입해도 1개) ===")
twice = np.inject_content_schema(injected, "reference-v1")
assert twice.count("content_schema") == 1, "중복 주입됨"

print("\n[OK] content_schema 자동 주입 동작 확인")
