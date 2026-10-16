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
| `openPosition` | session key | `user`, `instrumentId`, `isLong`, `size` (margin, 18 decimals), `leverage`, `useDebt`, `nonce`, `deadline` |
| `closePositions` | session key | `user`, `positionIds` (1 to 12), `nonce`, `deadline` |
| `withdrawToCore` | owner wallet | `user`, `amount` (USDC, 6 decimals), `nonce`, `deadline`; plus `"withdrawal": {"route": "hypercore"}` beside `signed` |

Numbers travel as decimal strings, addresses in lowercase. `user` is always the owner's
wallet, even when the session key signs. `deadline` is one hour ahead; `nonce` is never
reused.

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

## POST /funding/deposits/check

```json
{ "user": "<owner>" }  ->  { "proxy": "<the owner's deposit address>" }
```

## Reads (GET, no signature)

| Path | Gives |
| --- | --- |
| `/state/trading` | markets and minimums (the helper's `markets`) |
| `/queue-rank/accounts/<owner>` | `{ "ok": true, "entries": [ { "intentId", "position" } ] }`: intents still in the queue |
| `/query/accounts/<owner>/funding` | `{ "items": [...], "coreAccount": false }`: deposit and withdrawal history |

Balances and positions are read from the HyperEVM contracts by the helper, not from these.
