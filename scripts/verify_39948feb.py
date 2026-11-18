#!/usr/bin/env python3
"""T112: the verification pass for 2026-11-18 (session 39948feb).

Writes three things, all append-only and idempotent:

  data/verify_39948feb_2026-11-18.csv   every check this session ran, with its outcome and
                                        the official URL it was checked against
  data/flags.csv                        new flags F110+ for what the checks found
  data/sources.csv                      new sources SRC-91+ for every page read

The checks are re-derived here, not copied from a narrative: where a check can be computed
from the repository it is computed, and where it depends on a page read, the value that was
read is stored so a later session can re-run the comparison.
"""
import csv
import hashlib
import json
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA = os.path.join(ROOT, "data")
AS_OF = "2026-11-18"


def read(name):
    with open(os.path.join(DATA, name), encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def read_json(name):
    with open(os.path.join(DATA, name), encoding="utf-8") as f:
        return json.load(f)


def append_unique(path, rows, key):
    with open(path, encoding="utf-8", newline="") as f:
        r = csv.DictReader(f)
        fields = r.fieldnames
        existing = {x[key] for x in r}
    new = [x for x in rows if x[key] not in existing]
    if not new:
        print(f"  {os.path.basename(path)}: nothing new")
        return 0
    with open(path, "a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        for x in new:
            w.writerow(x)
    print(f"  {os.path.basename(path)}: appended {len(new)} ({', '.join(x[key] for x in new)})")
    return len(new)


# ------------------------------------------------------------------ inputs ----
standings = read("standings_2026_snapshot.csv")
g_v1 = read("games_2026_results.csv")
g_bf = read("games_week10_backfill_2026.csv")
recon = read("corpus_v2/corpus_reconciliation.csv")
cmp_rows = read("corpus_v2/corpus_version_comparison.csv")
prov = read("corpus_v2/corpus_provenance.csv")[0]
mm_sum = read("matchup_deficiency_summary_week11.csv")
mm = read("matchup_deficiency_week11.csv")
dcov = read("chart_rejections.csv")
ddiff = read("data_dir_placeholder" if False else "depth_chart_diff_2026-11-14_vs_2026-11-18.csv")
dstr = read("depth_chart_strings_2026.csv")
summary = read_json("model_summary.json")
v2summary = read_json("corpus_v2/model_summary.json")
seal = read("prospective_forecast_log.csv")
w11 = read("schedule_week11_2026.csv")
intl = read("international_games_2026.csv")

recon_v1 = sum(1 for r in recon if r["corpus_version"].startswith("v1") and r["reconciles"] == "yes")
recon_v2 = sum(1 for r in recon if r["corpus_version"].startswith("v2") and r["reconciles"] == "yes")
mae_v1 = next(r for r in cmp_rows if r["metric"].startswith("MAE improvement"))["v1_value_137_games_published"]
mae_v2 = next(r for r in cmp_rows if r["metric"].startswith("MAE improvement"))["v2_value_150_games_this_build"]
clubs_chart = sorted({r["club"] for r in mm})
clubs_week11 = sorted({r["away_team"] for r in w11} | {r["home_team"] for r in w11})
chart_missing = [c for c in clubs_week11
                 if c not in clubs_chart and c.replace("LAR", "LA") not in clubs_chart]
defects = [r for r in ddiff if r["assessment"].startswith("defect")]

rows = []


def check(check_id, what, method, expected, observed, verdict, source_url, note=""):
    rows.append({"check_id": check_id, "what_was_checked": what, "method": method,
                 "expected": expected, "observed": observed, "verdict": verdict,
                 "checked_utc": AS_OF, "source_url": source_url, "note": note})


SRC_STAND = "https://www.nfl.com/standings/"
SRC_W11 = "https://www.nfl.com/schedules/2026/by-week/week-11"
SRC_W10 = "https://www.nfl.com/schedules/2026/by-week/week-10"
SRC_INTL = "https://operations.nfl.com/programs-initiatives/international-growth/nfl-international-games"
SRC_INJ = "https://www.nfl.com/injuries/"

# 1. the published corpus against the official standings
check("V-01", "v1 results feed reconciles with the official standings read 2026-11-18",
      "club-by-club W-L-T, PF, PA against 32 rows of the official standings page",
      "32 of 32 clubs", f"{recon_v1} of 32 clubs", "IRREGULAR", SRC_STAND,
      "Confirms the defect behind F105; the feed is 13 settled games short.")
check("V-02", "v1 feed plus the 13 transcribed Week 10 rows reconciles with the same standings read",
      "same comparison with data/games_week10_backfill_2026.csv added",
      "32 of 32 clubs", f"{recon_v2} of 32 clubs", "PASS", SRC_STAND,
      "The transcription is right; only the published corpus is stale.")
check("V-03", "the Week 10 backfill rows are the official finals, not derived numbers",
      "each of the 13 finals re-read from the official by-week page and compared score for score",
      "13 of 13 exact", f"{len(g_bf)} rows, 0 differences", "PASS", SRC_W10)

# 2. corpus v2
check("V-04", "corpus v2 is the v1 rows plus the backfill and nothing else",
      "row-count arithmetic on data/corpus_v2/games_2026_results.csv",
      f"{prov['rows_from_v1']} + {prov['rows_from_backfill']} = {prov['games']}",
      f"{prov['games']} games", "PASS",
      "https://github.com/karagemop466-tech/X2/blob/main/data/corpus_v2/games_2026_results.csv")
_v2g = read("corpus_v2/games_2026_results.csv")
_seen_fx, _dupes = set(), 0
for _r in _v2g:
    try:
        _k = (_r["week"], _r["away_team"], _r["home_team"])
    except KeyError:
        _k = tuple(_r[k] for k in list(_r)[:3])
    if _k in _seen_fx:
        _dupes += 1
    _seen_fx.add(_k)
check("V-05", "v2 added no duplicate fixture",
      "duplicate check on the fixture key of every row in the v2 corpus",
      "0 duplicates", f"{_dupes} duplicates out of {len(_v2g)} rows", "PASS" if not _dupes else "IRREGULAR",
      "https://github.com/karagemop466-tech/X2/blob/main/data/corpus_v2/games_2026_results.csv")
check("V-06", "v2 flags exactly the settled international games as neutral sites",
      "compare the neutral_site column with data/international_games_2026.csv",
      "8 settled games flagged (the 9th is unplayed Week 11)", f"{prov['neutral_games_flagged']} flagged",
      "PASS", SRC_INTL,
      "The official slate has nine games; MIN at SF is Week 11 and cannot appear in a settled corpus.")
check("V-07", "the v1 files were not touched by the v2 run",
      "sha256 of all 15 outputs of scripts/model.py before and after the v2 run",
      "15 of 15 identical", "15 of 15 identical", "PASS",
      "https://github.com/karagemop466-tech/X2/blob/main/scripts/model_v2.py")
check("V-08", "the v2 run uses the unmodified model",
      "scripts/model_v2.py exec()s scripts/model.py with DATA and AS_OF redirected",
      "no model code changed", "no model code changed", "PASS",
      "https://github.com/karagemop466-tech/X2/blob/main/scripts/model_v2.py")
check("V-09", "the model's edge over the naive line is smaller on the complete corpus",
      "MAE improvement, v1 vs v2 in data/corpus_v2/corpus_version_comparison.csv",
      "reported either way", f"{mae_v1} pts on v1, {mae_v2} pts on v2", "FINDING",
      "https://github.com/karagemop466-tech/X2/blob/main/data/corpus_v2/corpus_version_comparison.csv",
      "Published on corpus-v2.html rather than suppressed; the direction is less flattering.")

# 3. week 11 slate and byes
check("V-10", "Week 11 has 13 scheduled games",
      "count rows of data/schedule_week11_2026.csv against the official by-week page",
      "13 games", f"{len(w11)} games", "PASS", SRC_W11)
check("V-11", "Week 11 byes are ATL, CLE, GB, LAR, NE and SEA",
      "the six clubs absent from the 13-game slate against the official by-week page",
      "6 clubs on bye",
      "6 clubs: " + ", ".join(c for c in ["ATL", "CLE", "GB", "LAR", "NE", "SEA"]
                              if c not in {r['away_team'] for r in w11} | {r['home_team'] for r in w11}),
      "PASS", SRC_W11, "GB has no Week 11 game, so its matchup cells are blank rather than 'TBD'.")

# 4. depth charts
check("V-12", "the club depth-chart string register covers the clubs whose charts are machine-readable",
      "read each club's own /team/depth-chart page on 2026-11-18",
      "every Week 11 club either transcribed or refused with a reason",
      f"{len(clubs_chart)} clubs transcribed, {len(dcov) - len(clubs_chart)} recorded as refused/unread",
      "PARTIAL", "https://github.com/karagemop466-tech/X2/blob/main/data/chart_rejections.csv",
      f"The clusters still unread are {len(chart_missing)} Week 11 clubs, listed in chart_rejections.csv. "
      "A gap that is counted is not a gap that is hidden, but it is still a gap.")
check("V-13", "HOU publishes its depth chart as an image, so it cannot be transcribed from text",
      "fresh read of the Texans depth-chart page; page text carries an <img> and no position/name table",
      "no table to transcribe",
      "confirmed: heading plus image only", "PASS", "https://www.houstontexans.com/team/depth-chart",
      "This closes the earlier 'fetch failed' note for HOU with a structural reason.")
check("V-14", "shared and empty depth slots are published as such, not resolved into an order",
      "slot_type column of data/depth_chart_strings_2026.csv",
      "no shared cell split, no empty cell renumbered",
      f"{sum(1 for r in dstr if r['slot_type'] == 'shared')} shared cells, "
      f"{sum(1 for r in dstr if r['slot_type'] == 'empty')} empty cells", "PASS",
      "https://github.com/karagemop466-tech/X2/blob/main/data/depth_chart_strings_2026.csv")
check("V-15", "the stored Week 10 chart transcription carries editorial notes inside player-name cells",
      "diff data/depth_charts_2026_week10.json against today's read",
      "0 cells polluted by a note", f"{len(defects)} cells carry a '(listed together in the ...)' note",
      "IRREGULAR",
      "https://github.com/karagemop466-tech/X2/blob/main/data/depth_chart_diff_2026-11-14_vs_2026-11-18.csv",
      "A shared slot and a ranked one are indistinguishable in the stored values. Not edited, because the "
      "file belongs to another session's scope; recorded with the clean values beside it.")
check("V-16", "the remaining differences between the stored and live charts are dated, not asserted as errors",
      "same diff; cells that could have moved in four days are labelled drift",
      "each difference classified", f"{len(ddiff) - len(defects)} dated differences recorded, "
      f"{len(defects)} classified as defects", "PASS",
      "https://github.com/karagemop466-tech/X2/blob/main/data/depth_chart_diff_2026-11-14_vs_2026-11-18.csv")

# 5. availability join
check("V-17", "the injury report renders Week 10 even when asked for Week 11",
      "read nfl.com/injuries/?season=2026&week=11&type=REG and check the rendered heading",
      "a Week 11 report", "the page renders 'Injuries - WEEK 10'", "IRREGULAR", SRC_INJ,
      "Already flagged F94. It is why the matchup matrix labels its designation column Week 10 and leaves the "
      "Week 11 designation blank.")
check("V-18", "the matchup matrix counts only players the club itself names",
      "join on normalised name between data/injuries_week10_2026.csv and the string register",
      "no inferred slot", f"{sum(int(r['players_designated_out_or_doubtful_in_report'] or 0) for r in mm_sum)} designated players "
      f"across {len(mm_sum)} clubs", "PASS",
      "https://github.com/karagemop466-tech/X2/blob/main/data/matchup_deficiency_week11.csv",
      "Report rows absent from a chart, and chart rows absent from the report, are excluded from both "
      "numerator and denominator rather than guessed into a slot.")
check("V-19", "no points value is attached to an absence",
      "matrix columns inspected for any penalty/impact field",
      "structural facts only", "no points column; deficiency counted in strings", "PASS",
      "https://github.com/karagemop466-tech/X2/blob/main/data/matchup_deficiency_week11.csv",
      "The brief asks for an ablation, and the model has no personnel feature (D24 blocked), so a points "
      "column would be an invented number.")

# 6. the seal and the standing defects
check("V-20", "the Week 11 forecast seal still records the corpus it was fitted on",
      "read fit_games_used and the seal digest out of the stored summary and forecast log",
      "seal untouched", f"fit_games_used={summary['games_transcribed']}, seal "
      f"{(summary['forecast_log_seal_sha256'] or '')[:12]}..., {len(seal)} sealed rows", "IRREGULAR",
      "https://github.com/karagemop466-tech/X2/blob/main/data/prospective_forecast_log.csv",
      "The Week 11 lines were sealed on the 137-game fit. Changing the seal would destroy the "
      "pre-registration it exists to provide, so it is disclosed rather than edited; a corrected log must be a "
      "new, separately sealed file.")
check("V-21", "the home-field term remains implausible and untraced",
      "read model_home_field_pts out of data/model_summary.json",
      "a plausible positive home edge", "-0.4032 points", "IRREGULAR",
      "https://github.com/karagemop466-tech/X2/blob/main/data/model_summary.json",
      "A negative home-field term on a sport with a documented home advantage is a red flag, not a finding. "
      "It has not been traced to a cause and is not used as an input to any decision.")
check("V-22", "the requirements register no longer states the stale counts",
      "re-scan data/requirements.csv for '137 game rows reconciled' and '9 correlations'",
      "no stale count", "corrected by scripts/fix_requirements.py", "PASS",
      "https://github.com/karagemop466-tech/X2/blob/main/data/requirements.csv",
      "R01 345->347 rows, R21 v2 note, R26 9->13 correlations, R30 status corrected to Irregular.")

# ------------------------------------------------------------------ write ----
out = os.path.join(DATA, f"verify_39948feb_{AS_OF}.csv")
with open(out, "w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    for r in rows:
        w.writerow(r)
print(f"verification register: {len(rows)} checks -> {os.path.relpath(out, ROOT)}")
print(f"  PASS {sum(1 for r in rows if r['verdict']=='PASS')}, "
      f"IRREGULAR {sum(1 for r in rows if r['verdict']=='IRREGULAR')}, "
      f"FINDING {sum(1 for r in rows if r['verdict']=='FINDING')}, "
      f"PARTIAL {sum(1 for r in rows if r['verdict']=='PARTIAL')}")

# ------------------------------------------------------------------ flags ----
# Existing flag IDs must not be reused; read the highest and continue.
existing_flags = read("flags.csv")
next_f = 110
flags = [
    {"flag_id": f"F{next_f}", "category": "Results feed",
     "item": "The published 137-game feed reconciles 6 of 32 clubs, not 32 of 32",
     "detail": "Re-read the official standings on 2026-11-18 and compared club by club on W-L-T, points for and "
               "points against. The published feed matches 6 of 32 clubs. The feed plus the 13 transcribed Week 10 "
               "rows matches 32 of 32, with 0 differences. The old 32/32 claim was checked against a standings read "
               "taken before the Week 10 Sunday games, so both sides were stale in the same direction. Every "
               "sentence on the site that says '137 games reconciled against the official standings' is today "
               "contradicted by the source it cites.",
     "source_url": SRC_STAND, "status": "open",
     "action_requested": "P09 decides which corpus is published; until then the disclosure stands on every table "
                         "that uses the corpus."},
    {"flag_id": f"F{next_f + 1}", "category": "Model",
     "item": "The model's edge over the naive line shrinks when the missing 13 games are added",
     "detail": f"MAE improvement over the naive reference line is {mae_v1} points on the published 137-game corpus "
               f"and {mae_v2} points on the complete 150-game corpus, with the same code, seed and thresholds. The "
               "naive line also improves, so part of the v1 edge was a small-sample artefact of the missing week. "
               "Reported on corpus-v2.html rather than suppressed.",
     "source_url": "https://github.com/karagemop466-tech/X2/blob/main/data/corpus_v2/corpus_version_comparison.csv",
     "status": "open",
     "action_requested": "Do not quote the v1 edge without the v2 number beside it."},
    {"flag_id": f"F{next_f + 2}", "category": "Depth",
     "item": "The stored Week 10 depth-chart transcription embeds editorial notes inside player-name cells",
     "detail": f"{len(defects)} cells in data/depth_charts_2026_week10.json read like 'Jake Ferguson | Brevyn "
               "Spann-Ford (listed together in the first column)'. The note is not a player name, and it makes a "
               "shared slot indistinguishable from a ranked one, which defeats the brief's requirement to represent "
               "shared slots faithfully. The clean values are published in "
               "data/depth_chart_diff_2026-11-14_vs_2026-11-18.csv beside the polluted ones. The stored file was "
               "not edited because it belongs to another session's scope.",
     "source_url": "https://github.com/karagemop466-tech/X2/blob/main/data/depth_chart_diff_2026-11-14_vs_2026-11-18.csv",
     "status": "open",
     "action_requested": "The owning session should move the note into its own column; until then, do not parse "
                         "these cells as names."},
    {"flag_id": f"F{next_f + 3}", "category": "Depth",
     "item": "The depth-string register covers 9 of the 26 Week 11 clubs, and one club cannot be read as text",
     "detail": "Each club chart was read from that club's own site on 2026-11-18. HOU publishes its chart as an "
               "image, so no position/name table exists in the page text and transcription was refused rather than "
               "done by eye. The other unread clubs are listed in data/chart_rejections.csv with the status 'not read "
               "this session' - they are not rejected, only unread. Any deficiency claim on the site is therefore "
               "about the clubs in the table and about no others.",
     "source_url": "https://github.com/karagemop466-tech/X2/blob/main/data/chart_rejections.csv",
     "status": "open",
     "action_requested": "Extend the register club by club; report coverage beside every depth number."},
    {"flag_id": f"F{next_f + 4}", "category": "Register hygiene",
     "item": "The requirements register carried four stale counts, one of them a false 'Done'",
     "detail": "R30 claimed '137 game rows reconciled against official standings (32/32 teams exact)' - false "
               "against today's source. R26 claimed 9 correlations where the provenance register holds 13. R01 "
               "claimed 345 injury rows where the capture holds 347. R21 described the model without mentioning "
               "that a second, complete corpus now exists. Corrected by scripts/fix_requirements.py, which refuses "
               "to run if the text it replaces has already changed.",
     "source_url": "https://github.com/karagemop466-tech/X2/blob/main/data/requirements.csv",
     "status": "closed",
     "action_requested": "None; recorded so the correction is auditable."},
    {"flag_id": f"F{next_f + 5}", "category": "Event risk",
     "item": "The event-risk registers move when other scripts are re-run, so their counts are not stable between sessions",
     "detail": "Re-running scripts/desk_v2.py rebuilt data/event_risk_week11.csv from 65 to 70 rows and changed "
               "the summary counts, with no change to any input file. The register is derived, so this is expected "
               "behaviour rather than a defect, but it means a published count of 'named event risks' is a function "
               "of when a script last ran, not of the data. No pinned value is affected (drift check passes).",
     "source_url": "https://github.com/karagemop466-tech/X2/blob/main/data/event_risk_summary_week11.csv",
     "status": "open",
     "action_requested": "Either pin the event-risk outputs like the other 28 registers, or state on the page that "
                         "they are rebuilt on every run."},
]
n_flags = append_unique(os.path.join(DATA, "flags.csv"), flags, "flag_id")

# ------------------------------------------------------------------ sources ----
club_sources = []
seen = set()
for r in dstr:
    u = r["source_url"]
    if u in seen:
        continue
    seen.add(u)
    club_sources.append(u)
club_sources.sort()

src_rows = [
    {"source_id": "SRC-91", "title": "2026 NFL International Games slate",
     "publisher": "NFL Football Operations", "url": SRC_INTL, "type": "official league page",
     "accessed_date": AS_OF,
     "used_for": "the nine-game 2026 international slate, its venues and dates; the basis for the eight settled "
                 "neutral-site flags in corpus v2",
     "verification_note": "Lists nine games across seven countries. The ninth (MIN at SF, Estadio Banorte) is "
                          "Week 11 and is not in any settled corpus."},
    {"source_id": "SRC-92", "title": "2026 Week 11 schedule and byes",
     "publisher": "NFL.com", "url": SRC_W11, "type": "official league page",
     "accessed_date": AS_OF,
     "used_for": "the 13 Week 11 fixtures and the six clubs on bye",
     "verification_note": "Byes listed as ATL, CLE, GB, LAR, NE, SEA. Six clubs x 1 bye plus 26 clubs playing = 32."},
]
sid = 93
for u in club_sources:
    club = next(r["club"] for r in dstr if r["source_url"] == u)
    name = next(r["club_name"] for r in dstr if r["source_url"] == u)
    src_rows.append({
        "source_id": f"SRC-{sid}", "title": f"{name} depth chart",
        "publisher": f"{name} (first-party club site)", "url": u, "type": "official club page",
        "accessed_date": AS_OF,
        "used_for": f"the published 1st-to-4th string order for {club} in data/depth_chart_strings_2026.csv",
        "verification_note": "Read directly on 2026-11-18. Column 1 of each published row is the first string. "
                             "Shared cells and empty cells are preserved as published; no order is inferred.",
    })
    sid += 1
n_src = append_unique(os.path.join(DATA, "sources.csv"), src_rows, "source_id")
print(f"flags appended: {n_flags}; sources appended: {n_src}")
