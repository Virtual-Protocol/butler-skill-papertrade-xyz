# Reading the Papertrade account

`python3 /tmp/papertrade.py account --owner <OWNER>` is the one read for balance,
positions, funding and the session key. Relay its figures; never work one out.

## Fields

| Field | Means |
| --- | --- |
| `availableUsd` | USDC free to open with or withdraw. Margin in open positions is not in it |
| `positions[]` | each open position, below |
| `depositAddress` | the owner's own Papertrade deposit address, for `--recipient` in the deposit step. Only USDC arriving on Hyperliquid's ledger (`--chain-out 1337`) is credited |
| `hyperCoreAccount` | whether the owner already has a Hyperliquid account; without one the first withdrawal pays 1 USDC |
| `withdrawActivationFeeUsd` | `0` or `1` |
| `maxWithdrawUsd` | the most a withdrawal can ask for now. Under 10 means nothing can be withdrawn yet |
| `withdrawNote` | set only when nothing can be withdrawn: the sentence to say, word for word. `null` otherwise |
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

## An unreadable account

The helper exits `1` with `error: ...` when Papertrade or HyperEVM does not answer. That is
not an empty account: say Butler cannot see it now, and file nothing.
