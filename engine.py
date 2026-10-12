"""
Game engine: state + rules for every action.

No UI and no player logic here. play.py (you choose) and simulate.py
(confused bot chooses) both drive this same engine through:

    game = Game()
    game.available_actions()   -> list of action strings
    game.act("fish")           -> list of messages describing what happened
    game.ended / game.end_reason

Time rule: only OUTDOOR actions (fish, story) advance the turn and tick hunger.
Deposit, Seita and shop are free on time - they only cost resources.
"""
import random

import config as C


def lerp(a, b, t):
    """Linear blend from a to b, t clamped to 0..1."""
    t = max(0.0, min(1.0, t))
    return a + (b - a) * t


class Game:
    def __init__(self, seed=C.RANDOM_SEED):
        self.rng = random.Random(seed)

        # core bars
        self.turn = 0
        self.hunger = float(C.HUNGER_START)
        self.wrath = float(C.WRATH_START)

        # resources
        self.tokens = 0
        self.iron = C.IRON_START
        self.haul = 0                              # fish carried, not yet deposited
        self.haul_capacity = C.HAUL_CAPACITY
        self.max_fish_per_cast = C.FISH_PER_CAST_MAX
        self.owned = set()                         # one-time shop items bought
        self.window_charges = 0                    # barred windows protection
        self.pike_jaw = False                      # earned by beating the boss

        # story
        self.stage = 0
        self.stage_progress = 0

        # end state
        self.bad_ending_locked = False
        self.ended = False
        self.end_reason = ""

        # stats for analysis
        self.hunger_history = []                   # hunger after each outdoor turn
        self.nakki_encounters = 0
        self.bonuses_won = 0
        self.bonuses_lost = 0
        self.fish_deposited = 0
        self.fish_sacrificed = 0

        self.log = []

    # ------------------------------------------------------------------
    # Derived values (the UI shows these)
    # ------------------------------------------------------------------
    @property
    def nakki_chance(self):
        """Chance per outdoor turn that Näkki surfaces. Driven ONLY by wrath."""
        return lerp(C.NAKKI_CHANCE_AT_ZERO_WRATH,
                    C.NAKKI_CHANCE_AT_MAX_WRATH,
                    self.wrath / C.WRATH_MAX)

    @property
    def bonus_chance(self):
        """Chance a deposit right now pays bonus tokens (the gamble)."""
        if self.hunger < C.BONUS_HUNGER_THRESHOLD:
            return 0.0
        span = C.HUNGER_MAX - C.BONUS_HUNGER_THRESHOLD
        t = 1.0 if span <= 0 else (self.hunger - C.BONUS_HUNGER_THRESHOLD) / span
        return lerp(C.BONUS_CHANCE_AT_THRESHOLD, C.BONUS_CHANCE_AT_MAX, t)

    @property
    def story_done(self):
        return self.stage >= len(C.STORY_STAGES)

    @property
    def stage_name(self):
        return "Complete" if self.story_done else C.STORY_STAGES[self.stage][0]

    def stage_length(self, i=None):
        """Outdoor turns needed to finish a stage (slumberhook shortens the boss)."""
        i = self.stage if i is None else i
        turns = C.STORY_STAGES[i][1]
        if i == C.BOSS_STAGE_INDEX and "slumberhook" in self.owned:
            turns = max(1, turns - C.SLUMBERHOOK_TURN_REDUCTION)
        return turns

    @property
    def avg_hunger(self):
        if not self.hunger_history:
            return self.hunger
        return sum(self.hunger_history) / len(self.hunger_history)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def available_actions(self):
        if self.ended:
            return []
        acts = []
        if self.haul < self.haul_capacity:
            acts.append("fish")
        if self.haul > 0:
            acts.append("deposit")
        if not self.story_done:
            acts.append("story")
        if self.haul > 0 and self.wrath > 0:
            acts.append("seita_fish")
        if self.pike_jaw and self.wrath > 0:
            acts.append("seita_jaw")
        for item, info in C.SHOP.items():
            if self.tokens < info["price"]:
                continue
            if info.get("once") and item in self.owned:
                continue
            acts.append(f"shop:{item}")
        return acts

    def act(self, action):
        """Perform one action. Returns the messages it produced."""
        start = len(self.log)
        if action not in self.available_actions():
            self._say(f"Can't do '{action}' right now.")
            return self.log[start:]

        if action == "fish":
            self._fish()
        elif action == "deposit":
            self._deposit()
        elif action == "story":
            self._story()
        elif action == "seita_fish":
            self._seita_fish()
        elif action == "seita_jaw":
            self._seita_jaw()
        elif action.startswith("shop:"):
            self._buy(action.split(":", 1)[1])

        return self.log[start:]

    # --- outdoor (cost time) ------------------------------------------
    def _fish(self):
        if self._outdoor_turn(nakki_possible=True):
            return
        caught = self.rng.randint(C.FISH_PER_CAST_MIN, self.max_fish_per_cast)
        caught = min(caught, self.haul_capacity - self.haul)
        self.haul += caught
        if caught:
            self._say(f"Caught {caught} fish. Haul {self.haul}/{self.haul_capacity}.")
        else:
            self._say("Nothing bites.")

    def _story(self):
        if self._outdoor_turn(nakki_possible=C.NAKKI_CAN_EMERGE_DURING_STORY):
            return
        self.stage_progress += 1
        needed = self.stage_length()
        name = self.stage_name
        if self.stage_progress < needed:
            self._say(f"{name}: progress {self.stage_progress}/{needed}.")
            return

        self._say(f"{name}: COMPLETE.")
        if self.stage == C.BOSS_STAGE_INDEX:
            self.pike_jaw = True
            self._say("You took the pike's jaw. It could be offered at the Seita.")
        self.stage += 1
        self.stage_progress = 0
        if self.story_done:
            self._finish_story()

    # --- free on time (cost resources) --------------------------------
    def _deposit(self):
        n = self.haul
        self.haul = 0
        tokens = n * C.TOKENS_PER_FISH

        # The gamble: chance is judged on hunger BEFORE the fish feed the village.
        chance = self.bonus_chance
        if chance > 0:
            if self.rng.random() < chance:
                tokens = round(tokens * C.BONUS_MULTIPLIER)
                self.bonuses_won += 1
                self._say(f"Desperate village pays extra! ({chance:.0%} gamble won)")
            else:
                self.bonuses_lost += 1
                self._say(f"No bonus this time. ({chance:.0%} gamble lost)")

        self.tokens += tokens
        self.hunger = max(0.0, self.hunger - n * C.HUNGER_RELIEF_PER_FISH)
        self.wrath = min(C.WRATH_MAX, self.wrath + n * C.WRATH_PER_FISH_DEPOSITED)
        self.fish_deposited += n
        self._say(f"Deposited {n} fish: +{tokens} tokens. "
                  f"Hunger {self.hunger:.0f}, wrath {self.wrath:.0f}.")

    def _seita_fish(self):
        self.haul -= 1
        self.fish_sacrificed += 1
        self.wrath = max(0.0, self.wrath - C.SEITA_WRATH_PER_FISH)
        self._say(f"Sacrificed a fish at the Seita. Wrath {self.wrath:.0f}.")

    def _seita_jaw(self):
        self.pike_jaw = False
        self.wrath = max(0.0, self.wrath - C.SEITA_WRATH_PIKE_JAW)
        self._say(f"Offered the pike jaw at the Seita. Wrath {self.wrath:.0f}.")

    def _buy(self, item):
        self.tokens -= C.SHOP[item]["price"]
        if C.SHOP[item].get("once"):
            self.owned.add(item)

        if item == "iron":
            self.iron += 1
        elif item == "haul_bucket":
            self.haul_capacity += C.HAUL_BUCKET_BONUS
        elif item == "murmuring_bait":
            self.max_fish_per_cast += 1
        elif item == "barred_windows":
            self.window_charges += 1
        # slumberhook: no instant effect, stage_length() checks for it
        self._say(f"Bought {item}. Tokens left: {self.tokens}.")

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _outdoor_turn(self, nakki_possible):
        """Advance time by one outdoor turn.
        Returns True if the turn was interrupted (Näkki or run ended)."""
        self.turn += 1
        self.hunger = min(float(C.HUNGER_MAX), self.hunger + C.HUNGER_PER_OUTDOOR_TURN)
        self.hunger_history.append(self.hunger)

        if self.hunger >= C.HUNGER_MAX:
            self._hunger_maxed()
            if self.ended:
                return True

        if self.turn >= C.MAX_TURNS:
            self._end("timeout", "Out of time. The story was never finished.")
            return True

        if nakki_possible and self.rng.random() < self.nakki_chance:
            self._nakki()
            return True
        return False

    def _nakki(self):
        self.nakki_encounters += 1
        self._say(f"!!! NÄKKI SURFACES (chance was {self.nakki_chance:.0%})")
        if self.iron >= C.IRON_PER_BANISH:
            self.iron -= C.IRON_PER_BANISH
            self._say(f"You throw iron. It sinks back... for now. Iron left: {self.iron}.")
        elif self.window_charges > 0:
            self.window_charges -= 1
            self._say("No iron! You flee to the cabin. The barred windows hold.")
        elif C.NO_IRON_RESULT == "game_over":
            self._end("caught", "No iron. Näkki drags you under.")
        else:  # "lose_haul"
            lost = self.haul
            self.haul = 0
            self.hunger = min(float(C.HUNGER_MAX), self.hunger + C.NO_IRON_HUNGER_SPIKE)
            self._say(f"No iron! You escape, but lose {lost} fish. Hunger spikes.")
            if self.hunger >= C.HUNGER_MAX:
                self._hunger_maxed()

    def _hunger_maxed(self):
        if C.HUNGER_MAX_RESULT == "game_over":
            self._end("starved", "The village starved.")
        elif not self.bad_ending_locked:
            self.bad_ending_locked = True
            self._say("The village is starving. The bad ending is now sealed.")

    def _finish_story(self):
        good = (not self.bad_ending_locked
                and self.avg_hunger <= C.GOOD_ENDING_AVG_HUNGER)
        if good:
            self._end("good_ending", "Näkki is banished. The lost souls find peace.")
        else:
            self._end("bad_ending", "Näkki is banished... and you become the next one.")

    def _end(self, reason, message):
        self.ended = True
        self.end_reason = reason
        self._say(f"=== END: {message} ===")

    def _say(self, msg):
        self.log.append(f"[T{self.turn:>3}] {msg}")

    def snapshot(self):
        """All the numbers in one dict - handy for UI and batch stats."""
        return {
            "turn": self.turn,
            "hunger": self.hunger,
            "avg_hunger": self.avg_hunger,
            "wrath": self.wrath,
            "nakki_chance": self.nakki_chance,
            "bonus_chance": self.bonus_chance,
            "tokens": self.tokens,
            "iron": self.iron,
            "haul": self.haul,
            "haul_capacity": self.haul_capacity,
            "stage": self.stage,
            "stage_name": self.stage_name,
            "stage_progress": self.stage_progress,
            "pike_jaw": self.pike_jaw,
            "owned": sorted(self.owned),
            "nakki_encounters": self.nakki_encounters,
            "bonuses_won": self.bonuses_won,
            "bonuses_lost": self.bonuses_lost,
            "fish_deposited": self.fish_deposited,
            "fish_sacrificed": self.fish_sacrificed,
            "ended": self.ended,
            "end_reason": self.end_reason,
        }


if __name__ == "__main__":
    # Quick smoke test: one run with a purely random player.
    g = Game(seed=1)
    while not g.ended:
        g.act(g.rng.choice(g.available_actions()))
    print("\n".join(g.log[-15:]))
    print(g.snapshot())