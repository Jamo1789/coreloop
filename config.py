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

# Deadline (decision K, 2026-11-09): the story must be finished by this game time, or
# the lake freezes over with Näkki still in it -> "deadline" ending (a bad ending).
# Time only passes outdoors, so this is an outdoor-time budget: every extra fishing trip
# spent "fixing" hunger or tokens is time the story doesn't get. None = no deadline.
DEADLINE = 18 * 60                                                     # OPEN
RANDOM_SEED = None       # int for repeatable runs

# ---------------------------------------------------------------
# HUNGER - the rate grows with hunger itself (decision F, 2026-11-03):
#   rate = AT_ZERO + (AT_MAX - AT_ZERO) * hunger      (per outdoor second)
# So hunger accelerates: low hunger is cheap time, high hunger is expensive.
# Set both ends equal for the old flat rate. Fishing feeds ~0.30/min shallow,
# ~0.45/min deep, so shallow stops keeping up once the rate passes 0.30.
# Only rises while the player is OUTDOORS. Paused in the cabin.
# ---------------------------------------------------------------
HUNGER_START = 0.0
HUNGER_RATE_AT_ZERO = 0.15 / 60  # OPEN: per second at 0% hunger
HUNGER_RATE_AT_MAX = 0.45 / 60   # OPEN: per second at 100% hunger

# At hunger 1.0 the village COLLAPSES (decision A):
#   - deposits give no tokens and no longer lower hunger
#   - wrath freezes (no rise from deposits, no Seita)
#   - bad ending is locked, run continues
# OPEN: can banked tokens still be spent at the shop after collapse?
SHOP_OPEN_AFTER_COLLAPSE = True

# ---------------------------------------------------------------
# FISH  (tokenReward, hungerValue, difficulty) - REARRANGED 2026-11-03, differs from the game.
# Shallow = food fish (feed the village), deep = money fish (tokens, little food).
# In the game's table every fish gave ~0.02 hunger per token, so deep won on both.
# Game values were: perch 5/.10, pike 10/.20, roach/ide/vendace 3/.05, zander 7/.15,
# eel 12/.25, burbot 15/.30, bream 6/.12.
# ---------------------------------------------------------------
FISH = {
    #            tokens  hunger  difficulty
    "perch":    (4,      0.14,   1.0),
    "pike":     (10,     0.20,   2.0),   # in both pools: middle of the road
    "roach":    (2,      0.08,   0.5),
    "ide":      (2,      0.08,   0.5),
    "vendace":  (2,      0.08,   0.5),
    "zander":   (10,     0.11,   0.1),   # difficulty 0.1 looks like a typo in the game
    "eel":      (16,     0.14,   1.8),
    "burbot":   (20,     0.17,   2.2),
    "bream":    (4,      0.16,   0.8),
    "fatPike":  (50,     0.50,   2.0),   # boss reward, not in the pools
}

FISH_POOLS = {   # shallow ~12 tok & 0.39 hunger per min, deep ~32 tok & 0.37 hunger per min
    "shallow": {"perch": 0.5, "pike": 0.2, "roach": 0.2, "ide": 0.2,
                "vendace": 0.2, "bream": 0.4},
    "deep":    {"zander": 0.5, "eel": 0.4, "burbot": 0.3, "pike": 0.3, "perch": 0.2},
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
DEEP_NAKKI_FACTOR = 2.5          # deep water is the risky money spot (was 1.5) # PLACEHOLDER
STORY_NAKKI_FACTOR = 0.5         # per story chunk, vs per cast         # PLACEHOLDER
NAKKI_ENCOUNTER_TIME = 10        # seconds lost to an encounter

IRON_START = 1
# No iron (decision B): pay BOARDING_COST tokens, flee to the cabin, survive.
# Not enough tokens -> game over.
# Each boarding costs more than the last (decision L): 30, 60, 90, ...
BOARDING_COST = 30                                                     # OPEN
BOARDING_COST_STEP = 30                                                # OPEN

# ---------------------------------------------------------------
# SEITA STONE  (free on time, costs fish)
# ---------------------------------------------------------------
SEITA_WRATH_PER_FISH = 8         # the first sacrifice ...
SEITA_DECAY = 0.8                # ... each later one removes this x the previous (decision L) # OPEN
SEITA_WRATH_MIN = 2              # ... but never less than this
SEITA_WRATH_FAT_PIKE = 40        # offering the boss fish (Fat Pike)

# ---------------------------------------------------------------
# SHOP  (free on time, costs tokens). Barred windows (decision C) and haul bucket (decision I) removed.
# OPEN: prices; item effects are placeholders - map them to the real accessories.
# ---------------------------------------------------------------
SHOP = {
    "iron":           {"price": 30, "effect": "+1 iron"},   # was 15 until 2026-11-03
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