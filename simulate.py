"""
Batch mode: simulated players with a CONFUSION variable play many runs.

    python simulate.py                    # all strategies, N_RUNS each, charts
    python simulate.py --runs 300         # fewer runs
    python simulate.py --strategy cautious
    python simulate.py --no-plot          # text report only
    python simulate.py --trace aggressive # print one full run log
    python simulate.py --sweep 0.15:0.45 0.25   # compare hunger rates (per min, at 0%:at 100%)
    python simulate.py --deadline 15 18 22 none # compare deadlines (minutes)

Strategies are bundles of simple rules (see STRATEGIES). Every decision the bot
makes has a `confusion` chance of being replaced by a random available action:
high early, lower as the story progresses, higher when wrath is high (fear).
"""
import argparse
import statistics as st
from collections import Counter

import config as C
from engine import Game, hunger_rate, lerp

# ----------------------------------------------------------------------
# Strategies
# ----------------------------------------------------------------------
STRATEGIES = {
    # mostly deep (money), holds the haul, gambles at high hunger, keeps little iron
    "aggressive": dict(deep_below_hunger=0.6, deposit_hunger=0.85, iron_target=1,
                       seita_wrath=60, story_hunger=0.5,
                       errands=["murmuring_bait", "slumberhook"]),
    # mostly shallow (food), deposits early, stocks iron
    # (deep_below_hunger: fish deep for tokens below this hunger, shallow for food above it)
    "cautious":   dict(deep_below_hunger=0.2, deposit_hunger=0.35, iron_target=2,
                       seita_wrath=40, story_hunger=0.25,
                       errands=["slumberhook"]),
    # keeps wrath low with constant Seita sacrifices, aims for the good ending
    "appeaser":   dict(deep_below_hunger=0.3, deposit_hunger=0.45, iron_target=1,
                       seita_wrath=15, story_hunger=0.3,
                       errands=["slumberhook"]),
}
STRATEGIES["random"] = None   # every choice random: the baseline real play should beat


def confusion(game):
    c = lerp(C.CONFUSION_START, C.CONFUSION_END, game.story_fraction)
    return min(1.0, c + C.CONFUSION_WRATH_FACTOR * game.wrath / C.WRATH_MAX)


# Bots push the story once the time left is under this x the story still to play
# (story chunks also lose time to Näkki encounters and the odd walk).
DEADLINE_MARGIN = 1.4


def decide(game, s):
    """What the strategy *wants* to do this step."""
    acts = game.available_actions()
    if (game.time_left is not None and not game.story_done
            and game.time_left < game.story_left * DEADLINE_MARGIN + 30):
        return "story"                                   # out of time: drop everything else
    cast = "cast_deep" if game.hunger < s["deep_below_hunger"] else "cast_shallow"

    if game.collapsed:                                   # nothing to gain from fishing
        if game.iron < s["iron_target"] and "shop:iron" in acts:
            return "shop:iron"
        return "story"

    full = len(game.haul) >= game.haul_capacity
    worth_walk = len(game.haul) >= min(2, game.haul_capacity)
    if game.haul and (full or game.hunger >= 0.92
                      or (worth_walk and game.hunger >= s["deposit_hunger"])):
        return "deposit"
    if game.has_fat_pike:
        return "seita_fatpike" if game.wrath > s["seita_wrath"] else "deposit"
    if game.wrath > s["seita_wrath"] and "seita" in acts:
        return "seita"
    if game.location == "cabin":                         # shopping happens at the cabin
        if game.iron < s["iron_target"] and "shop:iron" in acts:
            return "shop:iron"
    if game.hunger < s["story_hunger"] and not game.haul:
        for item in s["errands"]:
            if f"errand:{item}" in acts:
                return f"errand:{item}"
        if not game.story_done:
            return "story"
    if cast in acts:
        return cast
    return "deposit" if "deposit" in acts else acts[0]


def play_one(strategy, seed=None):
    g = Game(seed=seed)
    s = STRATEGIES[strategy]
    while not g.ended:
        acts = g.available_actions()
        if s is None or g.rng.random() < confusion(g):
            action = g.rng.choice(acts)
        else:
            action = decide(g, s)
        g.act(action)
    return g


# ----------------------------------------------------------------------
# Reporting
# ----------------------------------------------------------------------
ENDINGS = ["good_ending", "bad_ending", "deadline", "caught", "timeout"]


def mean(xs):
    return st.mean(xs) if xs else 0.0


def summarize(name, games):
    n = len(games)
    ends = Counter(g.end_reason for g in games)
    mins = [g.time / 60 for g in games]
    trips = [t for g in games for t in g.trips if t[1] > 0]
    tpm = [g.tokens_earned / (g.outdoor_time / 60) for g in games if g.outdoor_time > 60]
    bought = Counter(item for g in games for item in g.owned)
    gam_w = sum(g.bonuses_won for g in games)
    gam_l = sum(g.bonuses_lost for g in games)

    print(f"\n=== {name.upper()}  ({n} runs) " + "=" * 40)
    print("Endings:      " + "   ".join(f"{e} {ends[e] / n:5.1%}" for e in ENDINGS))
    print(f"Collapsed:    {sum(g.collapsed for g in games) / n:5.1%} of runs"
          f"   (avg at {mean([g.collapse_time / 60 for g in games if g.collapsed]):.1f} min)")
    print(f"Run length:   {mean(mins):.1f} min avg   (median {st.median(mins):.1f})")
    print(f"Trip:         {mean([t[0] for t in trips]):.0f} s avg, "
          f"{mean([t[1] for t in trips]):.1f} fish  -> {mean([t[0] / t[1] for t in trips]):.0f} s per fish")
    print(f"Income:       {mean(tpm):.1f} tokens per outdoor minute,"
          f" {mean([g.tokens_earned for g in games]):.0f} per run")
    print(f"Näkki:        {mean([g.nakki_encounters for g in games]):.1f} encounters/run,"
          f" iron used {mean([g.iron_used for g in games]):.1f}"
          f" (bought {mean([g.bought.get('iron', 0) for g in games]):.1f}),"
          f" boardings {mean([g.boardings for g in games]):.2f}")
    print(f"Tokens left:  {mean([g.tokens for g in games]):.0f} avg at the end (unspent)")
    print(f"Seita:        {mean([g.fish_sacrificed - g.fatpike_sacrificed for g in games]):.1f}"
          f" fish sacrificed/run, last one worth {mean([g.seita_relief for g in games]):.1f} wrath")
    print(f"Wrath at end: {mean([g.wrath for g in games]):.0f} avg")
    print(f"Gambles:      {gam_w + gam_l} taken, {gam_w / max(1, gam_w + gam_l):.0%} won")
    print("Gear owned:   " + ", ".join(f"{k} {v / n:.0%}" for k, v in bought.most_common()))
    return ends


def economy():
    """The math without randomness: what one minute of fishing is worth."""
    lo, hi = hunger_rate(0) * 60, hunger_rate(1) * 60
    print(f"\n=== ECONOMY (expected values, no gear, haul {C.HAUL_CAPACITY}) ===")
    print(f"Hunger rises {lo:.2f}/min at 0% -> {hunger_rate(0.5) * 60:.2f} at 50% -> {hi:.2f} at 100%"
          f" (per outdoor minute)")
    story = sum(s for _, s in C.STORY_STAGES)
    print(f"Story needs {story / 60:.1f} outdoor min -> {story / 60 * lo:.2f}-{story / 60 * hi:.2f}"
          f" hunger to make up\n")
    print(f"{'pool':8} {'s/fish':>7} {'tok/min':>8} {'relief/min':>11} {'keeps up below':>15}  pike")
    for pool, weights in C.FISH_POOLS.items():
        W = sum(weights.values())
        p = {f: w / W for f, w in weights.items()}
        base = {f: C.CATCH_TIME_OVERRIDE.get(
            f, C.CATCH_TIME_BASE + C.CATCH_TIME_PER_DIFFICULTY * C.FISH[f][2]) for f in p}
        walk = 2 * C.WALK_TIME
        secs = sum(p[f] * base[f] for f in p) + walk / C.HAUL_CAPACITY
        tok = sum(p[f] * C.FISH[f][0] for f in p)
        food = sum(p[f] * C.FISH[f][1] for f in p)
        relief = food / secs * 60
        h = 1.0 if hi <= lo else max(0.0, min(1.0, (relief - lo) / (hi - lo)))
        print(f"{pool:8} {secs:7.1f} {tok / secs * 60:8.1f} {relief:11.2f} {h:14.0%}  "
              f" {p.get('pike', 0):.0%}")
    print("'keeps up below': the hunger level under which fishing there out-feeds hunger.")


def plot(results):
    import matplotlib.pyplot as plt

    names = list(results)
    colors = {"good_ending": "#2e7d32", "bad_ending": "#9e9e9e",
              "deadline": "#5c6bc0", "caught": "#c62828", "timeout": "#f9a825"}
    fig, axes = plt.subplots(1, 3, figsize=(16, 5))

    # 1. Ending distribution per strategy
    ax = axes[0]
    bottom = [0.0] * len(names)
    for e in ENDINGS:
        vals = [Counter(g.end_reason for g in results[n])[e] / len(results[n]) for n in names]
        ax.bar(names, vals, bottom=bottom, label=e.replace("_", " "), color=colors[e])
        bottom = [b + v for b, v in zip(bottom, vals)]
    ax.set_title("How runs end")
    ax.set_ylabel("share of runs")
    ax.legend(loc="upper right", fontsize=8)

    # 2 & 3. Hunger and wrath over time, first 20 runs of each strategy
    for ax, idx, title, ylim in ((axes[1], 1, "Hunger over time", 1.05),
                                 (axes[2], 2, "Wrath over time", 105)):
        for i, n in enumerate(names):
            for g in results[n][:20]:
                t = [h[0] / 60 for h in g.history]
                v = [h[idx] for h in g.history]
                ax.plot(t, v, color=f"C{i}", alpha=0.25, lw=1,
                        label=n if g is results[n][0] else None)
        ax.set_title(title + " (20 runs each)")
        ax.set_xlabel("minutes")
        ax.set_ylim(0, ylim)
        ax.legend(fontsize=8)
    axes[2].axhline(C.GOOD_ENDING_MAX_WRATH, ls="--", color="k", lw=1)

    fig.tight_layout()
    fig.savefig("sim_results.png", dpi=110)
    print("\nChart saved to sim_results.png")
    plt.show()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=C.N_RUNS)
    ap.add_argument("--strategy", choices=list(STRATEGIES))
    ap.add_argument("--no-plot", action="store_true")
    ap.add_argument("--trace", choices=list(STRATEGIES), help="print one full run")
    ap.add_argument("--sweep", nargs="+", metavar="LOW:HIGH",
                    help="compare hunger rates per min at 0%%:100%%, e.g. --sweep 0.25 0.15:0.45")
    ap.add_argument("--deadline", nargs="+", metavar="MIN",
                    help="compare deadlines in minutes ('none' = no deadline), e.g. --deadline 15 18 none")
    args = ap.parse_args()

    if args.deadline:
        names = [args.strategy] if args.strategy else list(STRATEGIES)
        print(f"{'deadline':>8} {'strategy':>11} {'good':>6} {'bad':>6} {'late':>6} {'caught':>7}"
              f" {'collapse':>9} {'minutes':>8} {'tok left':>9}")
        for d in args.deadline:
            C.DEADLINE = None if d == "none" else float(d) * 60
            for n in names:
                gs = [play_one(n, seed=i) for i in range(args.runs)]
                e = Counter(g.end_reason for g in gs)
                print(f"{d:>8} {n:>11} {e['good_ending'] / len(gs):6.0%}"
                      f" {e['bad_ending'] / len(gs):6.0%} {e['deadline'] / len(gs):6.0%}"
                      f" {e['caught'] / len(gs):7.0%}"
                      f" {sum(g.collapsed for g in gs) / len(gs):9.0%}"
                      f" {mean([g.time / 60 for g in gs]):8.1f}"
                      f" {mean([g.tokens for g in gs]):9.0f}")
        return

    if args.sweep:
        names = [args.strategy] if args.strategy else list(STRATEGIES)
        print(f"{'hunger/min':>10} {'strategy':>11} {'good':>6} {'bad':>6} {'caught':>7}"
              f" {'collapse':>9} {'minutes':>8} {'tokens':>7}")
        for rate in args.sweep:
            lo, _, hi = rate.partition(":")
            C.HUNGER_RATE_AT_ZERO = float(lo) / 60
            C.HUNGER_RATE_AT_MAX = float(hi or lo) / 60
            for n in names:
                gs = [play_one(n, seed=i) for i in range(args.runs)]
                e = Counter(g.end_reason for g in gs)
                print(f"{rate:>10} {n:>11} {e['good_ending'] / len(gs):6.0%}"
                      f" {e['bad_ending'] / len(gs):6.0%} {e['caught'] / len(gs):7.0%}"
                      f" {sum(g.collapsed for g in gs) / len(gs):9.0%}"
                      f" {mean([g.time / 60 for g in gs]):8.1f}"
                      f" {mean([g.tokens_earned for g in gs]):7.0f}")
        return

    economy()
    if args.trace:
        g = play_one(args.trace, seed=C.RANDOM_SEED)
        print("\n".join(g.log))
        return

    names = [args.strategy] if args.strategy else list(STRATEGIES)
    results = {n: [play_one(n, seed=i) for i in range(args.runs)] for n in names}
    for n in names:
        summarize(n, results[n])
    if not args.no_plot:
        plot(results)


if __name__ == "__main__":
    main()