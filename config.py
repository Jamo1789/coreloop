"""
Core loop simulation - all tunable numbers live here.

Lines marked  # OPEN:  are design questions we haven't settled yet.
They have placeholder values so the sim runs; change them freely.
"""

# ---------------------------------------------------------------
# GENERAL
# ---------------------------------------------------------------
MAX_TURNS = 120          # safety cap so a run can't go on forever
RANDOM_SEED = None       # set to an int (e.g. 42) for repeatable runs

# ---------------------------------------------------------------
# HUNGER  (village threat - only ticks during outdoor actions)
# ---------------------------------------------------------------
HUNGER_START = 30
HUNGER_MAX = 100
HUNGER_PER_OUTDOOR_TURN = 4      # added each turn spent fishing / story / boss
HUNGER_RELIEF_PER_FISH = 6       # removed per fish deposited

# OPEN: what happens when hunger hits HUNGER_MAX?
#   "game_over"   -> run ends immediately
#   "bad_ending"  -> run continues, but the ending is locked to bad
HUNGER_MAX_RESULT = "bad_ending"

# Good ending requires keeping the village fed "well enough" overall.
# OPEN: placeholder rule = average hunger over the run stays below this.
GOOD_ENDING_AVG_HUNGER = 60

# ---------------------------------------------------------------
# DEPOSIT & TOKENS  (the gamble)
# ---------------------------------------------------------------
TOKENS_PER_FISH = 1

# Above this hunger level, a deposit has a CHANCE at bonus tokens.
BONUS_HUNGER_THRESHOLD = 70
# Chance of the bonus at the threshold, and at max hunger (scales linearly between).
BONUS_CHANCE_AT_THRESHOLD = 0.25
BONUS_CHANCE_AT_MAX = 0.75
BONUS_MULTIPLIER = 2.0           # tokens x this when the gamble pays off

# ---------------------------------------------------------------
# WRATH  (personal threat - ONLY drives Näkki emergence now)
# ---------------------------------------------------------------
WRATH_START = 0
WRATH_MAX = 100
WRATH_PER_FISH_DEPOSITED = 3     # taking from Näkki's realm angers it

# ---------------------------------------------------------------
# NÄKKI
# ---------------------------------------------------------------
# Chance per outdoor turn that Näkki surfaces, scaled linearly by wrath.
NAKKI_CHANCE_AT_ZERO_WRATH = 0.03
NAKKI_CHANCE_AT_MAX_WRATH = 0.40
NAKKI_CAN_EMERGE_DURING_STORY = True   # story/boss turns are outdoors too

IRON_START = 1
IRON_PER_BANISH = 1

# OPEN: what happens if Näkki surfaces and you have no iron?
#   "game_over"  -> caught, run ends
#   "lose_haul"  -> lose all carried fish + hunger spike
NO_IRON_RESULT = "game_over"
NO_IRON_HUNGER_SPIKE = 15        # only used with "lose_haul"

# ---------------------------------------------------------------
# SEITA STONE  (free on time, costs fish)
# ---------------------------------------------------------------
SEITA_WRATH_PER_FISH = 8         # wrath removed per sacrificed fish
SEITA_WRATH_PIKE_JAW = 40        # one-time big sacrifice after the pike boss

# ---------------------------------------------------------------
# FISHING
# ---------------------------------------------------------------
FISH_PER_CAST_MIN = 0
FISH_PER_CAST_MAX = 2
HAUL_CAPACITY = 4                # max fish carried before you must deposit

# ---------------------------------------------------------------
# SHOP  (free on time, costs tokens)
# OPEN: prices and effects are placeholders
# ---------------------------------------------------------------
SHOP = {
    "iron":           {"price": 3, "effect": "+1 iron"},
    "haul_bucket":    {"price": 6, "effect": "+3 haul capacity", "once": True},
    "murmuring_bait": {"price": 8, "effect": "+1 max fish per cast", "once": True},
    "slumberhook":    {"price": 5, "effect": "pike boss takes fewer turns", "once": True},
    "barred_windows": {"price": 7, "effect": "survive one no-iron Näkki encounter", "once": True},
}
HAUL_BUCKET_BONUS = 3
SLUMBERHOOK_TURN_REDUCTION = 3

# ---------------------------------------------------------------
# STORY  (each stage = outdoor turns needed to complete it)
# ---------------------------------------------------------------
STORY_STAGES = [
    ("Log 1: bed of reeds",        3),
    ("Log 2: fat pike boss",       8),   # long fight, normal wrath per turn
    ("Log 3: pull Näkki & breach", 4),
    ("Final: tunnel & banishing",  5),
]
BOSS_STAGE_INDEX = 1             # which stage the slumberhook shortens

# ---------------------------------------------------------------
# SIMULATED PLAYER  (batch mode only)
# ---------------------------------------------------------------
# Confusion 0..1: chance the bot makes a random/suboptimal choice.
CONFUSION_START = 0.40           # early game: doesn't understand the systems
CONFUSION_END = 0.10             # late game: has learned
CONFUSION_WRATH_FACTOR = 0.20    # extra confusion at max wrath (fear = messy choices)

N_RUNS = 1000