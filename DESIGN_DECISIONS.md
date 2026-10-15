# Settled design decisions – core loop

Decisions from the design sessions on 2026-10-12 and 2026-10-15.
As of 2026-10-15 the sim implements everything below except F (log curve, later) and
G (fish farm, shelved). Rule names are those used in `config.py`.

---

## Already in the code

1. **Actions per round:** fish, deposit, story (incl. boss), Seita, shop.
2. **Time rule:** only outdoor time raises hunger: walking out, casting, story/boss chunks,
   Näkki encounters (`NAKKI_ENCOUNTER_TIME`), and the walk back to the cabin to deposit
   (`WALK_TIME`, plus `DEEP_EXTRA_WALK` from deep water). Once in the cabin, deposit, Seita
   and shop cost no time. Deciding what to do costs no time either.
   The cabin is not a hiding place, because nothing progresses there.
3. **Wrath is decoupled from hunger.** Wrath's ONLY effect is Näkki's chance to bite on a
   cast or story chunk. The chance scales linearly with wrath
   (`NAKKI_CHANCE_AT_ZERO_WRATH` → `NAKKI_CHANCE_AT_MAX_WRATH`), ×`DEEP_NAKKI_FACTOR` in
   deep water and ×`STORY_NAKKI_FACTOR` per story chunk. It does not speed up hunger.
4. **Wrath rises per fish deposited** (`WRATH_PER_FISH_DEPOSITED`). The pike boss does NOT
   raise wrath more than normal fishing: the Fat Pike counts as one fish. Its danger is
   duration (many outdoor turns while hunger climbs).
5. **Deposit gamble:** above `BONUS_HUNGER_THRESHOLD`, a deposit has a *chance* of bonus
   tokens (×`BONUS_MULTIPLIER`), and the chance grows with hunger. The cost is that hunger
   stays close to the edge after deposit.
6. **Seita:** sacrifice a fish (`SEITA_WRATH_PER_FISH`) or the Fat Pike after the boss
   (`SEITA_WRATH_FAT_PIKE`) to lower wrath. It costs fish, not time.
7. **Iron banishes Näkki** when it surfaces.
8. **Simulated player** (for `simulate.py`) has a **confusion** variable: higher early, lower
   late, and rising with wrath (fear makes choices messier).

---

## Implemented in the sim 2026-10-15 (A–D)

### A. Village collapse at hunger 100
Hitting 100 is **not** game over. The village has collapsed, which means Näkki has already
won by protecting the lake. From then on:
- Depositing fish feeds only the player: **no tokens**, and hunger no longer drops.
- **Wrath freezes** at its current value. It stops rising and does NOT reset or drop
  (no wrath from deposits, Seita unavailable). Chosen for dread: Näkki stays as dangerous
  as the player made her.
- The run continues; the player finishes the story on whatever iron/tokens they banked.
- The ending is locked to **bad**.
- Collapse is permanent.

Engine: `Game.collapsed` flag, set in `_pass_outdoor`, checked in `_deposit` and
`available_actions`. Collapse is the only behaviour, so there is no config switch for it.

### B. Näkki surfaces and the player has no iron
- Has iron → spend 1 iron, banished.
- No iron, but tokens ≥ `BOARDING_COST` → pay the fixed cost, flee to the cabin and board
  the windows, survive the breach.
- No iron and not enough tokens → **game over** (Näkki takes you).
- So tokens are both shop currency and an emergency life. After collapse no new tokens
  come in, so this safety net shrinks.

Config: `BOARDING_COST = 30` (see E). The old `NO_IRON_RESULT` and `NO_IRON_HUNGER_SPIKE`
are removed.

### C. Barred windows removed from the shop
Boarding windows already happens inside the cabin (rule B). The shop item duplicated it.
`barred_windows` and `window_charges` are removed from config, engine and `play.py`.

### D. Good ending
Good ending = finish the story **AND** the village never collapsed **AND** final wrath ≤
`GOOD_ENDING_MAX_WRATH`. The theme: you fed the village *and* kept the lake calm, so you
coexisted with it. Anything else = bad ending.

Config: `GOOD_ENDING_MAX_WRATH = 30`; the old `GOOD_ENDING_AVG_HUNGER` is removed.
`play.py` marks the target on the wrath bar.

### E. Prices (rescaled 2026-10-15 to the real fish table, still to tune)
Real income is ~10–17 tokens per outdoor minute (5–15 tokens per fish).
- Iron: 15 tokens (about one trip)
- Emergency boarding (`BOARDING_COST`): 30 (stings more than iron, so pre-buying iron is smart)
- One-time gear: haul bucket 50, Murmuring Bait 60, slumberhook 50
- A run earns ~200–260 tokens -> iron plus 2–3 pieces of gear.

### F. Hunger curve: keep linear for now
The real game's curve (every 15 s: `log10(1 + 2h + 0.01) * 0.6 * (1 + wrath/50)`) actually
ACCELERATES with hunger and still multiplies by wrath, so above ~20% hunger it outruns
fishing. The sim is **linear** with no wrath link while balancing. Fishing feeds the
village at ~0.30/min (shallow) / ~0.35/min (deep), so the hunger rate must stay below that;
current value 0.20/min. Revisit a curve shape as a later polish pass.

### G. Fish farm: shelved
A shop-built fish pool that feeds the village without touching the lake. Not
implemented. It may come back if the restraint-based good ending tests well.

---

## Still open (marked `# OPEN` in `config.py`)
- Hunger rate (0.20/min now, sensible range ~0.15–0.25).
- Shop prices, item effects and `BOARDING_COST`.
- Good-ending wrath limit. At 30 (1000 runs per strategy, 2026-10-15):

  | Strategy   | Good | Bad | Caught |
  |------------|-----:|----:|-------:|
  | Appeaser   | 89%  | 1%  | 10%    |
  | Aggressive | 31%  | 47% | 22%    |
  | Cautious   | 8%   | 85% | 6%     |

  The strategies are not yet equally viable.
- After collapse: shop with banked tokens? Sim default `SHOP_OPEN_AFTER_COLLAPSE = True`;
  Seita stays closed (wrath frozen).
- Measure in the real game: pike fight time (`CATCH_TIME_OVERRIDE`), walk times, haul capacity.
