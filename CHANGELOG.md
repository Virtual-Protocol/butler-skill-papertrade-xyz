# Changelog

## 1.0.0

First release: trade BTC and ETH perpetuals on Papertrade (papertrade.xyz).

**What it does**

- **Look:** balance and open positions; `account` reads the chain directly.
- **Fund:** `deposit-plan`, then `acp trade --chain-out 1337 --recipient <deposit address>`.
  The plan counts what already waits at the deposit address, the one-time 1 USDC fee to
  open its HyperCore account, and a 1 USDC bridge margin, never under the trading bot's
  5 USDC floor. It refuses an amount that would sit uncredited, and `account` reports
  `pendingDepositUsd`.
- **Open:** `quote` first, which signs nothing and supplies `badCase`. Then `open`, signed
  by a session key, and a `curl` to Papertrade's relayer.
- **Close:** with no card, so a close is never delayed.
- **Withdraw:** `WithdrawToCore`, signed by the owner through `acp wallet sign-typed-data`
  (an approval card), to the owner's own Hyperliquid account. It counts as done at
  `cashflows` `settled`.
- **History:** `history` lists closed positions with PnL exactly as Papertrade's app
  computes it: the adjusted PnL less the fee, and minus the margin for a liquidation.
  `cashflows` lists deposits and withdrawals. Both follow `nextCursor`, and a repeated
  cursor is reported as incomplete.

**Design, and why**

- **A session key signs opens and closes.** Papertrade refuses an owner-signed trade
  (`403 unauthorized_intent`, measured). The key cannot withdraw. It lives in
  `~/.papertrade/session-key.json`, outside the skill directory that `hub_update`
  replaces, and is never printed.
- **Renewal a day ahead, on every read.** It needs an owner card. Re-registering the same
  key extends it a full 30 days (measured), so a second key is never made.
- **The helper is extracted with `awk`, never retyped.** That saves about 8k output tokens
  a turn, and keeps the code byte-identical to the tested script.
- **Every build writes its own files** (`/tmp/pt-<id>-*.json`), so two conversations never
  send each other's request.
- **The helper writes the sentences smaller models got wrong in testing:**
  - `badCase`, from `quote`;
  - `withdrawNote`, when nothing can be withdrawn;
  - `sessionKey.todo`, when the key needs an owner card;
  - `deposit-plan`'s `why`;
  - owner cards' `--reading`.
- **A card exists only once `bevo-read request` finds it.** In tests an agent claimed
  cards it never filed.
- **"Accepted but not landed"** (`intents --intent`): a `201` that never appears is
  reported as still queued or as did-not-go-through, and is never re-sent.
- **Papertrade's contract address is read from its app** and refused unless the chain
  agrees, both the session-key manager and the EIP-712 domain.
