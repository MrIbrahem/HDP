
You are modifying `me1.py`, a script that scrapes the Wikimedia Meta page "Hardware donation program" and builds a wikitable of applicants. Implement the following changes:

**Checklist**

1. Expand scope to the full "Current donation requests" section — currently only "Draft requests" (via the drafts category) is processed. Add the other subsections under that heading: "Open requests" and "Approved requests not yet delivered," using the same subpage-link-extraction approach (`get_section_by_heading` + `extract_subpage_links`) already used for older sections, since these likely don't have a dedicated tracking category like drafts do.
2. Add a "Global edits (last 3 months)" column. The current `get_global_editcounts` only returns lifetime edit count via `list=globalusers`. Recent-edit-count requires a different query per user/wiki (e.g. `list=usercontribs` with `ucstart`/`ucend` bounding the last 90 days, or `Special:Contributions` count, or `meta=globaluserinfo` with `guiprop=editcount` doesn't give time-bounded counts — likely needs per-wiki `usercontribs` aggregation, or use the `XTools` API (`https://xtools.wmcloud.org/api/...`) which can return edit counts in a date range across wikis if available). Pick one approach, document the API used, and add a `get_recent_editcounts(site, users, days=90)` function returning `{username: count}`.
3. Add a "Home wiki" column. Use `meta=globaluserinfo&guiprop=merged` (or similar) to fetch each user's home wiki (the wiki they're attached to / most active on), and add `get_home_wikis(site, users) -> dict[str, str]`.
4. Update `build_wikitable` to add the two new columns (Home wiki, Global edits last 3 months) to the header and each row, keeping the existing columns (Page, Last edited, User, Global edits).
5. Update the `data` dicts in `main()` to carry `home_wiki` and `recent_editcount` per user, batch-fetch them once per section (not per user, to avoid rate-limiting), and pass them into the row tuples.
6. Keep output writing to `OUTPUT_FILE` and `OUTPUT_FILE_TABLE` as-is, just with the richer table.
7. Add basic rate-limit/retry handling for the new API calls, consistent with the existing `time.sleep`/backoff pattern in `get_category_members_titles`.
8. Add a way to run this on a recurring schedule (every few months) — e.g. a `cron`-friendly entry point, or note in the docstring how to schedule it (cron, GitHub Actions scheduled workflow, etc.), since the employer wants regular updates.
9. Test against the live "Current donation requests" section (Open requests, Draft requests, Approved requests not yet delivered) and confirm the table renders correctly with all four data columns before saving.

**Execution steps**

1. Read the existing `me1.py` fully to preserve its conventions (error handling, logging, `site.get` usage pattern).
2. Investigate which MediaWiki/XTools API endpoint reliably returns edit counts limited to a 90-day window across all Wikimedia projects (global), and which one returns "home wiki." Test both against 2-3 known usernames before wiring them into the script.
3. Write `get_recent_editcounts()` and `get_home_wikis()`, batching requests for all users in a section rather than looping one-by-one.
4. Update `SECTION_HEADINGS` and the section-processing logic in `main()` to cover "Open requests" and "Approved requests not yet delivered" in addition to "Draft requests."
5. Update `build_wikitable()` and the row-building loop in `main()` to include the two new columns.
6. Run the script end-to-end against the live page, inspect `table.wiki` for correctness (column order, formatting, "unknown" fallback behavior).
7. Add scheduling instructions/config (cron line, or scheduled task) per requirement #8.
8. Report back: which API was used for recent edit counts and home wiki, any rate-limit constraints discovered, and confirm the script ran cleanly.


# Xtools:
## Global Contributions
> GET /api/user/globalcontribs/{username}/{namespace}/{start}/{end}/{offset}
>> Get global edits made by a user, IP or IP range across all Wikimedia projects.

### Parameters
* username (required) – Username or IP address.
* namespace – Namespace ID or all (default) for all namespaces.
* start – Start date in the format YYYY-MM-DD. Leave this and end blank to retrieve the most recent data.
* end – End date in the format YYYY-MM-DD. Leave this and start blank to retrieve the most recent data.
* offset – Shows edits created before the given timestamp. This is used for pagination. If there is more than one page of results, continue is returned, with the offset timestamp as the value.
### Examples
* Get edits made by Jimbo Wales across all wikis:

> https://xtools.wmcloud.org/api/user/globalcontribs/Jimbo_Wales/all/2026-01-01/2026-05-01


```
{
  "username": "Mr. Ibrahem",
  "namespace": "all",
  "start": "2026-01-01",
  "end": "2026-05-01",
  "limit": 50,
  "project": "meta.wikimedia.org",
  "globalcontribs": [
    ...
  ],
  "continue": "2026-05-01T00:05:01Z",
  "elapsed_time": 0.483
}
```
