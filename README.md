# Core loop simulation – Näkki fishing horror game

A small Python sandbox for balancing the core loop of a 2D top-down Finnish-folklore
horror fishing game (working titles: LURE / Mara's Wake). The real game is not in this
folder; this is an abstract model used to tune numbers before changing the game itself.

## The loop being modelled
- Player fishes to feed a starving village. Depositing fish gives tokens.
- **Hunger** (village threat) only rises during outdoor time. Depositing fish lowers it.
- **Wrath** (personal threat) rises per fish deposited. Its ONLY effect is Näkki's chance
  to bite on a cast (lower chance per story chunk, higher in deep water). Wrath and hunger
  are deliberately decoupled.
- **Näkki** surfacing is banished with iron.
- **Deposit gamble:** above a hunger threshold, a deposit has a chance (rising with hunger)
  to pay bonus tokens. The cost is that hunger stays high, near starvation.
- **Seita stone:** sacrifice fish (or the Fat Pike from the boss) to lower wrath.
- **Shop:** spend tokens on iron and the haul bucket (barred windows removed).
- **Story items:** Murmuring Bait and the slumberhook are not sold. They are fetched on
  optional outdoor errands that cost time (and so hunger and Näkki risk) instead of tokens.
- **Story:** 4 outdoor stages (logs 1–3, final), measured in seconds. Stage 2 is a long
  fat-pike boss fight.
- **Time rule:** outdoor seconds raise hunger: walking out, casting, story chunks, errands, Näkki
  encounters, and the walk back to the cabin to deposit. Shallow and deep are cast from
  the same shore, so switching costs no time. Once in the cabin, deposit, Seita and shop
  take no time.
- Hunger 100% = village collapse (no tokens, wrath frozen, bad ending locked).
- No iron vs Näkki: pay `BOARDING_COST` tokens to survive, else game over.
- Good ending: story done, never collapsed, final wrath <= `GOOD_ENDING_MAX_WRATH`.

## Files
- `config.py` – every tunable number. `# PLACEHOLDER` = guessed value to measure in the
  real game, `# OPEN` = unsettled design question.
- `engine.py` – `Game` class: state and rules. No UI. API: `available_actions()`, `act()`, `snapshot()`.
- `play.py` – interactive terminal UI (`rich`): you pick actions, bars update live.
  Run `python play.py [seed]`.
- `simulate.py` – batch mode. Strategy bots (aggressive / cautious / appeaser) with a
  **confusion** variable play N runs. Prints an economy break-even table, per-strategy
  stats and saves `sim_results.png`. Flags: `--runs`, `--strategy`, `--no-plot`,
  `--trace <strategy>`, `--sweep <hunger per min ...>`.
- `DESIGN_DECISIONS.md` – settled design decisions and what is still open.
- `requirements.txt` – Python packages.

Time is in seconds, hunger 0..1 (linear), wrath 0..100. Fish table copied from the real
game's GameState. Real game currently uses an accelerating log hunger curve every 15 s
and still multiplies hunger by wrath; the sim uses linear and no wrath link on purpose.

## Goals
- Find numbers where the loop is tense but not a death spiral.
- Support several viable strategies: aggressive fisher, cautious/defensive, Seita appeaser.

## Open design questions
Marked `# OPEN` in `config.py`: hunger rate, shop prices and item effects,
`BOARDING_COST`, good-ending wrath limit, pike fight time, and whether the shop stays open
after a collapse. Details in `DESIGN_DECISIONS.md`.

## Setup
```
python -m venv coreloop
coreloop\Scripts\activate        # Windows
pip install -r requirements.txt
python play.py
python simulate.py
```
The venv folder `coreloop/` is git-ignored. Developed in VS Code.
