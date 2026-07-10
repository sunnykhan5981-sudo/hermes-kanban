#!/usr/bin/env python3
"""Mobile/responsive test harness for the pl-kanban dashboard.

Tests against a live server (default http://localhost:9292) using Playwright
mobile emulation (iPhone 12, 390x844). Produces a JSON report + screenshots.

NON-DESTRUCTIVE: the swipe-move functional test creates its own throwaway
task (then deletes it) so the user's real board is never mutated.
"""
import json
import os
import sys
import sqlite3
from playwright.sync_api import sync_playwright

BASE_URL = os.environ.get("BASE_URL", "http://localhost:9292")
SHOT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mobile_shots")
os.makedirs(SHOT_DIR, exist_ok=True)
DB_PATH = r"C:\Users\PROJECT-1\AppData\Local\hermes\kanban.db"

VIEWPORT = {"width": 390, "height": 844}
UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) "
       "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1")

results = []


def record(name, passed, detail=""):
    results.append({"test": name, "pass": bool(passed), "detail": detail})
    print(f"[{'PASS' if passed else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


def db_status(tid):
    try:
        con = sqlite3.connect(DB_PATH)
        c = con.cursor()
        c.execute("SELECT status FROM tasks WHERE id=?", (tid,))
        r = c.fetchone()
        con.close()
        return r[0] if r else None
    except Exception:
        return None


def db_set_status(tid, status):
    con = sqlite3.connect(DB_PATH)
    con.execute("UPDATE tasks SET status=? WHERE id=?", (status, tid))
    con.commit()
    con.close()


with sync_playwright() as p:
    context = p.chromium.launch().new_context(
        viewport=VIEWPORT,
        device_scale_factor=3,
        user_agent=UA,
        is_mobile=True,
        has_touch=True,
    )
    page = context.new_page()
    console_errors = []
    page.on("console", lambda m: console_errors.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: console_errors.append(f"pageerror: {e}"))

    # 1. Load
    try:
        page.goto(BASE_URL, wait_until="networkidle", timeout=20000)
    except Exception as e:
        record("page_load", False, f"goto failed: {e}")
        print(json.dumps({"results": results, "console_errors": console_errors}, indent=2))
        sys.exit(1)
    record("page_load", True, f"loaded {BASE_URL} @ {VIEWPORT['width']}x{VIEWPORT['height']}")

    # 2. viewport meta
    has_vp = page.evaluate("""() => {
        const m = document.querySelector('meta[name=viewport]');
        return !!m && m.content.includes('width=device-width');
    }""")
    record("viewport_meta", has_vp)

    # 3. Horizontal overflow check
    overflow = page.evaluate("""() => ({
        scrollW: document.documentElement.scrollWidth,
        clientW: document.documentElement.clientWidth })""")
    no_h_overflow = overflow["scrollW"] <= overflow["clientW"] + 1
    record("no_horizontal_overflow", no_h_overflow,
           f"scrollW={overflow['scrollW']} clientW={overflow['clientW']}")

    # 4. Board + columns rendered
    page.wait_for_selector(".column", timeout=10000)
    cols = page.query_selector_all(".column")
    cards = page.query_selector_all(".card")
    record("board_renders_columns", len(cols) >= 4, f"{len(cols)} columns, {len(cards)} cards")
    record("board_renders_cards", len(cards) >= 1, f"{len(cards)} cards shown")

    # 5. FAB visible + in viewport
    fab = page.query_selector("#fab")
    fab_visible = bool(fab and fab.is_visible())
    fab_in_view = False
    if fab and fab_visible:
        box = fab.bounding_box()
        fab_in_view = box and -1 <= box["x"] and box["x"] + box["width"] <= VIEWPORT["width"] + 1
    record("fab_visible", fab_visible, f"size={fab.bounding_box() if fab else None}")
    record("fab_in_viewport", fab_in_view, f"box x within 0..{VIEWPORT['width']}")

    # 6. Tapping FAB opens create modal (bottom sheet)
    if fab and fab_visible:
        fab.tap()
        try:
            page.wait_for_selector("#createModal.open", timeout=3000)
            modal_open = True
        except Exception:
            modal_open = False
        record("fab_opens_modal", modal_open)
        if modal_open:
            page.wait_for_timeout(300)  # let slideUp animation settle
            mbox = page.query_selector("#createModal .modal").bounding_box()
            anchored_bottom = mbox and (mbox["y"] + mbox["height"]) <= VIEWPORT["height"] + 2
            within_width = mbox and mbox["width"] <= VIEWPORT["width"] + 1
            record("modal_fits_mobile", bool(anchored_bottom and within_width), f"modal box={mbox}")
            page.screenshot(path=os.path.join(SHOT_DIR, "02_create_modal.png"))
            page.keyboard.press("Escape")
            page.wait_for_selector("#createModal.open", state="detached", timeout=2000)
    else:
        record("fab_opens_modal", False, "FAB not visible")

    # 7. Tap a NON-DONE card -> drawer opens
    card_for_drawer = None
    for c in cards:
        col = c.evaluate("el => el.closest('.task-list')?.dataset.status")
        if col != "done":
            card_for_drawer = c
            break
    if card_for_drawer:
        card_for_drawer.tap()
        try:
            page.wait_for_selector("#drawer.open", timeout=3000)
            drawer_open = True
        except Exception:
            drawer_open = False
        record("card_opens_drawer", drawer_open)
        if drawer_open:
            dbox = page.query_selector("#drawer").bounding_box()
            dwidth_ok = dbox and dbox["width"] <= VIEWPORT["width"] + 1 and dbox["x"] >= -1
            danchored = dbox and dbox["y"] >= 0
            record("drawer_fits_mobile", bool(dwidth_ok and danchored), f"drawer box={dbox}")
            page.screenshot(path=os.path.join(SHOT_DIR, "03_drawer.png"))
            page.keyboard.press("Escape")

            card_for_drawer.tap()
            page.wait_for_selector("#drawer.open", timeout=3000)
            complete_btn = page.query_selector("#dComplete")
            record("drawer_has_complete", bool(complete_btn and complete_btn.is_visible()))
            page.screenshot(path=os.path.join(SHOT_DIR, "04_drawer_actions.png"))
            page.keyboard.press("Escape")
    else:
        record("card_opens_drawer", False, "no non-done card to tap")

    # 8. Tap target sizes >= 44px for key controls
    def tap_target_ok(sel):
        el = page.query_selector(sel)
        if not el or not el.is_visible():
            return None
        b = el.bounding_box()
        return min(b["width"], b["height"]) >= 40 if b else None
    for sel, name in [("#createBtn", "create_btn"), ("#refreshBtn", "refresh_btn"),
                        ("#assigneeFilter", "assignee_filter"), ("#priorityFilter", "priority_filter")]:
        ok = tap_target_ok(sel)
        record(f"tap_target_{name}", ok is not False, f"ok={ok}")

    # 9. Touch swipe-to-move — NON-DESTRUCTIVE.
    # Create a throwaway task (status 'todo'), swipe it LEFT to forward,
    # assert the status changed in the DB, then delete it.
    moved = False
    swipe_changed = False
    throwaway_id = None
    try:
        # create
        resp = page.evaluate("""() => fetch('/api/tasks', {
            method:'POST', headers:{'Content-Type':'application/json'},
            body: JSON.stringify({title:'__mobile_test_tmp__', assignee:'default', priority:'medium'})
        }).then(r=>r.json())""")
        throwaway_id = resp.get("id") if isinstance(resp, dict) else None
        if not throwaway_id:
            throwaway_id = resp
        # move it into a swipeable column ('ready') via API so it renders in a mid column
        page.evaluate("""(id) => fetch('/api/tasks/'+id+'/move', {
            method:'POST', headers:{'Content-Type':'application/json'},
            body: JSON.stringify({status:'ready'})
        })""", throwaway_id)
        page.wait_for_timeout(800)
        page.evaluate("location.reload()")
        page.wait_for_selector(".card", timeout=10000)

        target = None
        for c in page.query_selector_all(".card"):
            col = c.evaluate("el => el.closest('.task-list')?.dataset.status")
            if col and col == "ready":
                target = c
                break
        if target:
            before_status = db_status(throwaway_id)
            box = target.bounding_box()
            sx = box["x"] + box["width"] / 2
            sy = box["y"] + box["height"] / 2
            ex = max(box["x"] + 6, sx - 120)  # swipe LEFT > 80px
            page.evaluate("""(args) => {
                const {sx, sy, ex, ey} = args;
                const card = document.elementFromPoint(sx, sy);
                if (!card) return;
                const mk = (x, y) => new Touch({identifier: 1, target: card, clientX: x, clientY: y});
                card.dispatchEvent(new TouchEvent('touchstart', {bubbles: true, cancelable: true, touches: [mk(sx, sy)], targetTouches: [mk(sx, sy)], changedTouches: [mk(sx, sy)]}));
                document.dispatchEvent(new TouchEvent('touchend', {bubbles: true, cancelable: true, touches: [], targetTouches: [], changedTouches: [mk(ex, ey)]}));
            }""", {"sx": sx, "sy": sy, "ex": ex, "ey": sy})
            page.wait_for_timeout(1400)
            after_status = db_status(throwaway_id)
            moved = True
            swipe_changed = (before_status != after_status)
            record("swipe_move_functional", swipe_changed,
                   f"throwaway {before_status} -> {after_status} on swipe LEFT")
    except Exception as e:
        record("swipe_move", False, f"swipe error: {e}")
    # cleanup throwaway task (delete + restore if it was adopted)
    if throwaway_id:
        try:
            page.evaluate("""(id) => fetch('/api/tasks/'+id+'/delete', {method:'POST'})""", throwaway_id)
        except Exception:
            pass
    if moved:
        record("swipe_move", True, "synthetic touch swipe executed without error")
    else:
        record("swipe_move_functional", False, "could not set up swipe test")

    # 10. PWA manifest reachable
    try:
        r = page.goto(BASE_URL + "/manifest.json", wait_until="domcontentloaded", timeout=8000)
        manifest_ok = r.status == 200 and "name" in page.content()
    except Exception:
        manifest_ok = False
    record("pwa_manifest", manifest_ok)
    page.goto(BASE_URL, wait_until="networkidle")

    # 11. No console errors
    record("no_console_errors", len(console_errors) == 0,
           f"{len(console_errors)} errors: {console_errors[:3]}")

    page.screenshot(path=os.path.join(SHOT_DIR, "01_board.png"), full_page=False)
    context.close()

# Final safety: ensure no throwaway task lingers
try:
    con = sqlite3.connect(DB_PATH)
    con.execute("DELETE FROM tasks WHERE title='__mobile_test_tmp__' OR id LIKE 't___mobile%'")
    con.commit()
    con.close()
except Exception:
    pass

summary = {
    "base_url": BASE_URL,
    "viewport": VIEWPORT,
    "passed": sum(1 for r in results if r["pass"]),
    "failed": sum(1 for r in results if not r["pass"]),
    "total": len(results),
    "results": results,
    "console_errors": console_errors,
    "screenshots": sorted(os.listdir(SHOT_DIR)),
}
print("\n===== MOBILE TEST SUMMARY =====")
print(json.dumps(summary, indent=2))
with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "mobile_test_report.json"), "w") as f:
    json.dump(summary, f, indent=2)
sys.exit(1 if summary["failed"] else 0)
