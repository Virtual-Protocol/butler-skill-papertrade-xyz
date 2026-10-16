# papertrade-xyz

The `papertrade-xyz` skill for [Butler](https://github.com/Virtual-Protocol/butler-skills):
trade BTC and ETH perpetuals on [Papertrade](https://papertrade.xyz). This README is for
the humans maintaining the repo and is never published to a butler. Only `SKILL.md` and
`references/**/*.md` reach one.

**Status: 1.0.0; its listing (butler-skills#60) is a draft.** It waits for the changes in
"What it depends on" to ship.

## What it does

| Intent | How |
| --- | --- |
| Look | the helper's `account` and `markets` reads |
| Fund | `acp trade ... --chain-out 1337 --recipient <deposit address>`: Base USDC bridged into the owner's Papertrade deposit address on Hyperliquid's ledger |
| Open / close | the session key signs; `curl` posts to Papertrade's `/intents`. No approval card, so a close is never delayed |
| Withdraw | the owner signs `WithdrawToCore` through `acp wallet sign-typed-data` (an approval card); funds land on their Hyperliquid account |

## How signing is split

- **The owner's wallet** (the hosted Privy EOA, `agentWalletAddress`) signs only the
  session-key registration and withdrawals, through `acp wallet sign-typed-data`, which
  bevo-server signs after the owner approves a card.
- **The session key** signs opens and closes. Papertrade refuses an owner-signed trade
  (`403 unauthorized_intent`, measured). The helper generates the key and keeps it in
  `~/.papertrade/session-key.json` (0600) on the butler's volume.

Why a file and not the vault, bevo-server or a skill directory:
- **The vault:** only a duty can read a value, and only as a credential, never to sign.
- **bevo-server:** it would need key storage built for one venue.
- **A skill directory:** `hub_update` replaces the directory, so the key would be deleted
  on every version bump.

The risk is bounded because a session key **cannot withdraw**: a leaked key can lose the
Papertrade balance through trades, not move it anywhere. That is also why this pattern is
not the answer for a key that can move funds.

## What it depends on

1. **bevo-server `POST /butler-exec/execute`, typed-data mode:** `typedData` instead of
   `to`/`data`/`value` returns an EIP-712 signature behind an approval card, read back
   through `/butler-read/exec-requests/<key>?route=execute`.
2. **virtuals-agent:** `acp wallet sign-typed-data` forwarded to it.
3. **bevo-app:** a card for a signature request in the approvals screen.
4. **butler-skills:** `acp wallet sign-typed-data` classed as a money command in
   `SKILL_STANDARD.md`.

## Validating a change

```sh
python3 ../butler-skills/scripts/validate.py --standalone .
```

The helper in `references/helper.md` is the tested script verbatim. Edit the script, test
it, and regenerate the reference; never edit the code block by hand. The secp256k1
constants are decimal on purpose, because the hub's secret lint flags 64-hex strings.
