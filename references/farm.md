# Farming PAPER

Papertrade mints PAPER when a position closes at a loss. A farm holds a long and a short
of the same size on one market at once, so one side's loss is the other side's gain: the
losing leg mints PAPER, and the cycle costs what Papertrade keeps back from the winning
leg. A duty runs the cycles until the owner's budget is spent or they stop it, so they
fill in one ticket and approve it once:

```text
open a long + a short → price moves ±MOVE_PCT → close both → note the cycle → again
```

**The cost is what the winning leg gives back.** A winning leg is paid back about 10%
less than it made (much less on small moves), then Papertrade keeps its win fee (2%
today) of the rest; a loss costs nothing extra. On BTC a 1% cycle keeps about 86% of the
win, a 0.3% cycle about 82%. So a cycle costs about $1.36 per $1,000 leg at 1%, and $0.53
at 0.3%. `farm-quote` works it out; never do the arithmetic yourself.

## The ticket

"I want to farm PAPER" means a farm duty. **One farm per market:** read the owner's duties
first, and if a farm on that market is running (titled "Farm PAPER on <MARKET>, ..."), say so
and show it instead of a new ticket. A second one would take the first one's legs for its
own. A farm on the other market is fine. Never assume a setting: no leverage, size, move
or budget is the owner's until they say it. Show the ticket with every field blank, its
limits beside it, and this turn's `availableUsd`, and ask them to fill it in:

```text
Farm ticket — Papertrade (you have $<availableUsd>)
  Market             ___     BTC or ETH
  Margin per leg     $___    at least $10, and margin x leverage at least $1,000;
                             each cycle holds two legs (a long and a short)
  Leverage           ___x    the losing leg is wiped out at about a (100 / leverage)% move
  Move per cycle     ±___%   both legs close once price moves this far, either way
  Budget             $___    the most the farm may lose; it runs until this is spent
                             or they say "stop farming"
```

Ask again for only the fields still blank, showing what they have filled.

**Never fill a field for them, even when asked.** Not a value, not a "what I'd go with",
not a list of picks to confirm: the farm opens legs with no one asking, so every number
has to be one they typed. "You pick", "default", "whatever" or "go" is not a value:

> I can't choose these for you: the farm trades on its own once it starts, so each number
> has to be yours. Still blank: leverage, move per cycle, budget.

Never suggest a leverage higher than one they named. A field they gave earlier in the conversation
counts once you repeat it back in the ticket.

**Never judge Papertrade's room yourself.** A leg needs room for its whole position
(margin x leverage, such as $1,000), so $16 of room is full, not "room". Leave
`longRoomUsd`/`shortRoomUsd` out of the ticket; `farm-quote` says when a side is full.

Then quote it. It signs nothing, refuses settings that cannot work (and says which value
to change), and works out the cycle:

```sh
python3 /tmp/papertrade.py farm-quote --owner <OWNER> --market <MARKET> --margin <USD> --leverage <N> --move <PCT> --budget <USD>
```

Quote only once every field has their value. A refusal is said as written, and the ticket
shown again with that field marked for them to change.
Otherwise say, from its fields only:

> **{badCase}**
>
> **{summary}** {breakEven} That is {costPer1kPaperUsd} per 1,000 PAPER. The losing leg pays
> {losingLegsPayUsd}; the winning leg keeps {winningLegsKeepUsd} ({winningKeepsPct}%).
>
> BTC is at {markPrice}; this cycle closes at {exitDownPrice} or {exitUpPrice}. Your
> {budgetUsd} budget is about {cyclesForBudget} cycles and {paperForBudget} PAPER. It runs
> until that is spent or you say "stop farming", and stops by itself if BTC moves 1%
> inside a minute. Each cycle holds {cycleHoldsUsd} while it runs. Start it?

Say each of `warnings` after it, word for word. When `paperPerCycle` is null, say the
summary as written and skip the PAPER figures. Their yes, after you said the bad case, is
their yes to every leg the farm opens: a duty asks no one before it opens.

## Filing it

1. The key must be `ready` (`SKILL.md` step 1); otherwise do step 2 first and file the
   farm once it is.
2. Get the path the duty runs:

   ```sh
   python3 /tmp/papertrade.py duty-helper --owner <OWNER>
   ```

3. Check again that no farm runs on that market. Then file the duty below **exactly as
   written; never edit its code**. Send:
   - a `timer` trigger every 60 seconds;
   - `PARAMS`, as numbers: `PAPERTRADE_HELPER` (the `helper` path), `MARKET`,
     `MARGIN_USD`, `LEVERAGE`, `MOVE_PCT` and `BUDGET_USD`, exactly as quoted;
   - the title `Farm PAPER on {MARKET}, ${BUDGET_USD} budget`;
   - these three, as written:

   ```json
   {"statusTemplate": {"starting": "Opening the first long and short",
                       "opening": "Opening cycle {cycle} · {paper} PAPER so far",
                       "open": "{moved}% of {MOVE_PCT}% · {paper} PAPER · ${spent} spent",
                       "full": "Papertrade {side} full · waiting"},
    "statusExamples": {"cycle": 3, "moved": 0.21, "paper": 108, "spent": 1.54, "side": "longs"},
    "statusPlan": {"watching": "the price move from the pair's entry; both legs close at MOVE_PCT",
                   "shows": "how far it has moved toward that, PAPER minted so far, and budget spent",
                   "when": "it checks every minute and closes on the move, so no time is shown",
                   "confusion": "the % is the price move, not profit; spent is the whole farm's cost"}}
   ```

   The first try is refused once with a preview of the row: send the same payload again
   with `statusSeen` set to the token it printed. Change nothing else.
4. Tell them it is running, that each cycle lands in its thread with what it cost and
   minted, and that "stop farming" ends it.

## While it runs

- **"How's my farm?"** Read the duty's status and log, then `history`. The status has the
  budget spent so far; the log has one `cycle` line per closed cycle with its PnL and PAPER.
- **"Stop farming."** Pause the duty first, so it opens nothing more, then read `account`.
  The farm's legs are the positions on its `MARKET` at its `MARGIN_USD` and `LEVERAGE`:
  say their PnL before fees and close them all in one `close --ids` (`SKILL.md` step 7).
  If the owner holds other positions of that shape, ask which first.
- **A change** ("make it ETH", "bigger"): stop it as above, show the ticket with the new
  values, quote it, and file a new farm once they agree.

## What the duty does

Each minute it reads `account`, then:

- **Stops** (closing every farm leg first) when the price moved 1% or more since the
  last minute. With nothing open it also stops once its closed cycles have lost
  `BUDGET_USD` in all, or when a cycle no longer fits in `availableUsd`. It checks the
  budget between cycles, so the last cycle can take it a little past; a wiped-out leg,
  up to that leg's margin past.
- **Opens** a cycle when none is open and both sides have room under Papertrade's
  open-interest cap: the tighter side first, so a refusal leaves nothing open. When a side
  is full it waits, with one note to the owner, and starts once both have room. A cap
  that fills between the check and the open is not counted as a failure.
- **Just opened:** waits for all the legs. Some missing after two minutes means Papertrade
  took only part of it: it closes what did open and tries a fresh cycle; three in a row
  and it stops.
- **Cycle open:** closes every leg in one request once price is `MOVE_PCT` from the
  legs' average entry. A leg gone on its own (wiped out) closes the rest at once.
- **Cycle closed:** reads `history` for its legs and notes the cycle (PnL, PAPER) in the
  duty's thread without a push.

It never touches a position it did not open. A refused close is sent again every minute,
never given up on, with one note to the owner after five. A key that is not `ready` gets
one note and no request until it is; `renew` still trades. After a request is accepted it waits two
minutes before sending another for the same legs.

```python
import json
import os
import subprocess
import time

import bevo

PARAMS = json.loads(os.environ.get("PARAMS") or "{}")
INTENTS = "https://exchange.papertrade.xyz/intents"
MARKET = PARAMS["MARKET"]
MARGIN = float(PARAMS["MARGIN_USD"])
LEVERAGE = int(PARAMS["LEVERAGE"])
MOVE = float(PARAMS["MOVE_PCT"]) / 100
BUDGET = float(PARAMS["BUDGET_USD"])
WAIT = 120
SPIKE = 0.01


def helper(*args):
    run = subprocess.run(["python3", PARAMS["PAPERTRADE_HELPER"], *args],
                         capture_output=True, text=True, timeout=120, check=False)
    if run.returncode != 0:
        bevo.log(f"papertrade {args[0]}: {run.stderr.strip()}")
        return None
    return json.loads(run.stdout)


def send(body_file):
    run = subprocess.run(["curl", "-sS", "-X", "POST", INTENTS, "-H", "Content-Type: application/json",
                          "--data", "@" + body_file, "-w", "\n%{http_code}"],
                         capture_output=True, text=True, timeout=60, check=False)
    lines = run.stdout.strip().splitlines()
    return (lines[-1] if lines else "no answer"), "\n".join(lines[:-1])


def request(what, *args):
    """Build one intent and send it once. True when Papertrade accepted it."""
    built = helper(*args)
    if built is None:
        return False
    status, answer = send(built["bodyFile"])
    bevo.log(f"{what}: {status} {answer}")
    if status != "201" and "openInterest" in answer:
        bevo.state["oi_full"] = True
    return status == "201"


def close(ids, why):
    """Send a close. A refusal is retried next minute, never given up on: failing the run
    would pause the duty with its legs still open."""
    if request(f"close {','.join(ids)} ({why})", "close", "--owner", owner, "--ids", ",".join(ids)):
        bevo.state["sent_at"] = time.time()
        bevo.state["close_tries"] = 0
        return True
    tries = bevo.state.get("close_tries", 0) + 1
    bevo.state["close_tries"] = tries
    if tries == 5:
        bevo.notify(f"Papertrade has refused to close your farm's {MARKET} legs ({', '.join(ids)}) five times. "
                    "I keep trying every minute; you can also close them in the Papertrade app.",
                    push="Farm legs still open")
    return False


def totals():
    return bevo.state.get("cycles", 0), bevo.state.get("pnl", 0.0), bevo.state.get("paper", 0.0)


def finish(reason):
    cycles, pnl, paper = totals()
    bevo.done(f"Farm stopped: {reason}. {cycles} cycle{'' if cycles == 1 else 's'}, {paper:,.0f} PAPER minted, "
              f"{max(0.0, -pnl):,.2f} of your {BUDGET:,.2f} USD budget spent.")


def report(ids):
    """Count a closed cycle once history has its legs; give up on the figures after 5 minutes."""
    hist = helper("history", "--owner", owner, "--limit", "50")
    legs = [t for t in (hist or {}).get("trades", []) if t["positionId"] in ids]
    if len(legs) < len(ids) and time.time() - bevo.state["closed_at"] < 300:
        return False
    pnl = sum(t["pnlUsd"] for t in legs)
    paper = sum(t.get("paperMinted") or 0 for t in legs)
    cycles = bevo.state.get("cycles", 0) + 1
    bevo.state.update(cycles=cycles, pnl=bevo.state.get("pnl", 0.0) + pnl,
                      paper=bevo.state.get("paper", 0.0) + paper)
    if len(legs) < len(ids):
        line = f"Cycle {cycles} closed; Papertrade's history does not show its figures yet."
    else:
        wiped = " A leg was wiped out." if any(t["outcome"] == "liquidated" for t in legs) else ""
        line = f"Cycle {cycles} closed: {pnl:+.2f} USD, {paper:,.0f} PAPER minted.{wiped}"
    bevo.log(f"cycle {cycles}: ids {','.join(ids)} pnl {pnl:+.4f} paper {paper:.4f}")
    bevo.notify(line, quiet=True)
    return True


def stop_with(reason, open_ids):
    """Close every farm leg still open, then finish once they are gone."""
    bevo.state["stop"] = reason
    bevo.state.pop("opening", None)
    bevo.state.pop("legs", None)
    if open_ids:
        close(open_ids, "stop")
        bevo.state["closing"] = open_ids


owner = bevo.read("/me")["user"]["agentWalletAddress"]
for tick in bevo.ticks():
    acct = helper("account", "--owner", owner)
    if acct is None:
        bevo.fail("could not read the Papertrade account")
        continue
    key = acct["sessionKey"]
    if key["action"] not in ("ready", "renew"):
        if not bevo.state.get("told_key"):
            bevo.notify("Your Papertrade session key needs renewing. Ask me about Papertrade in a chat "
                        "to approve it; the farm is on hold until then.", push="Renew Papertrade key")
            bevo.state["told_key"] = True
        continue
    bevo.state["told_key"] = False
    open_by_id = {p["id"]: p for p in acct["positions"]}
    waited = time.time() - bevo.state.get("sent_at", 0)
    cycles, pnl, paper = totals()
    mine = [i for i in bevo.state.get("legs", []) + bevo.state.get("closing", []) if i in open_by_id]
    if "opening" in bevo.state:
        mine += [p["id"] for p in acct["positions"] if p["id"] not in set(bevo.state["opening"])
                 and p["market"] == MARKET and p["leverage"] == LEVERAGE]

    # A price spike stops the farm even mid-cycle: it closes every farm leg first.
    if not bevo.state.get("stop"):
        marks = [open_by_id[i]["markPrice"] for i in mine if open_by_id[i]["markPrice"]]
        last = bevo.state.get("last_mark")
        bevo.state["last_mark"] = marks[0] if marks else None
        if marks and last and abs(marks[0] - last) / last >= SPIKE:
            stop_with(f"{MARKET} moved 1% or more inside a minute (safety stop)", mine)
            continue

    # A cycle is closing: count it once its legs are gone.
    if "closing" in bevo.state:
        ids = bevo.state["closing"]
        still = [i for i in ids if i in open_by_id]
        if still:
            if waited >= WAIT:
                close(still, "still open")
            continue
        if "closed_at" not in bevo.state:
            bevo.state["closed_at"] = time.time()
        if report(ids):
            bevo.state.pop("closing")
            bevo.state.pop("closed_at")
        continue

    if bevo.state.get("stop"):
        finish(bevo.state["stop"])

    # A cycle just opened: find its legs among the new positions.
    if "opening" in bevo.state:
        before = set(bevo.state["opening"])
        new = [p["id"] for p in acct["positions"]
               if p["id"] not in before and p["market"] == MARKET and p["leverage"] == LEVERAGE]
        if len(new) >= 2:
            bevo.state.pop("opening")
            bevo.state["legs"] = new[:2]
            bevo.state["one_sided"] = 0
            bevo.log(f"cycle {cycles + 1} open: {', '.join(new)}")
        elif waited >= WAIT:
            bevo.state.pop("opening")
            # Papertrade's open-interest cap filling between the room check and the open
            # is not a fault: close what opened and wait for room, without counting it.
            one_sided = bevo.state.get("one_sided", 0) + (0 if bevo.state.pop("oi_full", False) else 1)
            bevo.state["one_sided"] = one_sided
            bevo.log(f"only {len(new)} of 2 legs opened ({one_sided} in a row)")
            if one_sided >= 3:
                stop_with("Papertrade opened only part of a cycle three times in a row", new)
            elif new:
                close(new, "part of a cycle")
                bevo.state["closing"] = new
        continue

    # A cycle is open: close every leg at the move, or the rest if one was wiped out.
    if "legs" in bevo.state:
        ids = bevo.state["legs"]
        legs = [open_by_id[i] for i in ids if i in open_by_id]
        entry = sum(p["entryPrice"] for p in legs) / len(legs) if legs else 0
        mark = next((p["markPrice"] for p in legs if p["markPrice"]), None)
        moved = abs(mark - entry) / entry if mark and entry else 0
        bevo.status("open", moved=round(moved * 100, 2), paper=round(paper), spent=round(max(0.0, -pnl), 2))
        if len(legs) == len(ids) and moved < MOVE:
            continue
        if legs and not close([p["id"] for p in legs], "move" if len(legs) == len(ids) else "a leg was wiped out"):
            continue
        bevo.state.pop("legs")
        bevo.state["closing"] = ids
        continue

    # Nothing open: stop once the budget is spent, or open the next cycle.
    if -pnl >= BUDGET:
        finish(f"your {BUDGET:,.2f} USD budget is spent")
    if acct["availableUsd"] < 2 * MARGIN:
        finish(f"{acct['availableUsd']:,.2f} USD is left, under the {2 * MARGIN:,.2f} a cycle holds")
    if waited < WAIT:
        continue
    # Papertrade caps open interest per side. Open only when both legs fit, and the
    # tighter side first, so a refusal leaves nothing open.
    market = next((m for m in (helper("markets") or {}).get("markets", []) if m["symbol"] == MARKET), None)
    if market is None:
        continue
    # Unknown room (no price) tries the open; Papertrade refuses it if the cap is full.
    room = {side: market[side + "RoomUsd"] for side in ("long", "short")}
    room = {side: float("inf") if usd is None else usd for side, usd in room.items()}
    full = [side + "s" for side in room if room[side] < MARGIN * LEVERAGE]
    if full:
        if not bevo.state.get("told_full"):
            bevo.notify(f"Papertrade is full on {MARKET} {' and '.join(full)} right now, so your farm is waiting. "
                        "It starts the next cycle by itself once both sides have room.", push="Farm waiting for room")
            bevo.state["told_full"] = True
        bevo.status("full", side=" and ".join(full))
        continue
    bevo.state["told_full"] = False
    bevo.state.pop("oi_full", None)
    bevo.state["opening"] = list(open_by_id)
    bevo.state["sent_at"] = time.time()
    base = ["--owner", owner, "--market", MARKET, "--margin", str(MARGIN), "--leverage", str(LEVERAGE)]
    for side in sorted(room, key=room.get):
        if not request(f"open {side}", "open", *base, "--side", side):
            bevo.log(f"{side} refused; the rest are closed once they show")
            break
    bevo.status("opening", cycle=cycles + 1, paper=round(paper))
```

Its settings: `PAPERTRADE_HELPER`, `MARKET`, `MARGIN_USD`, `LEVERAGE`, `MOVE_PCT` and
`BUDGET_USD`.
