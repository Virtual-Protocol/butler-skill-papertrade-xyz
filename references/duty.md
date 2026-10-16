# Papertrade from a duty

A duty can read the account and close (or open) with the same session key the chat uses,
with no card: the key signs. It cannot make a key, renew one, withdraw or file any owner
card. Those need the owner, so they happen in a chat; the helper refuses them in a duty.

## Filing one, from a chat

1. Run `SKILL.md` step 1 as always, and check `sessionKey.action` is `ready`. A duty
   filed on a key that is not usable closes nothing.
2. Get the path the duty runs:

   ```sh
   python3 /tmp/papertrade.py duty-helper --owner <OWNER>
   ```

   `helper` is a copy of the helper beside the key (`~/.papertrade/papertrade.py`). Every
   chat run keeps it current. A duty's HOME is its own folder, so the copy is what finds
   the key; never have a duty extract its own.
3. File the duty with a `timer` trigger (60 seconds is enough) and its settings in
   `PARAMS`: `PAPERTRADE_HELPER` (the `helper` path), the position id from this turn's
   `positions`, and the owner's figures. Before filing, tell the owner two things in
   plain words:
   - it checks once a minute against the price `account` reads, before fees;
   - at high leverage a fast move can liquidate the position before a check sees it.

## What the duty does

- Read the owner with `bevo.read("/me")["user"]["agentWalletAddress"]`.
- Run `python3 PARAMS["PAPERTRADE_HELPER"] <command> --owner <owner>`, and send the
  `bodyFile` a build prints with the same `curl` as `SKILL.md`, once.
- When `sessionKey.action` is not `ready`, notify the owner once (`bevo.notify`) and send
  nothing until it is `ready` again. `renew` still closes.
- After a `201`, build nothing more for that position for two minutes: a close lands in
  seconds, and the next tick sees it gone.
- Once the position is gone, finish with `bevo.done()`.
- Open only on terms the owner set when filing (market, side, margin, leverage, each in
  `PARAMS`), with the bad case said to them then: a duty asks no one before it opens.

## A stop-loss and take-profit duty

Closes one position when its PnL before fees reaches `-STOP_LOSS_USD` or
`TAKE_PROFIT_USD`. Tested against Papertrade with the duty SDK.

```python
import json
import os
import subprocess
import time

import bevo

PARAMS = json.loads(os.environ.get("PARAMS") or "{}")
INTENTS = "https://exchange.papertrade.xyz/intents"


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


owner = bevo.read("/me")["user"]["agentWalletAddress"]
position_id = str(PARAMS["POSITION_ID"])
for tick in bevo.ticks():
    acct = helper("account", "--owner", owner)
    if acct is None:
        continue
    key = acct["sessionKey"]
    if key["action"] != "ready" and not bevo.state.get("told_key"):
        bevo.notify("Your Papertrade session key needs renewing. Ask me about Papertrade in a chat "
                    "to approve it; until then I cannot close this position.", push="Renew Papertrade key")
        bevo.state["told_key"] = True
    if key["action"] not in ("ready", "renew"):
        continue
    position = next((p for p in acct["positions"] if p["id"] == position_id), None)
    if position is None:
        bevo.done(f"Your Papertrade position {position_id} is closed; nothing left to watch.")
    pnl = position["pnlUsdBeforeFees"]
    if pnl is None:
        continue
    hit = pnl <= -PARAMS["STOP_LOSS_USD"] or pnl >= PARAMS["TAKE_PROFIT_USD"]
    if not hit or time.time() - bevo.state.get("sent_at", 0) < 120:
        continue
    built = helper("close", "--owner", owner, "--ids", position_id)
    if built is None:
        continue
    status, answer = send(built["bodyFile"])
    bevo.state["sent_at"] = time.time()
    bevo.log(f"close {position_id} at {pnl:+.2f}: {status} {answer}")
    if status == "201":
        bevo.notify(f"Closing your Papertrade {position['market']} {position['side']} at "
                    f"{pnl:+.2f} USD before fees.", push="Papertrade close sent")
```

Its settings: `PAPERTRADE_HELPER`, `POSITION_ID`, `STOP_LOSS_USD` and `TAKE_PROFIT_USD`.
