"""Control baselines for every leaderboard run (session 6ee4d13e, T96).

Called from scripts/model.py after the leaderboard summaries are built, so the control is
computed on the EXACT bets each run made (unrounded walk-forward predictions), not on the
1-decimal values written to data/model_backtest.csv. That CSV rounds one game onto the
3.0-point bet threshold, which is why re-deriving bets from it gives 59 M3 bets, not 58.

Question answered: on the SAME games each leaderboard run bets, how does the run's mean edge
compare with (a) random picks and (b) always backing the reference-line favourite?

Conventions copied from scripts/model.py:
  * edge (side)  = (actual_margin - reference_margin) * (+1 if bet home / -1 if bet away)
  * edge (total) = (actual_total  - reference_total ) * (+1 if over   / -1 if under)
  * a push (edge == 0) is excluded from side and total runs, as in summarise()
  * a parlay (P1) is kept whole, as in summarise() for kind == "parlay"
  * the favourite is the team the reference line favours; a zero reference margin has no favourite

Random control: DRAWS draws with a fixed seed. Each draw picks a side (and, for P1, a total)
uniformly at random on each bet game. Favourites control: paired on the same decided games; the
per-game difference (strategy edge minus favourite edge) is bootstrapped over games.

A run whose recomputed bet count or mean edge does not equal the published summary raises an
error, so a control can never be reported against a different bet set.
"""
import csv
import random

DRAWS = 10000
BOOT = 5000
SRC = "https://www.nfl.com/schedules/2026/by-week/week-10"   # same schedule source as the leaderboard rows

FIELDS = ["strategy_id", "control", "market", "n_bet_games", "n_decided", "strategy_mean_edge",
          "control_mean_edge", "control_edge_p025", "control_edge_p975",
          "share_random_draws_at_least_strategy", "strategy_minus_control", "diff_ci_low", "diff_ci_high",
          "control_hit_rate", "strategy_hit_rate", "reproduced_bets", "reproduced_mean_edge",
          "status", "method_note", "source_url"]

RANDOM_NOTE = ("Expected random edge is 0 by construction: a side and its opposite average to zero. "
               "Interval = 2.5th to 97.5th percentile of the seeded draws; share = fraction of draws whose "
               "mean edge is at least the strategy's.")
FAV_NOTE = ("Paired on the same decided games (a game with a zero reference margin has no favourite and is dropped): "
            "strategy edge minus favourite edge, bootstrapped over games. "
            "A CI that excludes zero means the strategy's side choice beat simply backing the reference-line "
            "favourite on these games.")


def _pct(sorted_vals, q):
    k = (len(sorted_vals) - 1) * q
    lo = int(k)
    hi = min(lo + 1, len(sorted_vals) - 1)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (k - lo)


def _mean(xs):
    return sum(xs) / len(xs)


def _row(**kw):
    row = {k: "" for k in FIELDS}
    row["source_url"] = SRC
    row.update(kw)
    return row


def _legs(kind, decided, index, bets_by_key):
    """Per decided bet: the actual and reference inputs and the strategy's own edge."""
    out = []
    for b in decided:
        g = index[(b["week"], b["home"], b["away"])]
        a_side = g["actual_margin"] - g["ref_margin"]
        a_tot = g["actual_total"] - g["ref_total"]
        fav = "home" if g["ref_margin"] > 0 else ("away" if g["ref_margin"] < 0 else None)
        if kind == "side":
            e = a_side * (1 if b["side"] == "home" else -1)
            out.append({"e": e, "a_side": a_side, "a_tot": None, "fav": fav})
        elif kind == "total":
            e = a_tot * (1 if b["side"] == "over" else -1)
            out.append({"e": e, "a_side": None, "a_tot": a_tot, "fav": None})
        else:
            e_s = a_side * (1 if b["side"] == "home" else -1)
            e_t = a_tot * (1 if b["total"] == "over" else -1)
            if abs((e_s + e_t) - b["edge"]) > 1e-9:
                raise SystemExit("parlay legs do not sum to the published edge")
            out.append({"e": e_s + e_t, "a_side": a_side, "a_tot": a_tot, "fav": fav, "hit": b["hit"]})
    return out


def run(oos, summaries, seed):
    """oos: walk-forward rows from model.py. summaries: [(summary_dict, label, market)] from model.py.
    Returns one row per (strategy, control) for the leaderboard runs."""
    index = {(r["week"], r["home_team"], r["away_team"]): r for r in oos}
    rng = random.Random(seed)
    rows = []

    for summary, _label, _market in summaries:
        sid = summary["strategy_id"]
        kind = summary["kind"]                       # "side", "total" or "parlay"
        market = {"side": "Game side (spread)", "total": "Game total", "parlay": "Parlay"}[kind]
        decided = summary["bets"] if kind == "parlay" else [b for b in summary["bets"] if b["hit"] is not None]
        legs = _legs(kind, decided, index, None)
        n = len(legs)
        strat_mean = _mean([l["e"] for l in legs]) if n else None
        if n != summary["n_bets"] or abs(strat_mean - summary["mean_edge_points"]) > 1e-9:
            raise SystemExit(f"{sid}: baseline reproduction failed: bets {n} vs {summary['n_bets']}, "
                             f"mean edge {strat_mean} vs {summary['mean_edge_points']}")
        if kind == "parlay":
            strat_hit = sum(l["hit"] for l in legs) / n
        else:
            strat_hit = sum(1 for l in legs if l["e"] > 0) / n

        # ---- control A: random picks on the same games
        draws, draw_hits = [], []
        for _ in range(DRAWS):
            tot = 0.0
            hits = 0
            for l in legs:
                if kind == "parlay":
                    e_s = l["a_side"] * rng.choice([1, -1])
                    e_t = l["a_tot"] * rng.choice([1, -1])
                    tot += e_s + e_t
                    hits += 1 if (e_s > 0 and e_t > 0) else 0
                else:
                    a = l["a_side"] if kind == "side" else l["a_tot"]
                    e = a * rng.choice([1, -1])
                    tot += e
                    hits += 1 if e > 0 else 0
            draws.append(tot / n)
            draw_hits.append(hits / n)
        ds = sorted(draws)
        share_ge = sum(1 for d in draws if d >= strat_mean) / DRAWS
        rand_mean = _mean(draws)
        rows.append(_row(
            strategy_id=sid, control="Random picks (same games, seeded draws)", market=market,
            n_bet_games=len(summary["bets"]), n_decided=n,
            strategy_mean_edge=round(strat_mean, 3), control_mean_edge=round(rand_mean, 3),
            control_edge_p025=round(_pct(ds, 0.025), 3), control_edge_p975=round(_pct(ds, 0.975), 3),
            share_random_draws_at_least_strategy=round(share_ge, 4),
            strategy_minus_control=round(strat_mean - rand_mean, 3),
            control_hit_rate=round(_mean(draw_hits), 3), strategy_hit_rate=round(strat_hit, 3),
            reproduced_bets=n, reproduced_mean_edge=round(strat_mean, 3),
            status="Computed", method_note=RANDOM_NOTE))

        # ---- control B: favourites only (reference-line favourite on the same games)
        if kind == "total":
            rows.append(_row(
                strategy_id=sid, control="Favourites only (reference-line favourite)", market=market,
                n_bet_games=len(summary["bets"]), reproduced_bets=n, reproduced_mean_edge=round(strat_mean, 3),
                status="Not applicable",
                method_note="A total has no favourite on the reference line, so this control is not defined."))
            continue
        if kind == "parlay":
            rows.append(_row(
                strategy_id=sid, control="Favourites only (reference-line favourite)", market=market,
                n_bet_games=len(summary["bets"]), reproduced_bets=n, reproduced_mean_edge=round(strat_mean, 3),
                status="Not applicable",
                method_note=("The parlay's total leg has no favourite on the reference line, so a favourites-only "
                             "parlay is not defined.")))
            continue

        pairs = []
        for l in legs:
            if l["fav"] is None:
                continue
            e_fav = l["a_side"] * (1 if l["fav"] == "home" else -1)
            pairs.append((l["e"], e_fav))
        m = len(pairs)
        diffs = [s_ - f_ for s_, f_ in pairs]
        boot = []
        for _ in range(BOOT):
            boot.append(_mean([diffs[rng.randrange(m)] for _ in range(m)]))
        boot.sort()
        fav_mean = _mean([f_ for _s, f_ in pairs])
        rows.append(_row(
            strategy_id=sid, control="Favourites only (reference-line favourite)", market=market,
            n_bet_games=len(summary["bets"]), n_decided=m,
            strategy_mean_edge=round(_mean([s_ for s_, _f in pairs]), 3),
            control_mean_edge=round(fav_mean, 3),
            strategy_minus_control=round(_mean(diffs), 3),
            diff_ci_low=round(_pct(boot, 0.025), 3), diff_ci_high=round(_pct(boot, 0.975), 3),
            control_hit_rate=round(sum(1 for _s, f_ in pairs if f_ > 0) / m, 3),
            strategy_hit_rate=round(strat_hit, 3),
            reproduced_bets=n, reproduced_mean_edge=round(strat_mean, 3),
            status="Computed", method_note=FAV_NOTE))

    # ---- context row: the reference favourite on EVERY out-of-sample game, not only on bet games
    pairs_all = []
    for r in oos:
        ref = r["ref_margin"]
        if ref == 0:
            continue
        pairs_all.append((r["actual_margin"] - ref) * (1 if ref > 0 else -1))
    m_all = len(pairs_all)
    boot = sorted(_mean([pairs_all[rng.randrange(m_all)] for _ in range(m_all)]) for _ in range(BOOT))
    rows.append(_row(
        strategy_id="ALL", control="Favourites only, every out-of-sample game (context)",
        market="Game side (spread)", n_bet_games=len(oos), n_decided=m_all,
        control_mean_edge=round(_mean(pairs_all), 3),
        control_edge_p025=round(_pct(boot, 0.025), 3), control_edge_p975=round(_pct(boot, 0.975), 3),
        control_hit_rate=round(sum(1 for x in pairs_all if x > 0) / m_all, 3),
        reproduced_bets=len(oos), status="Computed",
        method_note=("Context row, not a strategy. The reference-line favourite on every out-of-sample game, "
                     "with a bootstrap interval over games. It shows whether the favourite control is weak "
                     "in general or only on the games a strategy chose.")))
    return rows


def write(rows, path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow(r)
