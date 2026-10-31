"""
Game engine: state + rules. No UI, no player logic.

    game = Game()
    game.available_actions()   -> list of action strings
    game.act("cast_shallow")   -> messages produced
    game.ended / game.end_reason / game.snapshot()

Time is in seconds. Only OUTDOOR time raises hunger:
walking, casting, story, errands, Näkki encounters. Deposit (after walking back),
Seita and shop take no time.

Actions:
    cast_shallow / cast_deep   one catch attempt (walks there first if needed)
    deposit                    walk back to the cabin, deposit the whole haul
    story                      one chunk of the current story stage
    errand:<item>              fetch a story item (murmuring bait, slumberhook)
    seita                      sacrifice the cheapest fish in the haul
    seita_fatpike              offer the fat pike from the boss
    shop:<item>                buy an item
"""
import random

import config as C


def lerp(a, b, t):
    t = max(0.0, min(1.0, t))
    return a + (b - a) * t


class Game:
    def __init__(self, seed=C.RANDOM_SEED):
        self.rng = random.Random(seed)

        self.time = 0.0                 # total game seconds
        self.outdoor_time = 0.0
        self.location = "cabin"         # cabin | shore
        self.hunger = float(C.HUNGER_START)
        self.wrath = 0.0

        self.tokens = 0
        self.iron = C.IRON_START
        self.haul = []                  # fish names carried
        self.haul_capacity = C.HAUL_CAPACITY
        self.owned = set()

        self.stage = 0
        self.stage_progress = 0.0       # seconds into current stage
        self.has_fat_pike = False       # boss reward, kept out of the haul

        self.collapsed = False
        self.ended = False
        self.end_reason = ""

        # stats
        self.tokens_earned = 0
        self.fish_caught = 0
        self.fish_deposited = 0
        self.fish_sacrificed = 0
        self.nakki_encounters = 0
        self.iron_used = 0
        self.boardings = 0
        self.bonuses_won = 0
        self.bonuses_lost = 0
        self.collapse_time = None
        self.trips = []                 # (seconds, fish) per completed trip
        self._trip_start = None
        self._trip_fish = 0
        self.history = []               # (time, hunger, wrath, tokens)

        self.log = []
        self._record()

    # ------------------------------------------------------------------
    # Derived values
    # ------------------------------------------------------------------
    def nakki_chance(self, pool="shallow"):
        p = lerp(C.NAKKI_CHANCE_AT_ZERO_WRATH, C.NAKKI_CHANCE_AT_MAX_WRATH,
                 self.wrath / C.WRATH_MAX)
        return p * (C.DEEP_NAKKI_FACTOR if pool == "deep" else 1.0)

    @property
    def bonus_chance(self):
        if self.collapsed or self.hunger < C.BONUS_HUNGER_THRESHOLD:
            return 0.0
        span = 1.0 - C.BONUS_HUNGER_THRESHOLD
        t = 1.0 if span <= 0 else (self.hunger - C.BONUS_HUNGER_THRESHOLD) / span
        return lerp(C.BONUS_CHANCE_AT_THRESHOLD, C.BONUS_CHANCE_AT_MAX, t)

    @property
    def story_done(self):
        return self.stage >= len(C.STORY_STAGES)

    @property
    def stage_name(self):
        return "Complete" if self.story_done else C.STORY_STAGES[self.stage][0]

    def stage_length(self, i=None):
        i = self.stage if i is None else i
        secs = C.STORY_STAGES[i][1]
        if i == C.BOSS_STAGE_INDEX and "slumberhook" in self.owned:
            secs *= C.SLUMBERHOOK_FACTOR
        return secs

    @property
    def story_fraction(self):
        total = sum(self.stage_length(i) for i in range(len(C.STORY_STAGES)))
        done = sum(self.stage_length(i) for i in range(min(self.stage, len(C.STORY_STAGES))))
        return (done + (0 if self.story_done else self.stage_progress)) / total

    def catch_time(self, fish):
        t = C.CATCH_TIME_OVERRIDE.get(
            fish, C.CATCH_TIME_BASE + C.CATCH_TIME_PER_DIFFICULTY * C.FISH[fish][2])
        if "murmuring_bait" in self.owned:
            t *= C.MURMURING_BAIT_FACTOR
        if fish == "pike" and "slumberhook" in self.owned:
            t *= C.SLUMBERHOOK_FACTOR
        return t * self.rng.uniform(1 - C.CATCH_TIME_NOISE, 1 + C.CATCH_TIME_NOISE)

    def shop_open(self):
        return not self.collapsed or C.SHOP_OPEN_AFTER_COLLAPSE

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def available_actions(self):
        if self.ended:
            return []
        acts = []
        if len(self.haul) < self.haul_capacity:
            acts += ["cast_shallow", "cast_deep"]
        if self.haul or self.has_fat_pike:
            acts.append("deposit")
        if not self.story_done:
            acts.append("story")
        for item, info in C.STORY_ITEMS.items():
            if item not in self.owned and self.stage >= info["unlock"]:
                acts.append(f"errand:{item}")
        if not self.collapsed and self.wrath > 0:
            if self.haul:
                acts.append("seita")
            if self.has_fat_pike:
                acts.append("seita_fatpike")
        if self.shop_open():
            for item, info in C.SHOP.items():
                if self.tokens >= info["price"] and not (info.get("once") and item in self.owned):
                    acts.append(f"shop:{item}")
        return acts

    def act(self, action):
        start = len(self.log)
        if action not in self.available_actions():
            self._say(f"Can't do '{action}' right now.")
            return self.log[start:]
        if action in ("cast_shallow", "cast_deep"):
            self._cast(action.split("_")[1])
        elif action == "deposit":
            self._deposit()
        elif action == "story":
            self._story()
        elif action.startswith("errand:"):
            self._errand(action.split(":", 1)[1])
        elif action == "seita":
            self._seita()
        elif action == "seita_fatpike":
            self._seita_fatpike()
        elif action.startswith("shop:"):
            self._buy(action.split(":", 1)[1])
        self._record()
        return self.log[start:]

    # --- outdoor ------------------------------------------------------
    def _go_to_shore(self):
        """Walk to the shore. Shallow and deep casts and the story all start there."""
        if self.location == "shore":
            return
        if self._trip_start is None:
            self._trip_start = self.time
            self._trip_fish = 0
        self.location = "shore"
        self._pass_outdoor(C.WALK_TIME)

    def _cast(self, pool):
        self._go_to_shore()
        if self.ended:
            return
        if self.rng.random() < self.nakki_chance(pool):
            self._nakki()
            return
        fish = self._pick_fish(pool)
        self._pass_outdoor(self.catch_time(fish))
        if self.ended:
            return
        self.haul.append(fish)
        self.fish_caught += 1
        self._trip_fish += 1
        self._say(f"Caught {fish} ({pool}). Haul {len(self.haul)}/{self.haul_capacity}.")

    def _story(self):
        self._go_to_shore()
        if self.ended:
            return
        if self.rng.random() < self.nakki_chance() * C.STORY_NAKKI_FACTOR:
            self._nakki()
            return
        chunk = min(C.STORY_CHUNK, self.stage_length() - self.stage_progress)
        self._pass_outdoor(chunk)
        if self.ended:
            return
        self.stage_progress += chunk
        name = self.stage_name
        if self.stage_progress < self.stage_length() - 1e-9:
            self._say(f"{name}: {self.stage_progress:.0f}/{self.stage_length():.0f}s")
            return
        self._say(f"{name}: COMPLETE.")
        if self.stage == C.BOSS_STAGE_INDEX:
            self.has_fat_pike = True
            self._say("You landed the Legendary Fat Pike. Deposit it, or offer it at the Seita.")
        self.stage += 1
        self.stage_progress = 0.0
        if self.story_done:
            self._finish()

    def _errand(self, item):
        """Optional story errand: costs outdoor time instead of tokens."""
        self._go_to_shore()
        if self.ended:
            return
        if self.rng.random() < self.nakki_chance() * C.STORY_NAKKI_FACTOR:
            self._nakki()
            return
        self._pass_outdoor(C.STORY_ITEMS[item]["time"])
        if self.ended:
            return
        self.owned.add(item)
        self._say(f"Errand done: you found the {item.replace('_', ' ')}.")

    def _nakki(self):
        self.nakki_encounters += 1
        self._say("!!! NÄKKI SURFACES")
        self._pass_outdoor(C.NAKKI_ENCOUNTER_TIME)
        if self.ended:
            return
        if self.iron > 0:
            self.iron -= 1
            self.iron_used += 1
            self._say(f"You throw iron. It sinks back. Iron left: {self.iron}.")
        elif self.tokens >= C.BOARDING_COST:
            self.tokens -= C.BOARDING_COST
            self.boardings += 1
            self.location = "cabin"
            self._end_trip()
            self._say(f"No iron! You flee and board the windows (-{C.BOARDING_COST} tokens). "
                      f"You survive the breach.")
        else:
            self._end("caught", "No iron, no tokens. Näkki drags you under.")

    # --- free on time -------------------------------------------------
    def _deposit(self):
        if self.location != "cabin":
            self._pass_outdoor(C.WALK_TIME)
            if self.ended:
                return
            self.location = "cabin"
            self._end_trip()

        fish = self.haul + (["fatPike"] if self.has_fat_pike else [])
        self.haul = []
        self.has_fat_pike = False
        if self.collapsed:
            self._say(f"You eat {len(fish)} fish alone. The village is gone.")
            return

        tokens = sum(C.FISH[f][0] for f in fish)
        relief = sum(C.FISH[f][1] for f in fish)
        chance = self.bonus_chance
        if chance > 0:
            if self.rng.random() < chance:
                tokens = round(tokens * C.BONUS_MULTIPLIER)
                self.bonuses_won += 1
                self._say(f"Desperate village pays double! ({chance:.0%} gamble won)")
            else:
                self.bonuses_lost += 1
                self._say(f"No bonus. ({chance:.0%} gamble lost)")
        self.tokens += tokens
        self.tokens_earned += tokens
        self.hunger = max(0.0, self.hunger - relief)
        self.wrath = min(C.WRATH_MAX, self.wrath + len(fish) * C.WRATH_PER_FISH_DEPOSITED)
        self.fish_deposited += len(fish)
        self._say(f"Deposited {len(fish)} fish: +{tokens} tokens. "
                  f"Hunger {self.hunger:.0%}, wrath {self.wrath:.0f}.")

    def _seita(self):
        cheapest = min(self.haul, key=lambda f: C.FISH[f][0])
        self.haul.remove(cheapest)
        self.fish_sacrificed += 1
        self.wrath = max(0.0, self.wrath - C.SEITA_WRATH_PER_FISH)
        self._say(f"Sacrificed a {cheapest} at the Seita. Wrath {self.wrath:.0f}.")

    def _seita_fatpike(self):
        self.has_fat_pike = False
        self.fish_sacrificed += 1
        self.wrath = max(0.0, self.wrath - C.SEITA_WRATH_FAT_PIKE)
        self._say(f"Offered the fat pike at the Seita. Wrath {self.wrath:.0f}.")

    def _buy(self, item):
        self.tokens -= C.SHOP[item]["price"]
        if C.SHOP[item].get("once"):
            self.owned.add(item)
        if item == "iron":
            self.iron += 1
        elif item == "haul_bucket":
            self.haul_capacity += C.HAUL_BUCKET_BONUS
        self._say(f"Bought {item}. Tokens left: {self.tokens}.")

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _pass_outdoor(self, seconds):
        self.time += seconds
        self.outdoor_time += seconds
        if not self.collapsed:
            self.hunger = min(1.0, self.hunger + seconds * C.HUNGER_PER_SECOND)
            if self.hunger >= 1.0:
                self.collapsed = True
                self.collapse_time = self.time
                self._say("The village has collapsed. Näkki has won. Your fate is sealed.")
        if self.time >= C.MAX_TIME:
            self._end("timeout", "Time ran out. The story was never finished.")

    def _end_trip(self):
        if self._trip_start is not None:
            self.trips.append((self.time - self._trip_start, self._trip_fish))
        self._trip_start = None

    def _finish(self):
        if not self.collapsed and self.wrath <= C.GOOD_ENDING_MAX_WRATH:
            self._end("good_ending", "Näkki is banished. The village lives and the lake is calm.")
        elif self.collapsed:
            self._end("bad_ending", "Näkki is banished... but the village is gone.")
        else:
            self._end("bad_ending", "Näkki is banished... but the lake still seethes. You become the next one.")

    def _end(self, reason, message):
        self.ended = True
        self.end_reason = reason
        self._say(f"=== END: {message} ===")

    def _record(self):
        self.history.append((self.time, self.hunger, self.wrath, self.tokens))

    def _say(self, msg):
        m, s = divmod(int(self.time), 60)
        self.log.append(f"[{m:02d}:{s:02d}] {msg}")

    def _pick_fish(self, pool):
        weights = C.FISH_POOLS[pool]
        return self.rng.choices(list(weights), weights=list(weights.values()))[0]

    def snapshot(self):
        return {
            "time": self.time, "outdoor_time": self.outdoor_time,
            "location": self.location,
            "hunger": self.hunger, "wrath": self.wrath,
            "nakki_shallow": self.nakki_chance("shallow"),
            "nakki_deep": self.nakki_chance("deep"),
            "bonus_chance": self.bonus_chance,
            "tokens": self.tokens, "tokens_earned": self.tokens_earned,
            "iron": self.iron, "haul": list(self.haul),
            "haul_capacity": self.haul_capacity, "has_fat_pike": self.has_fat_pike,
            "stage": self.stage, "stage_name": self.stage_name,
            "stage_progress": self.stage_progress,
            "owned": sorted(self.owned), "collapsed": self.collapsed,
            "collapse_time": self.collapse_time,
            "fish_caught": self.fish_caught, "fish_deposited": self.fish_deposited,
            "fish_sacrificed": self.fish_sacrificed,
            "nakki_encounters": self.nakki_encounters, "iron_used": self.iron_used,
            "boardings": self.boardings,
            "bonuses_won": self.bonuses_won, "bonuses_lost": self.bonuses_lost,
            "ended": self.ended, "end_reason": self.end_reason,
        }