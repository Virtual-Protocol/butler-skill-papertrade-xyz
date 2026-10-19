# Papertrade's request API

Papertrade publishes no API. This is what its own app sends, measured against production
on 2026-10-15. The helper builds every request; read this to understand an answer, not to
build a request by hand.

Base: `https://exchange.papertrade.xyz`. No account, cookie or API key: the signature in
each request is the only credential.

## POST /intents

```json
{ "action": "openPosition", "signed": { "...message fields...": "...", "v": "27", "r": "0x...", "s": "0x..." } }
```

| `action` | Signed by | Message |
| --- | --- | --- |
| `registerSessionKey` | owner wallet | `user`, `key`, `expiry`, `feeAddress`, `nonce`, `deadline` |
| `openPosition` | session key | `user`, `instrumentId`, `isLong`, `size` (margin, 18 decimals), `leverage`, `useDebt`, `nonce`, `deadline`. `useDebt` is always `false`: the skill opens only from the available balance, never from a queued payout |
| `closePositions` | session key | `user`, `positionIds` (1 to 12), `nonce`, `deadline` |
| `withdrawToCore` | owner wallet | `user`, `amount` (USDC, 6 decimals), `nonce`, `deadline`; plus `"withdrawal": {"route": "hypercore"}` beside `signed` |
| `paperStake` | owner wallet | `Stake`: `user`, `amount` (PAPER, 18 decimals), `nonce`, `deadline` |
| `paperUnstake` | owner wallet | `Unstake`: `user`, `amount` (PAPER, 18 decimals), `nonce`, `deadline` |
| `paperClaim` | owner wallet | `Claim`: `user`, `nonce`, `deadline` |

Numbers travel as decimal strings, addresses in lowercase. `user` is always the owner's
wallet, even when the session key signs. `deadline` is one hour ahead; `nonce` is never
reused.

The first four are signed under the Exchange's EIP-712 domain (name `String`, version
`1`, chain 999). The three `paper` actions are signed under PaperStaking's own: name
`PaperStaking`, version `1`, chain 999, PaperStaking as the verifying contract. Their
nonces are PaperStaking's, apart from the Exchange's: `nonces(user)` on PaperStaking is one
past the highest it has used, and `isNonceUsed(user, nonce)` says whether one is taken.
A session key never signs them; the helper refuses to.
The intent id is computed the same way for all seven.

An open or close signed by the owner's wallet is refused with `unauthorized_intent`: only
the session key trades.

### Accepted: 201

```json
{ "intentId": "0x...", "action": "openPosition", "state": "queued", "acceptedAt": "2026-10-15T10:07:58.324Z", "queueRevision": "3" }
```

`queued` is not filled. Measured: an open was on-chain 4 seconds later, a close about 9,
a registration up to 20. States after that: `prepared`, `confirmed`, `failed`,
`reverted`, `expired`, `cancelled`. The `account` read is the truth.

### Refused

| HTTP | Body | Means |
| --- | --- | --- |
| 403 | `{"code":"unauthorized_intent"}` | the signer is not allowed: no registered session key, an expired one, or an owner-signed trade |
| 409 | `{"code":"admission_rejected","reason":"..."}` | refused by Papertrade's checks; the reasons are in `SKILL.md` |
| 409 | `{"code":"intent_conflict"}` | the same intent is already in |
| 4xx | `{"code":"invalid_intent"}` / `deadline_expired` / `below_minimum_withdrawal` | as named |
| 429 | `{"code":"rate_limited"}` | too many requests; wait |

`registerSessionKey` for an account with no deposit yet answers `noDeposit`. A withdrawal
answers `funding` when it asks for more than the balance holds: the whole balance while a
1 USDC activation fee is owed on top, or a balance rounded up past its 18-decimal value.

The staking actions, measured on 2026-10-19 from a wallet with no PAPER, each correctly
signed:

| Sent | Answer |
| --- | --- |
| `paperStake` of 1 PAPER | 409 `{"code":"below_minimum_paper_stake","minimumPaperStakeRaw":"1000000000000000000000"}` |
| `paperStake` of 1,000 PAPER | 409 `admission_rejected`, `paperBalance` |
| `paperUnstake` of 1,000 PAPER | 409 `admission_rejected`, `stakedBalance` |
| `paperClaim` | 409 `admission_rejected`, `noRewards` |
| `paperStake` signed under the Exchange's domain instead | 403 `unauthorized_intent` |

An action Papertrade has paused answers `intake_action_paused`.

## POST /funding/deposits/check

```json
{ "user": "<owner>" }  ->  { "proxy": "<the owner's deposit address>" }
```

## Reads (GET, no signature)

| Path | Gives |
| --- | --- |
| `/state/trading` | markets and minimums (the helper's `markets`); `intakeControls` is `[revision, minimum stake in PAPER (18 decimals), [paused actions]]` |
| `/queue-rank/accounts/<owner>` | `{ "ok": true, "entries": [ { "intentId", "position" } ] }`: intents still in the queue |
| `/query/accounts/<owner>/funding` | `{ "items": [...], "coreAccount": false }`: deposit and withdrawal history |

Balances and positions are read from the HyperEVM contracts by the helper, not from these.
PAPER too: `balanceOf` on the PAPER token, and `stakedBalance`, `pendingReward` and
`totalStaked` on PaperStaking. `pendingReward` is USDC with 18 decimals, and counts only
rewards already distributed.
