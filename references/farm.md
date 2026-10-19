# Farming PAPER

Papertrade mints PAPER to an owner when a position closes at a loss. A farm holds a long
and a short of the same size on the same market at once, so one leg's loss is the other
leg's gain: the losing leg mints PAPER, and the pair costs only the fee on the winning
leg (2% of its gain). A duty runs the cycles, so the owner says one sentence and approves
one plan:

```text
open a long + a short → the price moves EXIT_MOVE_PCT → close both → report → again
```

Measured on 2026-10-19: a $1,000 BTC long closed at -0.22% lost $2.24, paid no fee, and
minted 24.08 PAPER, about 10.7 PAPER per dollar lost. The winning leg of the same move
pays about $0.045, so a cycle costs cents, not dollars. These are one trade's figures,
not a promise: never quote them to the owner as a rate.

## The plan

The owner gives a budget, the dollars the farm may hold in positions at once. Everything
else has a default; offer it, and change only what they ask to change.

| Setting | Default | Why |
| --- | --- | --- |
| `MARKET` | `BTC` | the deepest market; any `openable` symbol from `markets` |
| `MARGIN_USD` | 45% of the budget, rounded down to a whole dollar | one leg's margin. The pair holds 90% of the budget; the other 10% pays the winning legs' fees, so the next pair still fits |
| `LEVERAGE` | `25` when `MARGIN_USD` is at least 40, else `100` | Papertrade's $1,000 minimum position: 25x needs $40 a leg, 100x needs $10. So the smallest budget is $23 |
| `EXIT_MOVE_PCT` | `30 / LEVERAGE` (0.3 at 100x, 1.2 at 25x) | close well before a leg is wiped out at `100 / LEVERAGE`, since the duty looks once a minute |
| `MAX_LOSS_USD` | `MARGIN_USD` | stop once the farm's closed trades have lost this much in all |
| `MAX_CYCLES` | `0` (no limit) | stop after this many closed pairs |

Refuse the plan, and say which number is wrong, when:

- `MARGIN_USD` is under `minMarginUsd`, or `MARGIN_USD x LEVERAGE` is under `minPositionUsd`
  (`markets`);
- `2 x MARGIN_USD` is more than `availableUsd`;
- `EXIT_MOVE_PCT` is more than `40 / LEVERAGE`: a minute's move past the exit would then
  wipe out the losing leg before the duty sees it;
- `LEVERAGE` is more than `100`.

## Filing one, from a chat

1. Run `SKILL.md` step 1. The key must be `ready`; otherwise do step 2 first and file the
   farm only once it is.
2. Ask only for the budget, unless they already said it. "You pick" is not a budget: ask.
3. Get a quote for one leg with the plan's numbers. It signs nothing and gives the bad
   case for one leg:

   ```sh
   python3 /tmp/papertrade.py quote --owner <OWNER> --market <MARKET> --side long --margin <MARGIN_USD> --leverage <LEVERAGE>
   ```

4. Say the plan in one message, the bad case first, then ask for a yes:

   > **The bad case: you can lose $10 on one cycle.** If BTC jumps more than about 1% in
   > under a minute, one leg is wiped out, and if the price then comes back before I close
   > the other, its gain is gone too.
   >
   > The plan, from your $25: a $1,000 BTC long and a $1,000 BTC short, $10 each at 100x.
   > The other $5 pays the fees, so the next pair always fits.
   > When BTC moves 0.3% either way, I close both and open a new pair. The losing leg
   > mints PAPER; the winning leg pays 2% of its gain. I stop once the farm has lost $10
   > in all, or when you say "stop farming". Start it?

   The dollar figure in the bad case is `MARGIN_USD`, and "about 1%" is the quote's
   `wipedOutAtMovePct`. Their yes to this message, after you said it, is their yes to
   every pair the farm opens: a duty asks no one before it opens.
5. Get the path the duty runs (`references/duty.md`, step 2):

   ```sh
   python3 /tmp/papertrade.py duty-helper --owner <OWNER>
   ```

6. File the duty below with a `timer` trigger every 60 seconds, and in `PARAMS`:
   `PAPERTRADE_HELPER` (the `helper` path) and the plan's settings, as numbers. Title it
   after the plan, such as "Farm PAPER on BTC, $10 a leg at 100x".
7. Tell them it is running, that each closed pair lands in its thread with what it
   minted, and that "stop farming" ends it.

## While it runs

- **"How's my farm?"** Read the duty's status and log, then `history` for the figures. Its
  log has one `cycle` line per closed pair with that pair's PnL and PAPER minted.
- **"Stop farming."** Pause the duty first, so it opens nothing more. Then read `account`.
  The farm's open legs are the two positions on its `MARKET` with its `MARGIN_USD` and
  `LEVERAGE`; say their PnL before fees, and close both with one `close --ids` (`SKILL.md`
  step 7). If the owner holds other positions of the same shape, ask which ones first.
- **A change** ("make it ETH", "bigger"): pause it, close the open pair as above, and file
  a new farm with the new plan, said and agreed the same way.

## What the duty does

Each minute it reads `account` and does one thing:

- **No pair open:** stop if a limit is reached (`MAX_LOSS_USD`, `MAX_CYCLES`, or less than
  `2 x MARGIN_USD` available). Otherwise open the long, then the short.
- **Just opened:** find the two new positions. One leg alone after two minutes means
  Papertrade took only one: close it and stop, with the reason.
- **Pair open:** when either leg has moved `EXIT_MOVE_PCT`, close both in one request.
  When one leg is gone (wiped out), close the other at once: it holds the gain.
- **Pair closed:** read `history` for both ids, note the cycle (PnL, PAPER minted) in the
  duty's thread without a push, and count it.

It never touches a position it did not open. A key that is not `ready` gets one note and
no request until it is; `renew` still trades. After a request is accepted it waits two
minutes before sending another for the same pair.

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
EXIT = float(PARAMS["EXIT_MOVE_PCT"]) / 100
MAX_LOSS = float(PARAMS["MAX_LOSS_USD"])
MAX_CYCLES = int(PARAMS.get("MAX_CYCLES") or 0)
WAIT = 120


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
    if request(f"close {','.join(ids)} ({why})", "close", "--owner", owner, "--ids", ",".join(ids)):
        bevo.state["sent_at"] = time.time()
        return True
    bevo.fail(f"could not close {MARKET} position(s) {', '.join(ids)}; trying again next minute")
    return False


def totals():
    return bevo.state.get("cycles", 0), bevo.state.get("pnl", 0.0), bevo.state.get("paper", 0.0)


def finish(reason):
    cycles, pnl, paper = totals()
    bevo.done(f"Farm stopped: {reason}. {cycles} pair{'' if cycles == 1 else 's'} closed, {paper:.2f} PAPER minted, "
              f"{pnl:+.2f} USD after fees.")


def report(ids):
    """Count a closed pair once history has both legs; give up on the figures after 5 minutes."""
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
        line = f"Pair {cycles} closed; Papertrade's history does not show its figures yet."
    else:
        wiped = " One leg was wiped out." if any(t["outcome"] == "liquidated" for t in legs) else ""
        line = f"Pair {cycles} closed: {pnl:+.2f} USD, {paper:.2f} PAPER minted.{wiped}"
    bevo.log(f"cycle {cycles}: ids {','.join(ids)} pnl {pnl:+.4f} paper {paper:.4f}")
    bevo.notify(line, quiet=True)
    return True


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

    # A pair just closed: count it before anything else.
    if "closing" in bevo.state:
        ids = bevo.state["closing"]
        if any(i in open_by_id for i in ids):
            if waited >= WAIT:
                close([i for i in ids if i in open_by_id], "still open")
            continue
        if "closed_at" not in bevo.state:
            bevo.state["closed_at"] = time.time()
        if report(ids):
            bevo.state.pop("closing")
            bevo.state.pop("closed_at")
        continue

    # A pair just opened: find its two legs among the new positions.
    if "opening" in bevo.state:
        before = set(bevo.state["opening"])
        new = [p for p in acct["positions"]
               if p["id"] not in before and p["market"] == MARKET and p["leverage"] == LEVERAGE]
        long_ = next((p["id"] for p in new if p["side"] == "long"), None)
        short = next((p["id"] for p in new if p["side"] == "short"), None)
        if long_ and short:
            bevo.state.pop("opening")
            bevo.state["pair"] = [long_, short]
            bevo.log(f"pair open: long {long_}, short {short}")
        elif waited >= WAIT:
            lone = [i for i in (long_, short) if i]
            if lone and not close(lone, "half a pair"):
                continue
            bevo.state.pop("opening")
            if lone:
                bevo.state["closing"] = lone
            bevo.state["stop"] = ("Papertrade opened only one leg of the pair, so the farm closed it"
                                  if lone else "Papertrade did not open the pair")
        continue

    # A pair is open: close both on the exit move, or the survivor if one leg was wiped out.
    if "pair" in bevo.state:
        ids = bevo.state["pair"]
        legs = [open_by_id[i] for i in ids if i in open_by_id]
        moves = [abs(p["markPrice"] - p["entryPrice"]) / p["entryPrice"] for p in legs if p["markPrice"]]
        bevo.status(f"Pair {cycles + 1} open · {max(moves, default=0) * 100:.2f}% of {EXIT * 100:.2f}% · "
                    f"{paper:.2f} PAPER so far")
        if len(legs) == len(ids) and max(moves, default=0) < EXIT:
            continue
        if legs and not close([p["id"] for p in legs], "exit" if len(legs) == len(ids) else "other leg gone"):
            continue
        bevo.state.pop("pair")
        bevo.state["closing"] = ids
        continue

    # No pair: stop at a limit, or open the next one.
    if bevo.state.get("stop"):
        finish(bevo.state["stop"])
    if pnl <= -MAX_LOSS:
        finish(f"it has lost {-pnl:.2f} USD, the most you set ({MAX_LOSS:.2f})")
    if MAX_CYCLES and cycles >= MAX_CYCLES:
        finish(f"it ran the {MAX_CYCLES} pairs you set")
    if acct["availableUsd"] < 2 * MARGIN:
        finish(f"{acct['availableUsd']:.2f} USD is left, under the {2 * MARGIN:.2f} a pair needs")
    if waited < WAIT:
        continue
    bevo.state["opening"] = list(open_by_id)
    bevo.state["sent_at"] = time.time()
    base = ["--owner", owner, "--market", MARKET, "--margin", str(MARGIN), "--leverage", str(LEVERAGE)]
    if not request("open long", "open", *base, "--side", "long"):
        bevo.state.pop("opening")
        bevo.fail(f"Papertrade did not take the {MARKET} long; trying again in two minutes")
        continue
    if not request("open short", "open", *base, "--side", "short"):
        bevo.log("short refused; the long is closed once it shows")
    bevo.status(f"Opening pair {cycles + 1} · {paper:.2f} PAPER so far")
```

Its settings: `PAPERTRADE_HELPER`, `MARKET`, `MARGIN_USD`, `LEVERAGE`, `EXIT_MOVE_PCT`,
`MAX_LOSS_USD` and `MAX_CYCLES`.
