"""
Interactive mode: you choose every action and watch the bars move.

Run:   python play.py          (random run)
       python play.py 42       (repeatable run with seed 42)

Type the number of an action and press Enter.  h = help, q = quit.
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
LOG_LINES = 10


def mmss(seconds):
    m, s = divmod(int(seconds), 60)
    return f"{m:02d}:{s:02d}"


def bar(frac, width=30, colors=("green", "yellow", "red"), thresholds=(0.5, 0.8),
        marker=None):
    frac = max(0.0, min(1.0, frac))
    filled = round(frac * width)
    color = colors[0] if frac < thresholds[0] else colors[1] if frac < thresholds[1] else colors[2]
    t = Text()
    for i in range(width):
        ch, style = ("█", color) if i < filled else ("░", "grey37")
        if marker is not None and i == round(marker * width):
            ch, style = "|", "bold white"
        t.append(ch, style=style)
    return t


def status_panel(g):
    s = g.snapshot()
    table = Table.grid(padding=(0, 2))
    table.add_column(justify="right", style="bold")
    table.add_column()
    table.add_column()

    note = ""
    if s["bonus_chance"] > 0:
        note = f"  [magenta]gamble {s['bonus_chance']:.0%}[/]"
    if g.collapsed:
        note = "  [red]VILLAGE COLLAPSED[/]"
    table.add_row("Hunger", bar(s["hunger"], marker=C.BONUS_HUNGER_THRESHOLD),
                  f"{s['hunger']:.0%}{note}")
    frozen = "  [grey62](frozen)[/]" if g.collapsed else ""
    table.add_row("Wrath", bar(s["wrath"] / C.WRATH_MAX, colors=("cyan", "blue", "magenta"),
                               marker=C.GOOD_ENDING_MAX_WRATH / C.WRATH_MAX),
                  f"{s['wrath']:.0f}/{C.WRATH_MAX}  (good ending ≤ {C.GOOD_ENDING_MAX_WRATH}){frozen}")
    table.add_row("Näkki", Text(f"shallow {s['nakki_shallow']:.0%}   deep {s['nakki_deep']:.0%}"
                                f"   per cast", style="red" if s["nakki_shallow"] > 0.12 else ""), "")

    if g.story_done:
        table.add_row("Story", bar(1, colors=("green",) * 3), "done")
    else:
        table.add_row("Story", bar(s["stage_progress"] / g.stage_length(), colors=("white",) * 3),
                      f"{s['stage_progress']:.0f}/{g.stage_length():.0f}s")
        table.add_row("", Text(f"Stage {s['stage'] + 1}/{len(C.STORY_STAGES)}: {s['stage_name']}",
                               style="grey62"), "")

    res = Text()
    res.append(f"Tokens {s['tokens']}   ", style="yellow")
    res.append(f"Iron {s['iron']}   ", style="bold white" if s["iron"] else "bold red")
    haul = ", ".join(s["haul"]) or "empty"
    res.append(f"Haul {len(s['haul'])}/{s['haul_capacity']} ({haul})   ", style="cyan")
    if s["has_fat_pike"]:
        res.append("+ Fat Pike", style="magenta")
    owned = ", ".join(s["owned"]) or "nothing yet"
    title = (f"[bold]{mmss(s['time'])}[/]  ·  at the {s['location']}  ·  "
             f"Näkki encounters {s['nakki_encounters']}")
    return Panel(Group(table, Text(""), res, Text(f"Owned: {owned}", style="grey62")),
                 title=title, border_style="blue")


def log_panel(g):
    text = Text()
    for line in g.log[-LOG_LINES:] or ["Your first night at the cabin begins."]:
        style = ""
        if "NÄKKI" in line or "drags you" in line or "collapsed" in line:
            style = "bold red"
        elif "won" in line or "COMPLETE" in line:
            style = "green"
        elif "lost" in line or "No iron" in line:
            style = "yellow"
        elif "END" in line:
            style = "bold magenta"
        text.append(line + "\n", style=style)
    return Panel(text, title="What happened", border_style="grey50")


def describe(g, a):
    risk = "[grey62](outdoor: hunger rises, Näkki risk)[/]"
    if a == "cast_shallow":
        return f"Cast in the shallows  {risk}"
    if a == "cast_deep":
        return f"Cast in deep water  [grey62](further walk, better fish, more Näkki)[/]"
    if a == "deposit":
        n = len(g.haul) + g.has_fat_pike
        odds = f", [magenta]{g.bonus_chance:.0%} double-token gamble[/]" if g.bonus_chance else ""
        walk = "walk back, " if g.location != "cabin" else ""
        return f"Deposit {n} fish  [grey62]({walk}-hunger, +wrath, +tokens{odds})[/]"
    if a == "story":
        return f"Story: {g.stage_name}  {risk}"
    if a == "seita":
        return f"Seita: sacrifice cheapest fish  [grey62](-{C.SEITA_WRATH_PER_FISH} wrath)[/]"
    if a == "seita_fatpike":
        return f"Seita: offer the Fat Pike  [grey62](-{C.SEITA_WRATH_FAT_PIKE} wrath)[/]"
    if a.startswith("shop:"):
        item = a.split(":", 1)[1]
        info = C.SHOP[item]
        return f"Shop: {item}  [yellow]{info['price']} tokens[/]  [grey62]({info['effect']})[/]"
    return a


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
• Outdoor time (walking, casting, story) raises hunger by {C.HUNGER_PER_SECOND * 60:.2f} per minute.
  The cabin pauses hunger. Shop and Seita take no time.
• Deposit feeds the village and pays tokens, but each fish adds +{C.WRATH_PER_FISH_DEPOSITED} wrath.
• Wrath only raises Näkki's chance to bite. Iron banishes her. No iron: pay {C.BOARDING_COST}
  tokens to board the windows and survive. No tokens: game over.
• Above {C.BONUS_HUNGER_THRESHOLD:.0%} hunger, deposits are a gamble for x{C.BONUS_MULTIPLIER:g} tokens.
• At 100% hunger the village collapses: no more tokens, wrath freezes, bad ending sealed.
• Good ending: finish the story without a collapse, with wrath ≤ {C.GOOD_ENDING_MAX_WRATH}.
"""


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
        if choice.isdigit() and 1 <= int(choice) <= len(actions):
            g.act(actions[int(choice) - 1])

    render(g, [])
    s = g.snapshot()
    t = Table(title="Run summary", show_header=False, border_style="magenta")
    t.add_column(style="bold")
    t.add_column()
    rows = [("Result", s["end_reason"].replace("_", " ")),
            ("Time", f"{mmss(s['time'])} (outdoors {mmss(s['outdoor_time'])})"),
            ("Tokens earned", str(s["tokens_earned"])),
            ("Fish deposited / sacrificed", f"{s['fish_deposited']} / {s['fish_sacrificed']}"),
            ("Gambles won / lost", f"{s['bonuses_won']} / {s['bonuses_lost']}"),
            ("Näkki encounters", f"{s['nakki_encounters']} (iron {s['iron_used']}, boarded {s['boardings']})"),
            ("Bought", ", ".join(s["owned"]) or "-")]
    for k, v in rows:
        t.add_row(k, v)
    console.print(t)


if __name__ == "__main__":
    main()