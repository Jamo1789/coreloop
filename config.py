"""
Core loop simulation - all tunable numbers live here.

Time is in SECONDS. Hunger is 0..1 (like GameState.villageHunger), wrath 0..100.
Fish values are copied from the real game's GameState (not balanced yet).

Lines marked  # PLACEHOLDER  are guesses - measure them in the real game.
Lines marked  # OPEN  are unsettled design questions.
"""

# ---------------------------------------------------------------
# GENERAL
# ---------------------------------------------------------------
MAX_TIME = 60 * 60       # safety cap: one hour of game time
RANDOM_SEED = None       # int for repeatable runs

# ---------------------------------------------------------------
# HUNGER - linear while balancing (real game uses an accelerating log curve)
# Only rises while the player is OUTDOORS. Paused in the cabin.
# ---------------------------------------------------------------
HUNGER_START = 0.0
HUNGER_PER_SECOND = 0.20 / 60    # OPEN: 0.20/min -> 0% to 100% in 5 min outdoors (break-even ~0.30)

# At hunger 1.0 the village COLLAPSES (decision A):
#   - deposits give no tokens and no longer lower hunger
#   - wrath freezes (no rise from deposits, no Seita)
#   - bad ending is locked, run continues
# OPEN: can banked tokens still be spent at the shop after collapse?
SHOP_OPEN_AFTER_COLLAPSE = True

# ---------------------------------------------------------------
# FISH  (from the game: tokenReward, hungerValue, difficulty)
# ---------------------------------------------------------------
FISH = {
    #            tokens  hunger  difficulty
    "perch":    (5,      0.10,   1.0),
    "pike":     (10,     0.20,   2.0),
    "roach":    (3,      0.05,   0.5),
    "ide":      (3,      0.05,   0.5),
    "vendace":  (3,      0.05,   0.5),
    "zander":   (7,      0.15,   0.1),   # difficulty 0.1 looks like a typo in the game
    "eel":      (12,     0.25,   1.8),
    "burbot":   (15,     0.30,   2.2),
    "bream":    (6,      0.12,   0.8),
    "fatPike":  (50,     0.50,   2.0),   # boss reward, not in the pools
}

FISH_POOLS = {
    "shallow": {"perch": 0.5, "pike": 0.4, "roach": 0.1, "ide": 0.1,
                "vendace": 0.1, "bream": 0.3},
    "deep":    {"zander": 0.5, "eel": 0.4, "roach": 0.1, "ide": 0.1,
                "vendace": 0.1, "pike": 0.4, "perch": 0.5, "burbot": 0.3},
}

# ---------------------------------------------------------------
# TIME COSTS  (calibrated against 5 measured runs: ~59 s for ~2.8 fish)
# ---------------------------------------------------------------
WALK_TIME = 6.5                  # cabin <-> shore, each way (measured 6-7 s, 2026-10-31). Shallow and deep share the shore.
CATCH_TIME_BASE = 8              # seconds per catch ...
CATCH_TIME_PER_DIFFICULTY = 6    # ... plus this x fish difficulty
CATCH_TIME_OVERRIDE = {"pike": 40}   # pike fight w/o accessories        # OPEN, measure
CATCH_TIME_NOISE = 0.25          # +-25 % random variation per catch

HAUL_CAPACITY = 3                # fish carried before you must deposit # PLACEHOLDER

# ---------------------------------------------------------------
# DEPOSIT GAMBLE
# ---------------------------------------------------------------
BONUS_HUNGER_THRESHOLD = 0.70
BONUS_CHANCE_AT_THRESHOLD = 0.25
BONUS_CHANCE_AT_MAX = 0.75
BONUS_MULTIPLIER = 2.0

# ---------------------------------------------------------------
# WRATH  (only effect: Näkki's chance to surface)
# ---------------------------------------------------------------
WRATH_MAX = 100
WRATH_PER_FISH_DEPOSITED = 2                                           # PLACEHOLDER

# ---------------------------------------------------------------
# NÄKKI
# ---------------------------------------------------------------
# Chance per cast that Näkki bites instead of a fish (scales with wrath).
NAKKI_CHANCE_AT_ZERO_WRATH = 0.03                                      # PLACEHOLDER
NAKKI_CHANCE_AT_MAX_WRATH = 0.25                                       # PLACEHOLDER
DEEP_NAKKI_FACTOR = 1.5          # deep water is more dangerous         # PLACEHOLDER
STORY_NAKKI_FACTOR = 0.5         # per story chunk, vs per cast         # PLACEHOLDER
NAKKI_ENCOUNTER_TIME = 10        # seconds lost to an encounter

IRON_START = 1
# No iron (decision B): pay BOARDING_COST tokens, flee to the cabin, survive.
# Not enough tokens -> game over.
BOARDING_COST = 30                                                     # OPEN

# ---------------------------------------------------------------
# SEITA STONE  (free on time, costs fish)
# ---------------------------------------------------------------
SEITA_WRATH_PER_FISH = 8
SEITA_WRATH_FAT_PIKE = 40        # offering the boss fish (Fat Pike)

# ---------------------------------------------------------------
# SHOP  (free on time, costs tokens). Barred windows (decision C) and haul bucket (decision I) removed.
# OPEN: prices; item effects are placeholders - map them to the real accessories.
# ---------------------------------------------------------------
SHOP = {
    "iron":           {"price": 15, "effect": "+1 iron"},
}

# ---------------------------------------------------------------
# STORY ITEMS  (not sold - found on an optional outdoor errand, costs time)
# "unlock" = story stage index from which the errand is available.
# OPEN: errand lengths and unlock points.
# ---------------------------------------------------------------
STORY_ITEMS = {
    "murmuring_bait": {"time": 45, "unlock": 0, "effect": "catches 25% faster"},          # PLACEHOLDER
    "slumberhook":    {"time": 45, "unlock": 1, "effect": "pike & boss fights 50% faster"}, # PLACEHOLDER
}
MURMURING_BAIT_FACTOR = 0.75
SLUMBERHOOK_FACTOR = 0.5

# ---------------------------------------------------------------
# STORY  (seconds of outdoor time per stage, done in chunks)
# ---------------------------------------------------------------
STORY_CHUNK = 15
STORY_STAGES = [
    ("Log 1: bed of reeds",        60),                                # PLACEHOLDER
    ("Log 2: fat pike boss",       150),                               # PLACEHOLDER
    ("Log 3: pull Näkki & breach", 90),                                # PLACEHOLDER
    ("Final: tunnel & banishing",  120),                               # PLACEHOLDER
]
BOSS_STAGE_INDEX = 1

# ---------------------------------------------------------------
# ENDINGS (decision D)
# Good = story done AND village never collapsed AND final wrath <= this.
# ---------------------------------------------------------------
GOOD_ENDING_MAX_WRATH = 30       # OPEN: at 30 only the Seita appeaser wins reliably

# ---------------------------------------------------------------
# SIMULATED PLAYER (simulate.py)
# ---------------------------------------------------------------
CONFUSION_START = 0.30           # chance of a random choice early on
CONFUSION_END = 0.08             # ... once the story is nearly done
CONFUSION_WRATH_FACTOR = 0.15    # extra confusion at max wrath (fear)
N_RUNS = 1000