# Farming PAPER

Papertrade mints PAPER when a position closes at a loss. A farm holds longs and shorts of
the same size on one market at once, so one side's loss is the other side's gain: the
losing legs mint PAPER, and the cycle costs what Papertrade keeps back from the winning
legs. A duty runs the cycles, so the owner fills in one ticket and approves it once:

```text
open N longs + N shorts → price moves ±MOVE_PCT → close all → note the cycle → again
```

**The cost is the haircut on the winning legs, not a small fee.** A winning leg is paid
back about 10% less than it made, and much less on small moves; Papertrade takes nothing
from a loss. On BTC a 1% cycle keeps about 88% of the win, a 0.3% cycle about 84%. So a
cycle costs about $1.20 per $1,000 leg at 1%, and $0.48 at 0.3%. `farm-quote` works it
out; never do the arithmetic yourself.

## The ticket

"I want to farm PAPER" means a farm duty. Never assume a setting: no leverage, size, move
or stop is the owner's until they say it. Show the ticket with every field blank, its
limits beside it, and this turn's `availableUsd`, and ask them to fill it in:

```text
Farm ticket — Papertrade (you have $<availableUsd>)
  Market             ___     BTC or ETH
  Margin per leg     $___    at least $10, and margin x leverage at least $1,000
  Pairs per cycle    ___     1 to 6; each pair is a long and a short
  Leverage           ___x    the losing leg is wiped out at about a (100 / leverage)% move
  Move per cycle     ±___%   both legs close once price moves this far, either way
  Trigger stop       $___    stop, and close everything, under this balance
  Hour limit         ___     stop after this many hours
  Max cycles         ___     a number, or "no limit"
```

Ask again for only the fields still blank, showing what they have filled. "You pick",
"default" or "go" is not a value: say each blank needs their number. Never suggest a
leverage higher than one they named. A field they gave earlier in the conversation
counts once you repeat it back in the ticket.

Then quote it. It signs nothing, refuses settings that cannot work (and says which value
to change), and works out the cycle:

```sh
python3 /tmp/papertrade.py farm-quote --owner <OWNER> --market <MARKET> --margin <USD> --leverage <N> --move <PCT> --pairs <N> --stop-below <USD> --hours <H> --max-cycles <N>
```

Quote only once every field has their value. A refusal is said as written, and the ticket
shown again with that field marked for them to change.
Otherwise say, from its fields only:

> **{badCase}**
>
> **{summary}** That is {costPer1kPaperUsd} per 1,000 PAPER. The losing leg pays
> {losingLegsPayUsd}; the winning leg keeps {winningLegsKeepUsd} ({winningKeepsPct}%).
>
> BTC is at {markPrice}; this cycle closes at {exitDownPrice} or {exitUpPrice}. At your
> stop of {stopBelowUsd}, that is about {cyclesBeforeStop} cycles and {paperBeforeStop}
> PAPER, unless the hour limit comes first. The farm also stops by itself if BTC moves 1%
> inside a minute. Start it?

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

3. File the duty below with a `timer` trigger every 60 seconds, and in `PARAMS`, as
   numbers: `PAPERTRADE_HELPER` (the `helper` path), `MARKET`, `MARGIN_USD`, `LEVERAGE`,
   `MOVE_PCT`, `PAIRS`, `STOP_BELOW_USD`, `HOUR_LIMIT` and `MAX_CYCLES` (0 for none),
   exactly as quoted. Title it after the ticket, such as "Farm PAPER: BTC $10 x 100x
   ±0.5%".
4. Tell them it is running, that each cycle lands in its thread with what it cost and
   minted, and that "stop farming" ends it.

## While it runs

- **"How's my farm?"** Read the duty's status and log, then `history`. The log has one
  `cycle` line per closed cycle with its PnL and PAPER.
- **"Stop farming."** Pause the duty first, so it opens nothing more, then read `account`.
  The farm's legs are the positions on its `MARKET` at its `MARGIN_USD` and `LEVERAGE`:
  say their PnL before fees and close them all in one `close --ids` (`SKILL.md` step 7).
  If the owner holds other positions of that shape, ask which first.
- **A change** ("make it ETH", "bigger"): stop it as above, show the ticket with the new
  values, quote it, and file a new farm once they agree.

## What the duty does

Each minute it reads `account`, then:

- **Stops** (closing every farm leg first) at the hour limit, when the balance (available
  plus the farm legs' margin and PnL) is at or under `STOP_BELOW_USD`, or when the price
  moved 1% or more since the last minute. With nothing open it also stops at
  `MAX_CYCLES`, or when a cycle no longer fits in `availableUsd`.
- **Opens** a cycle when none is open: `PAIRS` longs, then `PAIRS` shorts.
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
PAIRS = int(PARAMS["PAIRS"])
STOP_BELOW = float(PARAMS["STOP_BELOW_USD"])
HOUR_LIMIT = float(PARAMS["HOUR_LIMIT"])
MAX_CYCLES = int(PARAMS.get("MAX_CYCLES") or 0)
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
              f"{pnl:+.2f} USD after fees.")


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
if "started_at" not in bevo.state:
    bevo.state["started_at"] = time.time()
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

    # Limits that stop the farm even mid-cycle: they close every farm leg first.
    if not bevo.state.get("stop"):
        balance = acct["availableUsd"] + sum(open_by_id[i]["marginUsd"] + (open_by_id[i]["pnlUsdBeforeFees"] or 0)
                                             for i in mine)
        marks = [open_by_id[i]["markPrice"] for i in mine if open_by_id[i]["markPrice"]]
        last = bevo.state.get("last_mark")
        reason = None
        if time.time() - bevo.state["started_at"] >= HOUR_LIMIT * 3600:
            reason = f"the {HOUR_LIMIT:g}-hour limit was reached"
        elif balance <= STOP_BELOW:
            reason = f"the balance is {balance:,.2f} USD, at or under your stop of {STOP_BELOW:,.2f}"
        elif marks and last and abs(marks[0] - last) / last >= SPIKE:
            reason = f"{MARKET} moved 1% or more inside a minute (safety stop)"
        bevo.state["last_mark"] = marks[0] if marks else None
        if reason:
            stop_with(reason, mine)
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
        if len(new) >= 2 * PAIRS:
            bevo.state.pop("opening")
            bevo.state["legs"] = new[:2 * PAIRS]
            bevo.state["one_sided"] = 0
            bevo.log(f"cycle {cycles + 1} open: {', '.join(new)}")
        elif waited >= WAIT:
            bevo.state.pop("opening")
            one_sided = bevo.state.get("one_sided", 0) + 1
            bevo.state["one_sided"] = one_sided
            bevo.log(f"only {len(new)} of {2 * PAIRS} legs opened ({one_sided} in a row)")
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
        bevo.status(f"Cycle {cycles + 1} open · {moved * 100:.2f}% of ±{MOVE * 100:.2f}% · {paper:,.0f} PAPER so far")
        if len(legs) == len(ids) and moved < MOVE:
            continue
        if legs and not close([p["id"] for p in legs], "move" if len(legs) == len(ids) else "a leg was wiped out"):
            continue
        bevo.state.pop("legs")
        bevo.state["closing"] = ids
        continue

    # Nothing open: stop at a limit, or open the next cycle.
    if MAX_CYCLES and cycles >= MAX_CYCLES:
        finish(f"it ran the {MAX_CYCLES} cycles you set")
    if acct["availableUsd"] < 2 * PAIRS * MARGIN:
        finish(f"{acct['availableUsd']:,.2f} USD is left, under the {2 * PAIRS * MARGIN:,.2f} a cycle holds")
    if waited < WAIT:
        continue
    bevo.state["opening"] = list(open_by_id)
    bevo.state["sent_at"] = time.time()
    base = ["--owner", owner, "--market", MARKET, "--margin", str(MARGIN), "--leverage", str(LEVERAGE)]
    for side in ["long"] * PAIRS + ["short"] * PAIRS:
        if not request(f"open {side}", "open", *base, "--side", side):
            bevo.log(f"{side} refused; the rest are closed once they show")
            break
    bevo.status(f"Opening cycle {cycles + 1} · {paper:,.0f} PAPER so far")
```

Its settings: `PAPERTRADE_HELPER`, `MARKET`, `MARGIN_USD`, `LEVERAGE`, `MOVE_PCT`, `PAIRS`,
`STOP_BELOW_USD`, `HOUR_LIMIT` and `MAX_CYCLES`.
