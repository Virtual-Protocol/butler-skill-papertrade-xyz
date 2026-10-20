# Reading the Papertrade account

`python3 /tmp/papertrade.py account --owner <OWNER>` is the one read for balance,
positions, funding and the session key. Relay its figures; never work one out.

## Fields

| Field | Means |
| --- | --- |
| `availableUsd` | USDC free to open with or withdraw. Margin in open positions is not in it |
| `positions[]` | each open position, below |
| `depositAddress` | the owner's own Papertrade deposit address, for `--recipient` in the deposit step. Only USDC arriving on Hyperliquid's ledger (`--chain-out 1337`) is credited |
| `pendingDepositUsd` | USDC sitting at the deposit address, not yet credited. It is credited once the total there reaches 10; until then it counts toward the next deposit (`deposit-plan`) |
| `hyperCoreAccount` | whether the owner already has a Hyperliquid account; without one the first withdrawal pays 1 USDC |
| `withdrawActivationFeeUsd` | `0` or `1`: the one-time fee Papertrade takes on top of a first withdrawal when the owner has no Hyperliquid account yet |
| `maxWithdrawUsd` | the most a withdrawal can ask for now: `availableUsd` less the activation fee when one is owed. Under 10 means nothing can be withdrawn yet |
| `withdrawNote` | set only when nothing can be withdrawn: the sentence to say, word for word. `null` otherwise |
| `paper` | `balance` (PAPER in the wallet), `staked` (PAPER staked) and `rewardsUsd` (USDC rewards ready to claim), or `null` when they could not be read. Details and limits: `staking` (`references/staking.md`) |
| `sessionKey.action` | `ready`, `renew`, `register` or `key-new` (`references/session-key.md`); `sessionKey.expiresIn` says how long is left |

### A position

| Field | Means |
| --- | --- |
| `id` | what `close --ids` takes |
| `market`, `side` | `BTC` / `ETH`, `long` / `short` |
| `marginUsd` | the owner's money in it, all of which a liquidation takes |
| `leverage`, `positionUsd` | margin x leverage; say the dollar size, not just the multiple |
| `entryPrice` | Hyperliquid's mid price when it opened |
| `markPrice` | Hyperliquid's mid now |
| `pnlUsdBeforeFees` | an estimate at `markPrice`. A winning close pays a small haircut and 2% of the gain, so the real figure is a little lower; say "about" |
| `wipedOutAtMovePct` | the move against the position at which the whole margin is gone |

`markPrice` and `pnlUsdBeforeFees` are `null` when Hyperliquid's price could not be
read: say the value is unknown, never zero.

## Closed positions and PnL

`python3 /tmp/papertrade.py history --owner <OWNER> [--limit 20]` lists closed positions,
newest first (at most 200), from Papertrade's own history. Each figure is computed the way
Papertrade's app computes it; relay them, never recompute or add them up.

| Field | Means |
| --- | --- |
| `outcome` | `closed` (the owner or Butler closed it) or `liquidated` |
| `pnlUsd` | the result: Papertrade's adjusted PnL less the fee paid; a liquidation is minus the whole margin |
| `pnlPct` | `pnlUsd` as a share of the margin |
| `feeUsd` | the fee taken from a winning close (2% of the gain) |
| `entryPrice`, `exitPrice`, `marginUsd`, `leverage`, `positionUsd` | as on the open position |
| `openedAt`, `closedAt`, `heldFor` | when, in UTC, and for how long |
| `paperMinted` | PAPER minted to the owner from a loss |

`summary` totals the trades returned: `count`, `wins`, `losses`, `liquidated`,
`totalPnlUsd`, `totalFeesUsd`. When `more` is true, `summary.covers` says it is only the
newest ones. Say so, and raise `--limit` if the owner asked about everything.

`python3 /tmp/papertrade.py cashflows --owner <OWNER>` lists deposits and withdrawals.
A deposit's `status` is `credited`. A withdrawal moves through `signed`, `submitted` and
`in_transit` to `settled`, its end, or `failed`. `needs_signature` means it needs a new
card.

## An unreadable account

The helper exits `1` with `error: ...` when Papertrade or HyperEVM does not answer. That is
not an empty account: say Butler cannot see it now, and file nothing.
