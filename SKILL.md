---
name: papertrade-xyz
description: Trade BTC and ETH perpetuals on Papertrade (papertrade.xyz) - fund the account, open a long or a short, close it, and withdraw - with a session key Butler keeps.
version: 1.0.1
metadata: {"butler":{"moneyMoving":true,"keywords":["papertrade","papertrade.xyz","synthetic perps","1000x","high leverage","long btc","short btc","long eth","short eth","papertrade position","close my papertrade","papertrade balance","withdraw from papertrade","deposit to papertrade"],"requires":{"bins":["python3","curl","cat","awk","bevo-read","acp"]}}}
---

## When to use

Your owner wants to act on **Papertrade**, a perpetuals exchange on Hyperliquid's HyperEVM
where every trade faces Papertrade's own pool at Hyperliquid's mid price:

- **Look** - "what's my Papertrade balance", "my positions": step 1, then stop.
- **History** - "how did my trades do", "my PnL": step 1, then `history`
  (`references/account.md`). Relay its figures; never add them up yourself.
- **Fund** - "put $50 into Papertrade": step 3.
- **Open** - "long BTC 100x with $20": steps 4 to 6 (`quote` first, always).
- **Close** - "close my BTC long": step 7. Never wait for anything to close.
- **Withdraw** - "take my money out of Papertrade": step 8.

Not this skill: Hyperliquid's own perps (`acp trade`), stop-loss or take-profit orders
(Papertrade has none), or a market `markets` does not list.

## Before you start

1. **Papertrade is not the owner's Hyperliquid perps.** Its balance and positions are only
   in this skill's reads.
2. **The bad case first, in their words, before anything else:** *"At 100x, a 1% move
   against you and the whole $20 is gone - there is no partial loss."* The figure is
   the `badCase` that `quote` prints; never compute one.
3. **Minimums are Papertrade's, not yours:** at least $10 margin and margin x leverage of
   at least $1,000. A small account therefore trades at high leverage; say so.
4. **Figures come only from this turn's reads.** An unreadable account is not an empty one.
5. **The session key file is never opened, printed or copied** - not to check it, not to
   help (`references/session-key.md`).

### Never open without all four

1. **They chose it:** market, long or short, margin and leverage, in their own words. "You
   pick" is not a choice: ask.
2. **They have it:** the margin is at most `availableUsd`.
3. **They said yes to the bad case,** with its dollar figure, after you said it. Approving
   a key card is not a yes to a trade.
4. **The read is fresh:** `account` ran after their last answer.

## Procedure

1. [FIXED] Every turn, before any reply - a refusal or a question too - extract the helper
   from this skill, then read the owner's wallet and the account:

   ```sh
   awk '/^```python$/{f=1;next} /^```$/{f=0} f' "$HOME/skills/papertrade-xyz/references/helper.md" > /tmp/papertrade.py
   bevo-read me
   python3 /tmp/papertrade.py account --owner <OWNER>
   python3 /tmp/papertrade.py markets
   ```

   `<OWNER>` is `user.agentWalletAddress` from `bevo-read me`, always. Relay the read's
   figures as given (`references/account.md`). Then look at
   `sessionKey.action` (step 2) on **every** read, whatever the owner asked.

2. [FIXED] Keep the session key usable. When `sessionKey.todo` is set, do it in this same
   turn, before you reply: file the card, then tell the owner it is waiting in the app.
   `sessionKey.action` says why:
   - `ready` - nothing.
   - `renew` - under a day left. It still works; file the renewal now, even if they asked
     about something else, so a close never waits for one.
   - `register` - not usable: none on-chain, or expired. Opens **and closes** wait for it.
   - `key-new` - no key yet: run `key-new` once, then register it.
   - `fund-first` - never funded: no card yet; fund it (step 3).

   Register (also for `renew`; it is the same key again):

   ```sh
   python3 /tmp/papertrade.py key-new --owner <OWNER>
   python3 /tmp/papertrade.py register-typed-data --owner <OWNER>
   acp wallet sign-typed-data --data "$(cat <typedDataFile>)" --chain-id 999 --purpose "Let Butler trade on Papertrade for 30 days (cannot withdraw)" --reading "$(cat <readingFile>)" --idempotency-key <KEY>:register
   ```

   `key-new` only for `key-new`. `<typedDataFile>` and `<readingFile>` are the paths
   `register-typed-data` printed; never edit those files. The reply is an approval card:
   tell the owner what it lets Butler do and to approve it in the app. Then step 9 with
   `<KEY>:register`, and with the signature:

   ```sh
   python3 /tmp/papertrade.py register-body --owner <OWNER> --signature <SIGNATURE>
   curl -sS -X POST https://exchange.papertrade.xyz/intents -H "Content-Type: application/json" --data @<bodyFile> -w "\n%{http_code}\n"
   ```

   `201` is accepted; `key-status` reads `ready` about 30 seconds later. Still not after a
   minute: "Accepted but not landed" below.

3. [FIXED] Fund only when asked or when `availableUsd` is below the margin they want. Plan
   it first: it counts what already waits at their deposit address and refuses an amount
   that would sit there uncredited. Its refusal is said as written; nothing is filed:

   ```sh
   python3 /tmp/papertrade.py deposit-plan --owner <OWNER> --amount <USDC>
   acp trade --token-in usdc --amount-in <amountUsd> --token-out usdc --chain-out 1337 --recipient <depositAddress> --idempotency-key <KEY>:deposit
   ```

   No amount, or refused: say its `why` and ask for at least `sendAtLeastUsd`; never
   offer a smaller one. Use the
   plan's `amountUsd` and `depositAddress` exactly; never another chain than `1337`. The
   reply is a card; once it confirms (step 9, `--route trade`), read `account` until
   `availableUsd` rises (`pendingDepositUsd` is what still waits).

4. [ADAPT] Quote it with the owner's own numbers. It signs nothing, and refuses anything
   under Papertrade's minimums or over `availableUsd`; give its reason as written:

   ```sh
   python3 /tmp/papertrade.py quote --owner <OWNER> --market <MARKET> --side <SIDE> --margin <USD> --leverage <N>
   ```

   Offer it with the quote's fields only, never your own arithmetic: `positionUsd`,
   `badCase` word for word, and `wipedOutNearPrice` as "about". Ask:
   *"Open a $2,000 BTC long with $20 at 100x? A 1% move against you and the whole $20
   is gone - about $81,500 on BTC."*

5. [FIXED] With all four met and the key `ready` or `renew`, build the open with the same
   numbers they said yes to:

   ```sh
   python3 /tmp/papertrade.py open --owner <OWNER> --market <MARKET> --side <SIDE> --margin <USD> --leverage <N>
   ```

   `<MARKET>` is a `symbol` from `markets` (`BTC`, `ETH`); `<SIDE>` is `long` or `short`.

6. [FIXED] Send the `bodyFile` it printed, once, then confirm from the account:

   ```sh
   curl -sS -X POST https://exchange.papertrade.xyz/intents -H "Content-Type: application/json" --data @<bodyFile> -w "\n%{http_code}\n"
   python3 /tmp/papertrade.py account --owner <OWNER>
   ```

   `201` is queued, not filled: the position appears in `positions` within seconds. Not
   there after half a minute: "Accepted but not landed" below.

7. [FIXED] Close as soon as they ask, with ids from this turn's `positions` (at most 12):

   ```sh
   python3 /tmp/papertrade.py close --owner <OWNER> --ids <ID,ID>
   curl -sS -X POST https://exchange.papertrade.xyz/intents -H "Content-Type: application/json" --data @<bodyFile> -w "\n%{http_code}\n"
   python3 /tmp/papertrade.py account --owner <OWNER>
   ```

   No card while the key is usable. If `close` says it is not registered, file the
   registration (step 2) at once; the close waits for the owner.

8. [FIXED] Withdraw only when asked, at most `maxWithdrawUsd` and at least 10. It lands
   on the owner's Hyperliquid account. If `account` has a `withdrawNote`, nothing can go
   out: say it word for word and file nothing; never offer a smaller amount.

   ```sh
   python3 /tmp/papertrade.py withdraw-typed-data --owner <OWNER> --amount <USDC>
   acp wallet sign-typed-data --data "$(cat <typedDataFile>)" --chain-id 999 --purpose "Withdraw <USDC> USDC from Papertrade to your Hyperliquid account" --reading "$(cat <readingFile>)" --idempotency-key <KEY>:withdraw
   ```

   Approval card; then step 9 with `<KEY>:withdraw`, and:

   ```sh
   python3 /tmp/papertrade.py withdraw-body --owner <OWNER> --signature <SIGNATURE>
   curl -sS -X POST https://exchange.papertrade.xyz/intents -H "Content-Type: application/json" --data @<bodyFile> -w "\n%{http_code}\n"
   ```

   The signature is good for one hour; past that, build it again and file a new card.
   It is done when `cashflows` shows the withdrawal `settled`.

9. [FIXED] Wait for a card's outcome; never file it again to find out:

   ```sh
   bevo-read request <KEY>:<OP> --route execute
   ```

   A card exists only once this finds it: run it right after filing, and never tell the
   owner a card is waiting before it does. `not_found` - nothing was filed; say so.
   `approvalStatus: confirmed` - `approvalOutcome.signature` is the `<SIGNATURE>`.
   `rejected` or `failed` - nothing was signed; give the reason as written. `pending` -
   still with the owner: say so and stop until they come back.

## Idempotency and retries

One key per errand, such as `pt:btc:long:1`, with `:register`, `:deposit` and `:withdraw`.
On an error, a timeout or an unclear answer, **do not re-run** a signing or `acp trade`
command: a second deposit spends twice. Look it up as in step 9. A `curl` to `/intents`
may be sent again **with the same `bodyFile` only** - Papertrade refuses a used nonce -
but **never build a new open** after an unclear answer: read `account` first, because a
new build is a second trade.

### Accepted but not landed

Every build prints an `intentId`. When a `201` has not shown up in `account` or
`key-status` after half a minute, ask Papertrade's queue once:

```sh
python3 /tmp/papertrade.py intents --owner <OWNER> --intent <intentId>
```

- `stillQueued: true` - still waiting its turn; say so and read again later.
- `false`, and still not in `account` - it did not go through, and nothing moved. Say so.
  An open or a close is built again only if the owner asks again. A registration or a
  withdrawal needs a new card: build it again (`register-typed-data` or
  `withdraw-typed-data`, never `key-new`) and file it with a new key.

## Failure handling

| Answer | What to do |
| --- | --- |
| `admission_rejected` + `noDeposit` | Fund first (step 3). |
| `admission_rejected` + `funding` | Not enough available; re-read `account` and say so. |
| `admission_rejected` + `belowMinimum`, `belowMinimumNotional`, `leverageTooHigh`, `positionTooLarge`, `openInterest` | Give the reason and ask; never resize it yourself. |
| `admission_rejected` + `tradingPaused`, `marketPaused`, `inactiveInstrument` | Not taking that trade now; closing still works. |
| `admission_rejected` + `noOpenPositions` | Already closed or closing. Re-read `account`. |
| `admission_rejected` + `sessionKeyLimit` | Too many keys registered; never make another. Say so and stop. |
| `unauthorized_intent` | The key is not usable: read `account`, then step 2. |
| `deadline_expired` | Build it again; for an owner step, a new card. |
| `intent_conflict` | That intent is already in; read `account`. |
| `below_minimum_withdrawal` | Withdraw at least 10. |
| `rate_limited` | Wait a minute, then send the same `bodyFile`. |
| Helper `error: ...` | Give it as written; nothing was sent. |
| `on-chain check failed` | Papertrade changed its contracts. Stop and say so. |

## Limits

- **Markets:** those `markets` lists `openable` (BTC, ETH today).
- **No stop-loss or take-profit.** Liquidation takes the whole margin at the bust price.
- **Fees:** a small haircut plus 2% of a winning close's gain; a loss costs nothing extra.
- **Withdrawals:** at least 10 USDC, plus 1 USDC the first time unless the owner has a
  Hyperliquid account; `maxWithdrawUsd` includes it.
- **Deposits** come from the owner's USDC through `acp trade` only.
- **Chat only.** A duty cannot use this session key.
- **Papertrade's API is unpublished:** an answer unlike `references/api.md` means it
  changed; stop and say so.

## Say to the owner

- Leverage in dollars: "a $2,000 position with $20 of your money", never just "100x".
- The bad case before the upside, every time.
- "Queued" until `account` shows the position; never "filled" from a `201`.
- Approval cards: what it lets Butler do, then "approve it in the app".
- After a close: what came back to `availableUsd`, from the read.
