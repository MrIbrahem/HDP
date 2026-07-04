# HDP — Codebase Audit Report

**Audit date:** 2026-07-04
**Audited at commit:** `d711503`
**Auditor:** `improve` skill (standard effort, no subagents — repo is ~1.3K lines, single-maintainer bot)
**Baseline:** `python -m pytest` → 15 passed (tests at `tests/wtp_parse/` only)

---

## Scope of audit

**Audited:**

-   All Python under `src/`, `run.py`, `update.py`, `tests/`
-   Config: `pyproject.toml`, `pytest.ini`, `requirements.txt`, `.env.example`, `.gitignore`
-   Docs: `README.md`, `AGENTS.md`, `docs/plan.md` (noted as stale planning doc, not a spec)

**Not audited:**

-   Live network behavior against the real Meta page (no `.env`/credentials in audit environment)
-   `src/v1.py` (declared legacy in AGENTS.md)
-   Contents of `edit_counts_cache.json` (cache state — committed and always dirty, per AGENTS.md; treated as data not code)
-   `.github/` (no workflow references in repo docs; recon did not inspect — low expected signal for a single-user bot repo)
-   Actual wikimedia rendering of generated `.wiki` files

---

## Conventions observed (executor / maintainer reference)

-   **Python 3.13 target.** Modern union syntax (`str | None`, `X | None`), `datetime.now(UTC)`.
-   **Logging:** per-project-namespace setup via `src.setup_logging()` (`name="src"`); modules do `logger = logging.getLogger(__name__)`; `propagate = False`. Do NOT add `basicConfig` or root handlers.
-   **Line length 120**, black + isort (black profile) + ruff + mypy; all targeting py313. Lint config in `pyproject.toml`.
-   **Throttle convention:** 0.3s after each _uncached_ network fetch in the editcounts loop (gated by `was_cached`); 0.1s inside `get_home_wikis_and_registration`. Preserve when refactoring.
-   **Cache invariant:** `edit_counts_cache.json` shape is `{username: {date: count}, "_meta": {username: {"start", "end"}}}`; `META_KEY = "_meta"` reserved; `save_cache` is the only writer (atomic temp + `os.replace`). Don't hand-edit.
-   **Column-add invariant (AGENTS.md §"Conventions"):** when adding a wikitable column, update (a) `build_wikitable` header + row append, (b) `row_data` dict in `load_rows`, (c) `table_headers_to_row_key` in `update`, in that order — otherwise the in-place update path silently drops the column.
-   **`Johnjoy12` debug log block** in `solve_users_redirects` is intentional (watchpoint) — do not remove without asking.

---

## Findings

Ordered by leverage (impact ÷ effort, discounted by confidence and fix-risk).

### [CORRECTNESS-01] `python -m update` passes a category string as a section title — produces an empty subpage list and a silent no-op update of the live HDP page

-   **Evidence**:
    -   `update.py:40` — passes `section_name="Category:Hardware donation program open requests"` into `v3.update(...)`.
    -   `src/v3.py:258-261` — `if section_name:` branch calls `get_subpages_for_section(site, full_wikitext, BASE_PAGE, section_title=section_name)`.
    -   `src/load_subpages.py:18` — `SECTIONS_TO_CATEGORY = {"Draft requests": "Category:Hardware donation program drafts"}`. The passed string is NOT a key here.
    -   `src/load_subpages.py:29-45` — `category_name = SECTIONS_TO_CATEGORY.get(section_title)` returns `None`, so control falls to the `else` branch, which calls `get_section_by_heading(full_wikitext, "Category:Hardware donation program open requests")`. No heading has that title on the live HDP page, so the function logs a warning and returns `[]`.
-   **Impact**: The documented live-update entrypoint (`python -m update`) silently fetches zero subpages, builds empty `rows`, and writes back the original wikitext (the table is left untouched because no row keys match). The operator believes the page was updated; in reality nothing happened. AGENTS.md itself describes `update` as "updates User:Mr. Ibrahem/hdp page (live wikitext in-place update)" — i.e. it is expected to work and is broken in its current call shape.
-   **Effort**: S.
-   **Risk**: MED. The fix is small, but the correct shape depends on how the live `User:Mr. Ibrahem/hdp` page is actually structured (does it contain a section titled `"Open requests"`? or is the intent to feed a _category_ name through a category-mapping branch that doesn't exist?). Two viable fix shapes; needs maintainer confirmation (see Direction #1).
-   **Confidence**: MED (high that the current path is broken; MED on the intended contract, since the page may have been hand-edited to include such a heading historically).
-   **Fix sketch**: Either (a) add `"Category:Hardware donation program open requests"` (or a normalized variant) into `SECTIONS_TO_CATEGORY` so the category-resolution branch is taken, or (b) — preferred — generalize `update.py` to iterate the same section list `run.py` already maintains (see Direction #1) and drop the single hardcoded `section_name` arg.

### [CORRECTNESS-02] Partial pagination failure in `_get_recent_editcount` is recorded as a fully-fetched range in `_meta`, permanently undercounting the user on all future cached runs

-   **Evidence**:
    -   `src/api/xtools_cached.py:73-84` — on a `requests` exception after some `total_by_day` has accumulated, the function returns the partial dict ("We got partial data before the failure; treat as a lower bound"). The retry/exhaustion branch (lines 79-84) also returns the partial dict once `delay >= max_delay`.
    -   `src/api/xtools_cached.py:219-231` — in the partial-overlap path, after calling `_get_recent_editcount(username, _iso(fetch_start), end)`, the code does `user_counts.update(new_days)` and **unconditionally** writes `cache[META_KEY][username] = {"start": _iso(new_start), "end": _iso(new_end)}`, regardless of whether the fetch actually completed or returned a partial lower-bound.
    -   `src/api/xtools_cached.py:238-247` — same pattern in the no-cache-entry branch: `fetched = _get_recent_editcount(...)`; if `fetched` is non-empty (which includes partial failures), `cache[META_KEY][username] = {"start": start, "end": end}` is recorded.
-   **Impact**: Once a user's fetch fails partway (network blip, XTools 5xx mid-pagination, `max_pages` cap of 50 hit), the cache records the _full_ requested window as already fetched. Every subsequent run treats the window as covered (`cached_end >= req_end` at lines 202-204) and sums only the days actually present — silently understating the user's recent edit count in the published wiki table, permanently, with no warning. The committed `edit_counts_cache.json` could already contain such silent undercounts for any user that ever hit a transient XTools error.
-   **Effort**: M (needs a small regression test against a mocked fetch that fails on page 2 of 3).
-   **Risk**: MED. Touches the cache invariant. The fix must distinguish "completed fetch" from "partial fetch" in `_get_recent_editcount`'s return contract, and only record `_meta` on full success.
-   **Confidence**: HIGH (read the code; the unconditional `_meta` write is clear).
-   **Fix sketch**: Have `_get_recent_editcount` return a sentinel (e.g. a `(counts, complete: bool)` tuple, or raise a custom `PartialFetchError` carrying the partial dict) so the caller can decide whether to update `_meta`. On partial: merge whatever days arrived but do NOT advance `_meta.end`; log a warning. Add a regression test using a mocked `requests.get` that raises on the second call.

### [TESTS-03] No tests exist outside `wtp_parse/` — orchestrator, cache pipeline, API wrappers, and `load_subpages` are 0% covered

-   **Evidence**: `tests/` contains only `tests/wtp_parse/test_wtp_tables.py` (12 tests) and `tests/wtp_parse/test_wtp_links.py` (3 tests). `pytest.ini:8` declares `testpaths = tests` but no other test files exist. `v3.load_rows`, `v3.build_wikitable`, `v3.update`, `v3.solve_users_redirects`, `xtools_cached.*`, `mwclient_req.*`, `category.*`, `load_subpages.*` have zero direct tests.
-   **Impact**: Both CORRECTNESS-01 and CORRECTNESS-02 shipped because nothing exercises the affected paths. Any future change to `load_rows`, the cache invariant, or the section/category mapping is likewise unguarded. AGENTS.md implies the suite is "15 tests, all in `tests/wtp_parse/`" — i.e. the gap is acknowledged, not accidental.
-   **Effort**: M (a focused characterization-test pass for the cache pipeline and `load_subpages`, mocking `mwclient.Site` and `requests.get`).
-   **Risk**: LOW (additive only — no behavior changes).
-   **Confidence**: HIGH.
-   **Fix sketch**: Add `tests/test_xtools_cached.py` (mocked `_get_recent_editcount` exercising full, partial-failure, gap, and overlap paths; assert `_meta` only advances on full success — this test also anchors CORRECTNESS-02). Add `tests/test_load_subpages.py` (mocked `site.get` for the category-members branch + a wikitext string for the heading branch; assert the section/category match logic that CORRECTNESS-01 depends on). Use the existing `tests/wtp_parse/test_wtp_tables.py` as the structural pattern (local `@pytest.fixture`, no conftest).

### [TECH-DEBT-04] `src/api/xtools.py` duplicates the fetch loop already in `xtools_cached.py` and is imported by nothing in the current flow

-   **Evidence**:
    -   `src/api/xtools.py:1-89` is character-for-character the same `_get_recent_editcount` as `src/api/xtools_cached.py:40-106` (same constants `RECENT_DAYS`/`XTOOLS_GLOBALCONTRIBS_URL`/`HEADERS`, same retry/backoff, same `max_pages = 50`, same `total_by_day` accumulation, same commented-out `time.sleep(0.3)` at line 85).
    -   Grep for `from .xtools import` / `from src.api.xtools import` returns zero matches anywhere in the repo. `v3.py:24` imports only from `xtools_cached`.
    -   `requirements.txt` and `pyproject.toml` make no reference to it.
-   **Impact**: Every future fix to the XTools fetch loop (e.g. CORRECTNESS-02) must be applied in two files or it silently diverges. Drift is already visible (the cached version has the `_meta` bookkeeping the uncached version lacks). Dead code inflates onboarding surface.
-   **Effort**: S.
-   **Risk**: LOW — but confirm no external caller (e.g. a sibling repo or a Toolforge cron job) imports `xtools.py` directly before deleting. If unsure, deprecate-first (re-export from `xtools_cached`) rather than delete.
-   **Confidence**: HIGH (no internal callers; `__all__` in both files is non-overlapping so no import-wildcard risk).
-   **Fix sketch**: Delete `src/api/xtools.py`. If external callers are a concern, replace the file body with `from .xtools_cached import get_recent_editcounts_cached as get_recent_editcounts  # noqa` for one release cycle. Run `python -m pytest` and `ruff check .` as the gate.

### [PERF-05] `load_rows` runs API calls sequentially per user with no batching or concurrency

-   **Evidence**:
    -   `src/v3.py:124-137` — `get_global_editcounts` (one batched call), then `get_recent_editcounts_cached` (sequential XTools per user), then `get_home_wikis_and_registration` (one `meta=globaluserinfo` per user + `time.sleep(0.1)`).
    -   `src/api/mwclient_req.py:287-294` — loop over users calling `get_global_userinfo` one at a time; `meta=globaluserinfo` only accepts a single username so this cannot be batched but _can_ be parallelized.
-   **Impact**: Scales linearly with user count. On the HDP scale (dozens of users) this is minutes, not hours, so M rather than L. Real cost is on iteration time during development / cache-warm runs.
-   **Effort**: M.
-   **Risk**: MED — `mwclient.Site` is stateful and not documented as thread-safe; concurrency would need a connection pool or one `Site` per worker. XTools rate-limits too. Not a drop-in `ThreadPoolExecutor` over the existing call sites.
-   **Confidence**: HIGH (the linear pattern is obvious); fix ROI is MED (see Impact).
-   **Fix sketch**: If pursued, isolate per-worker `mwclient.Site` instances (re-login each) and use `concurrent.futures.ThreadPoolExecutor` with `max_workers=3-4` only over the XTools calls; keep `mwclient` calls sequential (or batched where the API allows). Add a throttle guard honoring the 0.3s-per-uncached-fetch convention.

### [TECH-DEBT-06] `solve_pages_redirects` batches 30 titles instead of the API max of 50, and logs an end index past the list

-   **Evidence**: `src/api/mwclient_req.py:214` — `for i in range(0, len(pages), 30):`. `src/api/mwclient_req.py:216` — `logger.info(f"Fetching {i} - {i + 30}...")` reports `i + 30` even on the last short group.
-   **Impact**: Extra API requests on large user lists; misleading log line on the tail batch. Minimal at current scale.
-   **Effort**: S.
-   **Risk**: LOW.
-   **Confidence**: HIGH.
-   **Fix sketch**: Use `batch_size = 50` and log `min(i + batch_size, len(pages))`.

### [TECH-DEBT-07] Legacy `v1.py` ships in `src/`; `requirements.txt` has unpinned transitive deps

-   **Evidence**: `src/v1.py` exists and is imported nowhere (AGENTS.md confirms legacy). `requirements.txt:4-6` lists `wikitextparser`, `colorlog`, `tqdm` with no version specifiers; `requests`, `mwclient`, `python-dotenv` use `>=` lower bounds only.
-   **Impact**: Onboarding confusion (new contributors must read AGENTS.md to learn `v1.py` is dead); reproducibility gap (a breaking `wikitextparser` release would silently change table-parse behavior — and the only tests in the repo depend on that library's exact cell/row semantics).
-   **Effort**: S.
-   **Risk**: LOW.
-   **Confidence**: HIGH.
-   **Fix sketch**: Delete `src/v1.py`. Pin `wikitextparser`, `colorlog`, `tqdm` to compatible release ranges (e.g. `wikitextparser>=0.5,<1` after checking the installed version on a green run) and regenerate a `requirements.lock` / pin the resolver if reproducibility matters to the operator.

### [TECH-DEBT-08] Blanket `except Exception` throughout `mwclient_req.py` and `xtools_cached.py` swallows all errors, making "API down" indistinguishable from "user has 0 edits"

-   **Evidence**: `src/api/mwclient_req.py:38-40,60-62,93-95,132-134,173-175,220-222,266-269` (7 bare `except Exception` returning `""`, `None`, `[]`, or `{}`). `src/api/xtools_cached.py:73-84` catches `requests.RequestException` more narrowly but still returns partial data as a "lower bound" without surfacing the failure to the caller.
-   **Impact**: The orchestrator (`load_rows`) treats "API hiccup" and "legitimate empty result" identically → bad data reaches the wiki table silently. This is the upstream cause that makes CORRECTNESS-02's undercount invisible to the operator. It also blocks meaningful logging: only `logger.error(...)` lines indicate failure, and nothing rolls them up.
-   **Effort**: M.
-   **Risk**: MED — changing return contracts (e.g. raising a custom `ApiUnavailable` exception, or returning a `Result[T, Error]` sentinel) ripples through every caller in `v3.py` and `load_subpages.py`. Must be gated behind TESTS-03.
-   **Confidence**: HIGH.
-   **Fix sketch**: Define a small set of typed exceptions (`MwclientApiError`, `XtoolsApiError`) and a sentinel `UNAVAILABLE` constant. Have callers branch on the sentinel and emit a warning row in the table (e.g. "API unavailable — retry later") instead of inventing a 0. Write the tests in TESTS-03 first.

### [DX-09] `get_home_wikis_and_registration` sleeps 0.1s after the last user (pointless), and the throttle pattern is not centralized

-   **Evidence**: `src/api/mwclient_req.py:287-296` — `for username in tqdm(...): ... time.sleep(0.1)` sleeps even after the final iteration.
-   **Impact**: Trivial runtime cost; minor DX inconsistency vs. the cached-XTools path which centralizes the throttle behind `was_cached`.
-   **Effort**: S.
-   **Risk**: LOW.
-   **Confidence**: HIGH.
-   **Fix sketch**: Move the sleep to the top of the loop guarded by "not first iteration", or behind an `index < len - 1` check. Match the cached-XTools convention of "only sleep when you actually hit the network for the previous item".

### [DX-10] No in-repo CI workflow / pre-commit / test-runner script declared

-   **Evidence**: Recon found no `tox.ini`, no `Makefile`, no `.pre-commit-config.yaml`. `.github/` exists but was not inspected. `pyproject.toml` declares tools but no `[project.scripts]` or task runner. The README's "Testing & linting" section lists four commands the operator must invoke directly.
-   **Impact**: CORRECTNESS-01 and CORRECTNESS-02 both shipped with no automated gate. A trivial GitHub Action running `python -m pytest && ruff check . && mypy src` on push would catch the next one.
-   **Effort**: S.
-   **Risk**: LOW.
-   **Confidence**: MED (did not open `.github/`; if a workflow already exists there, this finding is moot — verify).
-   **Fix sketch**: Add `.github/workflows/ci.yml` running `python -m pytest`, `ruff check .`, and `mypy src` on Python 3.13 across push/PR. Cache pip with `actions/setup-python@v5`'s built-in caching.

---

## Direction findings (options for the maintainer, not ranked against bugs)

### Direction 1 — Generalize `update.py` over the full section set the live page contains

The fragility that produced CORRECTNESS-01 is structural: `update.py` hardcodes a single `section_name` and threads it through a function whose contract mixes "section heading" and "category name" by lookup table. `run.py:25-31` already maintains the intended section list (`"Current donation requests"`, `"Approved requests not yet delivered"`, `"Draft requests"`, etc.) — most commented out. Let `update.py` iterate the un-commented subset of the same list (or a small config table) per section, and drop the `section_name` arg entirely. This makes CORRECTNESS-01 moot in a way that a one-line fix does not. Trade-off: small effort, but requires confirming that `update_wikitable_data` correctly handles a page with multiple tables under multiple `===` sections (the existing tests cover multiple tables in one wikitext — see `tests/wtp_parse/test_wtp_tables.py:282-314`).

### Direction 2 — Add a `--dry-run` / diff mode to `update.py`

`update_wikitable_data` is pure-string-in/string-out (`src/wtp_parse/wtp_tables.py:84-103`), and `update()` already calls `file.write_text(...)` at the end (`src/v3.py:287-289`). A `--dry-run` flag would skip the write and print a unified diff between the fetched wikitext and the rewritten wikitext via Python's `difflib.unified_diff`. Because the operator currently pastes the generated `.wiki` back into Meta by hand, a diff stage would catch silent no-ops (like the one in CORRECTNESS-01) and unintended edits before they reach the live page. Trade-off: ~30 lines, no new dependencies, high safety value for a human-in-the-loop workflow.

### Direction 3 — Collapse the free-function / `MwclientApi` duplication in `mwclient_req.py`

The file defines both `def get_page_wikitext(site, ...)` and `MwclientApi.get_page_wikitext(self, ...)` calling the free function, and the call sites mix conventions: `v3.py` calls `connect_to_meta(...)` (free), then uses `MwclientApi(site)` for some calls but passes the bare `site` into `get_subpages_for_section(site, ...)` (`src/v3.py:216`). The class exists as a facade; the free functions exist as the implementation detail. Pick one (the class) and route the facade call sites through it consistently, with the free functions becoming module-private (`_get_page_wikitext`). Trade-off: medium mechanical effort, mostly import-line churn; low behavioral risk but high churn-risk if done hastily. Gate behind TESTS-03.

---

## Prioritization summary

| #   | Finding                                   | Category    | Impact | Effort | Risk | Confidence | Suggested plan?                       |
| --- | ----------------------------------------- | ----------- | ------ | ------ | ---- | ---------- | ------------------------------------- |
| 1   | `update` entrypoint broken                | correctness | M      | S      | MED  | MED        | **YES (P1)**                          |
| 2   | `_meta` records unverified ranges         | correctness | M      | M      | MED  | HIGH       | **YES (P1)**                          |
| 3   | No tests outside `wtp_parse/`             | tests       | M      | M      | LOW  | HIGH       | **YES (P2) — bundle with #4**         |
| 4   | `xtools.py` duplicates `xtools_cached.py` | tech-debt   | L      | S      | LOW  | HIGH       | **YES (P2) — bundled with #3**        |
| 8   | Blanket `except Exception`                | tech-debt   | M      | M      | MED  | HIGH       | **YES (P2) — gated on #3**            |
| —   | Direction #2 dry-run diff mode            | direction   | M      | S      | LOW  | MED        | optional P3                           |
| 5   | Sequential per-user fetches               | perf        | M      | M      | MED  | HIGH       | defer                                 |
| 6   | 30-batch vs 50-batch + tail log           | tech-debt   | S      | S      | LOW  | HIGH       | defer                                 |
| 7   | `v1.py` dead + unpinned deps              | tech-debt   | S      | S      | LOW  | HIGH       | defer                                 |
| 9   | Tail sleep in home-wiki loop              | dx          | S      | S      | LOW  | HIGH       | defer (or fold into #5)               |
| 10  | No CI workflow                            | dx          | M      | S      | LOW  | MED        | optional P3 (verify `.github/` first) |
| —   | Direction #1 generalize update            | direction   | M      | S      | MED  | MED        | alternative to #1                     |
| —   | Direction #3 collapse mwclient dup        | direction   | M      | M      | MED  | MED        | defer                                 |

## Findings considered and rejected

-   **"Pinning the exact `wikitextparser` version is urgent."** Not urgent — the only tests in the repo pin its behavior implicitly; a breaking release would surface as test failures, not silent corruption. Rolled into TECH-DEBT-07 as a minor note.
-   **"`agents_redirects` hardcoded dict is tech debt."** It is a deliberately-documented source of truth per AGENTS.md. Not a finding.
-   **"The committed `edit_counts_cache.json` should be gitignored."** AGENTS.md explicitly says it is committed on purpose and shows up dirty on every run. Not a finding; the AGENTS.md instruction stands.
-   **"The throttle of 0.3s after uncached fetches is a perf bug."** AGENTS.md explicitly documents the 0.3s throttle and the `was_cached` gate as intended behavior. Not a finding.

## Notes for the next planning / execution pass

-   Dependency ordering: plans for CORRECTNESS-02 (cache invariant) and TECH-DEBT-08 (typed error handling) both require the characterization tests in TESTS-03 to land first. TESTS-03 must precede both.
-   Direction #1 is the structural alternative to CORRECTNESS-01's one-line fix. A maintainer choosing Direction #1 renders CORRECTNESS-01 moot — note this in the plans index when planning.
-   All CHECKED verification commands must run on Python 3.13; `pytest.ini:11` sets `pythonpath = . src` so `from src...` imports work without installation, but executors must `pip install -r requirements.txt` first.
