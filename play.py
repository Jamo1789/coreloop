"""
Interactive mode: you choose every action and watch the bars move.

Run:   python play.py          (random run)
       python play.py 42       (repeatable run with seed 42)

Each round, type the number of an action and press Enter.
Also: h = help, q = quit.
"""
import sys

from rich.console import Console, Group
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from rich.text import Text

import config as C
from engine import Game

console = Console()
LOG_LINES = 10          # how many recent events to show


# ----------------------------------------------------------------------
# Drawing helpers
# ----------------------------------------------------------------------
def bar(value, maximum, width=30, colors=("green", "yellow", "red"),
        thresholds=(0.5, 0.8)):
    """A text progress bar that changes color as it fills."""
    frac = 0.0 if maximum <= 0 else max(0.0, min(1.0, value / maximum))
    filled = round(frac * width)
    if frac < thresholds[0]:
        color = colors[0]
    elif frac < thresholds[1]:
        color = colors[1]
    else:
        color = colors[2]
    t = Text()
    t.append("█" * filled, style=color)
    t.append("░" * (width - filled), style="grey37")
    return t


def status_panel(g):
    s = g.snapshot()
    table = Table.grid(padding=(0, 2))
    table.add_column(justify="right", style="bold")
    table.add_column()
    table.add_column(justify="right")

    # Hunger - mark the bonus-gamble zone
    hunger_note = ""
    if s["bonus_chance"] > 0:
        hunger_note = f"  [magenta]gamble {s['bonus_chance']:.0%}[/]"
    if g.bad_ending_locked:
        hunger_note += "  [red]BAD ENDING SEALED[/]"
    table.add_row("Hunger", bar(s["hunger"], C.HUNGER_MAX),
                  f"{s['hunger']:.0f}/{C.HUNGER_MAX}{hunger_note}")
    table.add_row("", Text(f"avg {s['avg_hunger']:.0f} "
                           f"(good ending needs ≤ {C.GOOD_ENDING_AVG_HUNGER})",
                           style="grey62"), "")

    table.add_row("Wrath", bar(s["wrath"], C.WRATH_MAX,
                               colors=("cyan", "blue", "magenta")),
                  f"{s['wrath']:.0f}/{C.WRATH_MAX}")
    table.add_row("Näkki", bar(s["nakki_chance"], C.NAKKI_CHANCE_AT_MAX_WRATH,
                               colors=("grey62", "yellow", "red")),
                  f"{s['nakki_chance']:.0%} per outdoor turn")

    # Story
    total_stages = len(C.STORY_STAGES)
    if g.story_done:
        story_bar, story_txt = bar(1, 1, colors=("green",) * 3), "done"
    else:
        need = g.stage_length()
        story_bar = bar(s["stage_progress"], need, colors=("white",) * 3)
        story_txt = f"{s['stage_progress']}/{need}"
    table.add_row("Story", story_bar, story_txt)
    table.add_row("", Text(f"Stage {min(s['stage'] + 1, total_stages)}/{total_stages}: "
                           f"{s['stage_name']}", style="grey62"), "")

    # Resources
    res = Text()
    res.append(f"Tokens {s['tokens']}   ", style="yellow")
    res.append(f"Iron {s['iron']}   ", style="bold white" if s["iron"] else "bold red")
    res.append(f"Haul {s['haul']}/{s['haul_capacity']}   ", style="cyan")
    if s["pike_jaw"]:
        res.append("Pike jaw   ", style="magenta")
    if g.window_charges:
        res.append(f"Barred windows x{g.window_charges}", style="green")

    owned = ", ".join(s["owned"]) if s["owned"] else "nothing yet"
    title = f"[bold]Turn {s['turn']}[/]  ·  Näkki encounters {s['nakki_encounters']}"
    return Panel(Group(table, Text(""), res, Text(f"Owned: {owned}", style="grey62")),
                 title=title, border_style="blue")


def log_panel(g):
    lines = g.log[-LOG_LINES:] or ["Your first night at the cabin begins."]
    text = Text()
    for line in lines:
        style = ""
        if "NÄKKI" in line or "drags you" in line:
            style = "bold red"
        elif "gamble won" in line or "COMPLETE" in line:
            style = "green"
        elif "gamble lost" in line or "starving" in line or "No iron" in line:
            style = "yellow"
        elif "END" in line:
            style = "bold magenta"
        text.append(line + "\n", style=style)
    return Panel(text, title="What happened", border_style="grey50")


def describe(g, action):
    """Human-readable label for an action, with its cost."""
    if action == "fish":
        return "Fish  [grey62](outdoor: +hunger, Näkki risk)[/]"
    if action == "deposit":
        odds = g.bonus_chance
        gamble = f", [magenta]{odds:.0%} bonus chance[/]" if odds else ""
        return (f"Deposit {g.haul} fish  [grey62](free: -hunger, +wrath, "
                f"+tokens{gamble})[/]")
    if action == "story":
        return f"Story: {g.stage_name}  [grey62](outdoor: +hunger, Näkki risk)[/]"
    if action == "seita_fish":
        return (f"Seita: sacrifice 1 fish  [grey62](free: "
                f"-{C.SEITA_WRATH_PER_FISH} wrath)[/]")
    if action == "seita_jaw":
        return (f"Seita: offer pike jaw  [grey62](free: "
                f"-{C.SEITA_WRATH_PIKE_JAW} wrath)[/]")
    if action.startswith("shop:"):
        item = action.split(":", 1)[1]
        info = C.SHOP[item]
        return (f"Shop: {item}  [yellow]{info['price']} tokens[/]  "
                f"[grey62]({info['effect']})[/]")
    return action


def menu_panel(g, actions):
    text = Text()
    for i, a in enumerate(actions, 1):
        text.append(f" {i:>2}. ", style="bold")
        text.append_text(Text.from_markup(describe(g, a)))
        text.append("\n")
    text.append("\n  h = help   q = quit", style="grey50")
    return Panel(text, title="Choose an action", border_style="green")


def render(g, actions):
    console.clear()
    console.print(status_panel(g))
    console.print(log_panel(g))
    if actions:
        console.print(menu_panel(g, actions))


HELP = f"""[bold]How it works[/]
• [bold]Outdoor[/] actions (fish, story) cost one turn: hunger +{C.HUNGER_PER_OUTDOOR_TURN}, and Näkki may surface.
• [bold]Free[/] actions (deposit, Seita, shop) cost no time, only resources.
• Depositing feeds the village and gives tokens, but every fish adds +{C.WRATH_PER_FISH_DEPOSITED} wrath.
• Wrath only raises Näkki's chance to surface. Iron banishes it; without iron you're in trouble.
• Above hunger {C.BONUS_HUNGER_THRESHOLD}, deposits become a gamble for x{C.BONUS_MULTIPLIER:g} tokens.
• Finish all story stages to reach an ending. Keep average hunger ≤ {C.GOOD_ENDING_AVG_HUNGER}
  and never let it hit {C.HUNGER_MAX} for the good ending.
"""


# ----------------------------------------------------------------------
# Main loop
# ----------------------------------------------------------------------
def main():
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else C.RANDOM_SEED
    g = Game(seed=seed)

    while not g.ended:
        actions = g.available_actions()
        render(g, actions)
        choice = Prompt.ask("[bold]>[/]", default="").strip().lower()

        if choice == "q":
            console.print("You leave the cabin. The lake waits.")
            return
        if choice == "h":
            console.print(Panel(HELP, border_style="cyan"))
            Prompt.ask("[grey50]Press Enter to continue[/]", default="")
            continue
        if not choice.isdigit() or not 1 <= int(choice) <= len(actions):
            continue
        g.act(actions[int(choice) - 1])

    # Final screen
    render(g, [])
    s = g.snapshot()
    summary = Table(title="Run summary", show_header=False, border_style="magenta")
    summary.add_column(style="bold")
    summary.add_column()
    summary.add_row("Result", s["end_reason"].replace("_", " "))
    summary.add_row("Turns", str(s["turn"]))
    summary.add_row("Average hunger", f"{s['avg_hunger']:.1f}")
    summary.add_row("Fish deposited", str(s["fish_deposited"]))
    summary.add_row("Fish sacrificed", str(s["fish_sacrificed"]))
    summary.add_row("Gambles won / lost", f"{s['bonuses_won']} / {s['bonuses_lost']}")
    summary.add_row("Näkki encounters", str(s["nakki_encounters"]))
    summary.add_row("Bought", ", ".join(s["owned"]) or "-")
    console.print(summary)


if __name__ == "__main__":
    main()