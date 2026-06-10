# -*- coding: utf-8 -*-
"""_test_close_loop.py — 침묵실패/고아락/finalize 3종 수정 검증 (네트워크 없음).

검증 항목:
  1) is_stale_processing — 오래된 처리중만 고아 락으로 판정
  2) run_check_failures — 실패>0 이면 exit 1 (워크플로 빨간불)
  3) run_finalize — 상태파일의 성공 행을 실제 커밋 SHA 로 마감,
     마감 PATCH 실패 시 exit 1 (행은 처리중으로 남아 다음 실행이 회수)
"""
import datetime
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "scripts"))
import notion_publish as np

fails = []


def check(name, cond):
    print(("  [OK] " if cond else "  [FAIL] ") + name)
    if not cond:
        fails.append(name)


now = datetime.datetime.now(datetime.timezone.utc)


def page_edited(hours_ago):
    ts = (now - datetime.timedelta(hours=hours_ago)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    return {"last_edited_time": ts}


print("=== 1) is_stale_processing ===")
check("3시간 전 편집 → 고아 락", np.is_stale_processing(page_edited(3), now) is True)
check("10분 전 편집 → 정상 락(안 건드림)",
      np.is_stale_processing(page_edited(10 / 60), now) is False)
check("타임스탬프 없음 → 보수적으로 False",
      np.is_stale_processing({}, now) is False)
check("깨진 타임스탬프 → False",
      np.is_stale_processing({"last_edited_time": "not-a-date"}, now) is False)

print("=== 2) run_check_failures ===")
tmp = tempfile.mkdtemp()
np.STATE_FILE = os.path.join(tmp, "._publish_state.json")

check("상태파일 없음 → 0 (통과)", np.run_check_failures() == 0)
np.write_state({"to_finalize": [], "published": 0, "failed": 0, "skipped": 0})
check("실패 0건 → 0", np.run_check_failures() == 0)
np.write_state({"to_finalize": [], "published": 1, "failed": 2, "skipped": 0})
check("실패 2건 → 1 (빨간불)", np.run_check_failures() == 1)

print("=== 3) run_finalize ===")
os.environ["NOTION_TOKEN"] = "test-token"
os.environ["PUBLISH_COMMIT_SHA"] = "abc1234deadbeef"

done_calls = []


def fake_set_done(token, page_id, slug, pub_date, sha):
    if slug == "boom":
        raise RuntimeError("PATCH 실패 시뮬레이션")
    done_calls.append((page_id, slug, pub_date, sha))


np.set_done = fake_set_done

np.write_state({"to_finalize": [], "published": 0, "failed": 0, "skipped": 0})
check("마감할 행 없음 → 0", np.run_finalize() == 0)

np.write_state({"to_finalize": [
    {"page_id": "p1", "slug": "cpp-pointer-param",
     "pub_date": "2026-06-11", "result": "written"},
], "published": 1, "failed": 0, "skipped": 0})
rc = np.run_finalize()
check("정상 마감 → 0", rc == 0)
check("set_done 1회 호출", len(done_calls) == 1)
check("SHA 7자리로 잘려 전달", done_calls and done_calls[0][3] == "abc1234")
check("pub_date 가 date 객체로 파싱",
      done_calls and done_calls[0][2] == datetime.date(2026, 6, 11))

revert_calls = []


def fake_update_props(token, page_id, props):
    revert_calls.append((page_id, props))


np.update_page_props = fake_update_props

np.write_state({"to_finalize": [
    {"page_id": "p2", "slug": "boom", "pub_date": "2026-06-11", "result": "written"},
], "published": 1, "failed": 0, "skipped": 0})
check("마감 PATCH 실패 → 1 (빨간불)", np.run_finalize() == 1)
check("마감 실패 행은 발행준비로 복귀 시도(빠른 자가복구)",
      len(revert_calls) == 1 and
      revert_calls[0][1][np.P_STATUS]["select"]["name"] == np.ST_READY)

print("=== 4) Codex 지적: 크로스데이 재시도 멱등성 ===")
posts_tmp = tempfile.mkdtemp()
np.POSTS_DIR = posts_tmp

fm_old = '---\ntitle: "t"\ndate: 2026-06-10\nslug: "s"\n---\n'
fm_new = '---\ntitle: "t"\ndate: 2026-06-11\nslug: "s"\n---\n'
body = "## 개념 정의\n\n본문."
os.makedirs(os.path.join(posts_tmp, "s"))
with open(os.path.join(posts_tmp, "s", "index.md"), "w", encoding="utf-8") as f:
    f.write(fm_old + "\n" + body + "\n")
check("신규: 날짜만 다른 동일 글 → skip (어제 push 분 재시도)",
      np.write_new_post("s", fm_new, body) == "skip")

try:
    np.write_new_post("s", fm_new, body + "\n다른 내용 추가")
    check("신규: 다른 본문 → PublishError", False)
except np.PublishError:
    check("신규: 다른 본문 → PublishError", True)

appended_post = (fm_old + "\n" + body +
                 "\n\n## 추가 학습 (2026-06-10)\n\n어제 추가한 내용.\n")
with open(os.path.join(posts_tmp, "s", "index.md"), "w", encoding="utf-8") as f:
    f.write(appended_post)
check("추가학습: 같은 본문이 어제 날짜로 이미 있음 → skip (이중 append 방지)",
      np.append_to_post("s", "어제 추가한 내용.",
                        datetime.date(2026, 6, 11)) == "skip")
check("추가학습: 새 본문은 정상 append",
      np.append_to_post("s", "오늘 새로 공부한 내용.",
                        datetime.date(2026, 6, 11)) == "appended")

print("=== 5) Codex 지적: 회수 실패도 빨간불 ===")
np.write_state({"to_finalize": [], "published": 0, "failed": 0,
                "skipped": 0, "recover_errors": 1})
check("recover_errors>0 → check-failures 1", np.run_check_failures() == 1)


def fake_query_fail(token, db_id, status):
    raise RuntimeError("Notion 다운")


np.query_pages_by_status = fake_query_fail
check("처리중 조회 실패 → (0,1) 반환(상태파일로 빨간불 전달)",
      np.recover_stale_processing("t", "d") == (0, 1))

print()
if fails:
    print(f"[FAIL] {len(fails)}건: {fails}")
    sys.exit(1)
print("[OK] 침묵실패/고아락/finalize 수정 전부 통과")
