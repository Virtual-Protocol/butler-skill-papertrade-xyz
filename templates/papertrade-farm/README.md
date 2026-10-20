Farms PAPER on Papertrade. PAPER is minted when a position closes at a loss, so the duty
holds a long and a short of the same size on one market at once: one leg's loss is the
other's gain, and a cycle costs only what Papertrade keeps back from the winning leg.

```text
open a long + a short → price moves ±MOVE_PCT → close both → note the cycle → again
```

It checks once a minute, on the owner's Papertrade account, with the owner's session key.
It signs and sends through the Papertrade skill's helper at `PAPERTRADE_HELPER`, so a duty
filed from this template needs that skill installed and its key `ready`.

| Setting | Meaning |
| --- | --- |
| `PAPERTRADE_HELPER` | the path `papertrade.py duty-helper` returned |
| `MARKET` | `BTC` or `ETH` |
| `MARGIN_USD` | margin per leg in USD; a cycle holds twice this |
| `LEVERAGE` | each leg's leverage; the losing leg is wiped out at about (100 / LEVERAGE)% |
| `MOVE_PCT` | the price move in percent, either way from the legs' average entry, that closes both |
| `BUDGET_USD` | what the closed cycles may lose in all; the farm stops once that is spent |

Each closed cycle lands in the duty's thread with its PnL and PAPER, with no push.

## When it stops

- The closed cycles have lost `BUDGET_USD`. It checks between cycles, so the last cycle
  can take it a little past; a wiped-out leg, up to that leg's margin past.
- A cycle no longer fits in `availableUsd` (twice `MARGIN_USD`).
- The price moved 1% or more inside a minute: it closes every farm leg first.
- Papertrade opened only part of a cycle three times in a row.

## What it will not do

- **Touch a position it did not open.** Only legs it opened on `MARKET` at `LEVERAGE`.
- **Open into a full side.** Papertrade caps open interest per side. It opens only when
  both legs fit, the tighter side first, and otherwise waits with one note to the owner.
- **Give up on a close.** A refused close is sent again every minute, with one note to
  the owner after five.
- **Trade without a ready key.** It notes the owner once and sends nothing until the key
  is `ready` again; a key due to `renew` still trades.
- **Pick its own settings.** Every figure comes from the settings; there is no default.
