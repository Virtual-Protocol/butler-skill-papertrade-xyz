import json
import os
import subprocess
import time

import bevo

PARAMS = json.loads(os.environ.get("PARAMS") or "{}")
MARKET = PARAMS["MARKET"]
MARGIN = float(PARAMS["MARGIN_USD"])
LEVERAGE = int(PARAMS["LEVERAGE"])
MOVE = float(PARAMS["MOVE_PCT"]) / 100
BUDGET = float(PARAMS["BUDGET_USD"])
STOP = PARAMS.get("STOP") is True
WAIT = 120
SPIKE = 0.01


def helper(*args):
    run = subprocess.run(["python3", PARAMS["PAPERTRADE_HELPER"], *args],
                         capture_output=True, text=True, timeout=120, check=False)
    if run.returncode != 0:
        bevo.log(f"papertrade {args[0]}: {run.stderr.strip()}")
        return None
    return json.loads(run.stdout)


def request(what, *args):
    """Build one intent and send it once. True when Papertrade accepted it."""
    built = helper(*args)
    if built is None:
        return False
    sent = helper("send", "--body-file", built["bodyFile"]) or {"status": "no answer", "answer": ""}
    status, answer = sent["status"], sent["answer"]
    bevo.log(f"{what}: {status} {answer}")
    if status != "201" and "openInterest" in answer:
        bevo.state["oi_full"] = True
    if status != "201" and "noOpenPositions" in answer:
        bevo.state["close_queued"] = True
    return status == "201"


def close(ids, why):
    """Send a close. A refusal is retried next minute, never given up on: failing the run
    would pause the duty with its legs still open."""
    bevo.state.pop("close_queued", None)
    accepted = request(f"close {','.join(ids)} ({why})", "close", "--owner", owner, "--ids", ",".join(ids))
    # Papertrade answers noOpenPositions to a close of legs an earlier accepted close is
    # still queued for (live: it held one for 20 minutes). That close is still coming, so
    # it is no refusal: wait for it, without counting a try or telling the owner.
    if accepted or bevo.state.pop("close_queued", False):
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

    # The owner's stop arrives as STOP, a settings update that restarts this program with
    # its state kept. The farm closes its own legs: only it knows which they are, and a
    # paused farm cannot close anything.
    if STOP and not bevo.state.get("stop"):
        if "opening" in bevo.state and len(mine) < 2 and waited < WAIT:
            bevo.status("stopping")
            continue  # the cycle's legs are still landing; close them once they show
        if "closing" in bevo.state:
            bevo.state["stop"] = "you asked to stop"
        else:
            stop_with("you asked to stop", mine)
            bevo.status("stopping")
            continue

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
            if bevo.state.get("stop"):
                bevo.status("stopping")
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
        bevo.status("waiting", side=" and ".join(full))
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
