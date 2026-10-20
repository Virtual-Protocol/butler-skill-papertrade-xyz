# Changelog

## 1.2.0

- **Papertrade's open-interest cap.** `markets` reports `longRoomUsd` and `shortRoomUsd`,
  the room left under each side's cap, in dollars: Papertrade counts the cap in coins, so
  the helper prices it at the Hyperliquid mid. `farm-quote` warns when a leg does not fit. The
  duty opens only when both legs fit, the tighter side first, and otherwise waits with one
  note ("Papertrade is full on BTC longs right now, so your farm is waiting"). A cap that
  fills between the check and the open (`admission_rejected`, `openInterest`) is not
  counted as a failure. Found live: BTC and ETH longs were both over their caps.
- The duty files with a `statusTemplate` (lines of 46 characters at most) and a 28-character
  title, as the Duties list requires; the Butler no longer rewrites the duty to fit.
- **One farm per market.** The Butler reads the owner's duties first and shows a running
  farm on that market instead of a new ticket; a second would take the first one's legs.
- `farm-quote` returns `breakEven` and `breakEvenUsdPerPaper`: the PAPER price the cycle
  only pays off above, said with "it buys PAPER with fees; it is not a return".
- **Farm PAPER, from a ticket.** "I want to farm PAPER" shows the owner a blank ticket of
  five fields: market, margin per leg, leverage, move per cycle and budget. Nothing is
  assumed, even when the owner asks the Butler to pick: they fill in every field, and the
  farm duty is filed only after that. `farm-quote` then says what one cycle costs and
  mints ("Each cycle costs $0.77 for 54 PAPER"), the cost per 1,000 PAPER, about how many
  cycles and how much PAPER the budget buys, and the bad case in dollars, before anything
  is filed (`references/farm.md`).
- **The cost is what the winning legs give back.** A winning leg is paid back about 10%
  less than it made (less still on small moves), then Papertrade's win fee (2% today, read
  live; `markets` now reports it as `winFeeRate`) comes off the rest; a loss costs nothing
  extra. `farm-quote` uses Papergainz' haircut model, which reproduces its published BTC
  cycle ($47,399.20 for 4,290,739 PAPER) to within rounding, plus the win fee that model
  leaves out. PAPER per $1 lost is read from the
  owner's own losing closes; with none yet it is unknown, never guessed.
- **The farm duty** opens a long and a short, closes both once price is `MOVE_PCT` from
  their average entry, notes each cycle in its thread without a push, and repeats until
  the owner says "stop farming" or its closed cycles have lost `BUDGET_USD`. It closes
  every farm leg and stops when price moves 1% inside a minute, and stops between cycles
  once the budget is spent or a cycle no longer fits. It never touches a position it did not open, closes the
  rest at once when a leg is wiped out, closes a part-opened cycle (three in a row and it
  stops), and retries a refused close every minute rather than giving up.
- **Measured:** a $1,000 BTC long closed at -0.22% lost $2.24, paid no fee and minted
  24.08 PAPER (about 10.95 per $1, after Papertrade's 2% carve). The duty is tested
  against a simulated Papertrade in ten cases.

## 1.1.0

- **From a duty:** a duty reads the account and closes (or opens) with the same session
  key, with no card: `duty-helper` gives the path it runs, a copy of the helper beside the
  key that every chat run keeps current. `references/duty.md` has a stop-loss and
  take-profit duty, tested against Papertrade. A duty never makes a key, renews one,
  withdraws or files an owner card; the helper refuses those there, and a key that is not
  usable makes a duty notify the owner rather than ask for a card.
- **One writer at a time.** A chat and a duty share the key file, so a nonce is taken and
  the file written under a lock, each write through its own temporary file. Without it,
  three processes racing on one file reused 12 of 450 nonces and lost 269 writes.

## 1.0.1

- **Fund before the key.** Papertrade refuses a session-key registration with `noDeposit`
  until the account has had a deposit, so a card filed earlier can only be refused and
  the owner approves it for nothing. `key-status` now answers `fund-first` for an account
  with no cashflow yet, files no card, and asks for the key once the deposit is credited.
  An unreadable cashflow history counts as funded, so the registration then meets
  Papertrade's own refusal rather than being skipped.
- **A full withdrawal is never refused for dust.** Papertrade's balance carries 18
  decimals and a withdrawal asks in USDC's 6; `availableUsd` and `maxWithdrawUsd` were
  rounded to the nearest, so a balance just under a cent boundary read a hair high and a
  withdrawal of all of it answered `funding`. Both now round down, and `withdraw-typed-data`
  checks the amount in whole USDC units.
- **The activation fee is said, and counted the way Papertrade counts it.** Step 8 tells
  the owner about the one-time 1 USDC fee before the card, and `maxWithdrawUsd` leaves it
  out. A past withdrawal is now read from `/funding`'s items, which are all withdrawals; the
  old check looked for a `kind` field those items do not have.

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
