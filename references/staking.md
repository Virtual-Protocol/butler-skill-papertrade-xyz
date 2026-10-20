# Staking PAPER

PAPER is Papertrade's own token. It is minted to the owner's wallet when they close a trade
at a loss or are liquidated (`paperMinted` in `history`), and it cannot be sent to another
wallet. Staked, it earns a share of Papertrade's trading fees, paid in USDC. Stake and
unstake take effect at once, with no lockup and no cooldown.

All three actions are signed by the owner's wallet, each through its own approval card
(`SKILL.md` step 8). The session key cannot sign any of them, and a duty never files one.

## Reading it

`python3 /tmp/papertrade.py staking --owner <OWNER>` reads the chain directly. Relay its
figures; never work one out.

| Field | Means |
| --- | --- |
| `paperBalance` | PAPER in the owner's wallet: what can be staked |
| `stakedPaper` | PAPER staked: what can be unstaked |
| `rewardsUsd` | USDC earned and ready to claim, rounded down |
| `shareOfStakedPct` | the owner's share of all staked PAPER, which is their share of each distribution |
| `minimumStakePaper` | the least Papertrade takes in one stake |
| `stakeNote`, `unstakeNote`, `claimNote` | set only when that action cannot run now: the sentence to say, word for word. `null` otherwise |

`account` carries the same three figures in `paper`, so a balance question can mention them.

## The three actions

| Owner says | `<OP>` | Does |
| --- | --- | --- |
| "stake my PAPER" | `stake` | moves PAPER from the wallet into staking. `--amount` in PAPER, or `all` |
| "unstake", "take my PAPER out" | `unstake` | moves staked PAPER back to the wallet. Rewards already earned stay claimable. `--amount` in PAPER, or `all` |
| "claim my rewards" | `claim` | moves the USDC rewards into the Papertrade balance (`availableUsd`), from where they can be withdrawn (`SKILL.md` step 8). No `--amount`: it claims all of it |

Before the card, say what it does in their words:

- Stake: "This stakes 5,000 PAPER. It earns a share of Papertrade's fees in USDC, and you
  can unstake it any time."
- Unstake: "This returns 5,000 PAPER to your wallet. It stops earning, and the USDC it
  already earned stays yours to claim."
- Claim: "This moves about 52.71 USDC of rewards into your Papertrade balance."

"About" for a claim: rewards keep arriving, and the claim takes whatever is there when it
lands.

When a `-typed-data` command refuses, say its reason as written and file nothing. It makes
the checks Papertrade makes, so a card is never filed only to be refused. Never offer a
different amount; ask.

## Done

A `201` is queued, not done. Read `staking` until it shows the change: `stakedPaper` up or
down, or `rewardsUsd` back near zero with `availableUsd` in `account` higher. Not there
after half a minute: "Accepted but not landed" in `SKILL.md`.

## Rewards

Rewards come from two places:

- **A fee share:** half of every 2% fee, from a winning close's gain and from the pool's
  gain on a losing close or a liquidation.
- **The pool's overflow:** once the pool is above its staker cap, every further dollar it
  gains goes to stakers. Papertrade sets the cap and can change it (it has been $5M, with a
  raise to $10M queued), so never quote a figure for it.

The overflow comes only while the pool sits above its cap. Below it, stakers get the fee
share alone, which is far smaller. While winners wait in
Papertrade's payout queue, no fees are paid to stakers at all. So rewards swing a lot
from day to day and can stop for a while: never promise an amount or a rate. PAPER has no
price, so there is no APR; never quote one.

Papertrade distributes rewards by itself; the owner never has to. Each distribution is
split by staked PAPER at that moment: no tiers, boosts or lockups. `rewardsUsd` counts
only what is already distributed, so a stake earns nothing until the next distribution.
