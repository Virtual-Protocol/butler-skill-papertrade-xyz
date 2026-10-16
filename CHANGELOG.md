# Changelog

## 0.2.0

- **Renewal a day ahead, on every read.** `sessionKey.action` is `renew` with under a day
  left, and the skill asks for the renewal whatever the owner asked about. A close should
  never be the first thing to find the key expired, because renewal waits on an approval
  card.
- **The same key is registered again; never a second one.** Measured: re-registering a
  live key moved its expiry forward a full 30 days. `key-new` now refuses whenever a key
  exists, and the skill never passes `--rotate`.
- **Every build writes its own files** (`/tmp/pt-<id>-body.json` and the rest) and prints
  their paths. Fixed `/tmp/pt_body.json` let two conversations building at once send
  each other's request.
- **The helper is extracted, never retyped:** step 1 runs `awk` over
  `references/helper.md`. That saves about 8k output tokens a turn, and a smaller model
  can no longer alter the code while copying it.
- **Owner cards carry a reading** (`--reading`) computed by the helper from the signed
  message: what the key can and cannot do, the amount and where a withdrawal goes.
- `curl` prints the HTTP status; closes say what to do when the key is not usable.
- **`quote` before every offer.** It runs every check an open makes and signs nothing. It
  gives the owner `badCase` word for word, `positionUsd` and `wipedOutNearPrice`. In
  tests, agents without it computed the bad case themselves, and `open` was the only
  command that printed it, after it had already signed.
- **"Accepted but not landed"** (`intents --intent`): a `201` that never shows up in
  `account` is checked against Papertrade's queue, so it is reported as still queued or
  as did-not-go-through, never re-sent or rebuilt by the agent alone.
- **The helper writes the sentences a model kept getting wrong:**
  - `withdrawNote`: when nothing can be withdrawn. Haiku offered "$9.72 now" against a $10
    minimum.
  - `sessionKey.todo`: whenever the key is not `ready`. Haiku told the owner to approve a
    renewal "when prompted" and filed no card.
- Step 1 runs before any reply, refusals included. Approving a key card is never a yes
  to a trade.

## 0.1.0

- First version: look, fund, open, close and withdraw on Papertrade's BTC and ETH
  perpetuals.
- A session key kept in `~/.papertrade/session-key.json` signs opens and closes. The owner's
  wallet signs registration and withdrawals through `acp wallet sign-typed-data`.
- Deposits go through `acp trade --chain-out 1337 --recipient <deposit address>`.
- The helper reads Papertrade's contract address from its app and refuses it unless the
  chain agrees.
