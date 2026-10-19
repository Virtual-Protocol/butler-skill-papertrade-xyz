# Changelog

## 1.2.0

- **PAPER staking.** Stake PAPER, unstake it, and claim its USDC rewards into the
  Papertrade balance (`references/staking.md`). Each is the owner's signature through an
  approval card, signed under PaperStaking's own EIP-712 domain: Papertrade lets no
  session key sign them. `staking` reads the wallet's PAPER, the stake, the rewards and
  the minimum stake, and says in `stakeNote`, `unstakeNote` or `claimNote` why an action
  cannot run, so no card is filed only to be refused. `account` shows the same figures in
  `paper`. Measured against Papertrade from a wallet with no
  PAPER: each request reached its balance check (`paperBalance`, `stakedBalance`,
  `noRewards`, `below_minimum_paper_stake`), and one signed under the wrong domain was
  refused as `unauthorized_intent`.
- **One step for owner cards.** Step 8 now covers a withdrawal and the three staking
  actions alike: `<OP>-typed-data`, the card, `<OP>-body`. The helper prints each card's
  `purpose`, the withdrawal's included, so the model never types an amount into it.
- **A withdrawal card shows every digit.** Its reading printed the amount with six
  significant digits, so 12,345.67 USDC read as 12345.7.
- **Staking never stops trading.** PaperStaking's address is checked on-chain like the
  Exchange's. If that fails, only the staking commands refuse; opens and closes go on.
- **Its own nonces.** PaperStaking does not share the session key's nonces; the helper
  takes the contract's next unused one, and never hands the same one out twice.
- **Rewards are not promised.** `references/staking.md` says when rewards dry up: the
  pool's overflow reaches stakers only while it is above its cap, which Papertrade can
  change, and no fees reach them while winners are queued. No APR, no cap figure.
- **`history` past 75 trades works.** Papertrade answers 400 unless the cursor comes
  before `limit` in the query, so every second page failed; `cashflows` too.

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
