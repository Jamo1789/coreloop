"""
Play-style analysis: what kind of player made these decisions?

Every Game records its decisions (Game.decisions). This module turns a finished
run into a few behaviour numbers and compares them with the simulated strategies
in simulate.py, so a human run can be labelled "played most like the appeaser".

    python playstyle.py            # table of all logged runs in runs/
    python playstyle.py --bots     # the reference numbers for each bot strategy

play.py saves every run to runs/<date>-<time>.json and shows the analysis at the end.
"""
import argparse
import json
import math
import time
from pathlib import Path

import simulate as S

RUNS_DIR = Path(__file__).parent / "runs"

# name, how to read it, scale used when comparing (difference of one scale = "very different")
FEATURES = [
    ("deep_share",     "casts made in deep water",                      1.0),
    ("deposit_hunger", "avg hunger when you went to deposit",           1.0),
    ("haul_at_deposit", "avg fish carried per deposit",                 3.0),
    ("story_hunger",   "avg hunger when you pushed the story",          1.0),
    ("seita_per_fish", "Seita sacrifices per fish caught",              0.5),
    ("iron_bought",    "iron bought",                                   4.0),
    ("avg_wrath",      "avg wrath while playing",                       50.0),
]


def _mean(xs, default=0.0):
    return sum(xs) / len(xs) if xs else default


def features(g):
    d = g.decisions
    casts = [x for x in d if x["action"].startswith("cast_")]
    deposits = [x for x in d if x["action"] == "deposit"]
    stories = [x for x in d if x["action"] == "story"]
    seita = [x for x in d if x["action"].startswith("seita")]
    return {
        "deep_share": _mean([x["action"] == "cast_deep" for x in casts]),
        "deposit_hunger": _mean([x["hunger"] for x in deposits]),
        "haul_at_deposit": _mean([x["haul"] for x in deposits]),
        "story_hunger": _mean([x["hunger"] for x in stories]),
        "seita_per_fish": len(seita) / max(1, g.fish_caught),
        "iron_bought": sum(x["action"] == "shop:iron" for x in d),
        "avg_wrath": _mean([x["wrath"] for x in d]),
    }


_reference = None


def reference(runs=150):
    """Average features of each bot strategy (computed once, cached)."""
    global _reference
    if _reference is None:
        _reference = {}
        for name in S.STRATEGIES:
            fs = [features(S.play_one(name, seed=i)) for i in range(runs)]
            _reference[name] = {k: _mean([f[k] for f in fs]) for k, _, _ in FEATURES}
    return _reference


def distance(a, b):
    return math.sqrt(sum(((a[k] - b[k]) / scale) ** 2 for k, _, scale in FEATURES))


def classify(g):
    """-> (closest strategy, {strategy: distance}, player features)"""
    f = features(g)
    dists = {name: distance(f, ref) for name, ref in reference().items()}
    return min(dists, key=dists.get), dists, f


def save_run(g, seed=None):
    RUNS_DIR.mkdir(exist_ok=True)
    style, dists, f = classify(g)
    path = RUNS_DIR / time.strftime("%Y%m%d-%H%M%S.json")
    path.write_text(json.dumps({
        "seed": seed, "result": g.end_reason, "style": style,
        "distances": dists, "features": f, "summary": g.snapshot(),
        "decisions": g.decisions,
    }, indent=1, ensure_ascii=False), encoding="utf-8")
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bots", action="store_true", help="show the bot reference numbers")
    args = ap.parse_args()

    ref = reference()
    if args.bots:
        print(f"{'':34}" + "".join(f"{n:>12}" for n in ref))
        for k, label, _ in FEATURES:
            print(f"{label:34}" + "".join(f"{ref[n][k]:12.2f}" for n in ref))
        return

    files = sorted(RUNS_DIR.glob("*.json")) if RUNS_DIR.exists() else []
    if not files:
        print("No logged runs yet. Play one with: python play.py")
        return
    print(f"{'run':16} {'result':12} {'style':11} {'deep':>5} {'dep.hunger':>10}"
          f" {'seita/fish':>10} {'iron':>5} {'wrath':>6} {'decisions':>9}")
    for p in files:
        r = json.loads(p.read_text(encoding="utf-8"))
        f = r["features"]
        print(f"{p.stem:16} {r['result']:12} {r['style']:11} {f['deep_share']:5.0%}"
              f" {f['deposit_hunger']:10.0%} {f['seita_per_fish']:10.2f}"
              f" {f['iron_bought']:5.0f} {f['avg_wrath']:6.0f} {len(r['decisions']):9}")


if __name__ == "__main__":
    main()
