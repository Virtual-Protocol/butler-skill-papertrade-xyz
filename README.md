# butler-skill-papertrade-xyz

Teaches a Butler agent to trade BTC and ETH perpetuals on
[Papertrade](https://papertrade.xyz) for its owner: check the balance and open positions,
fund the account, open and close positions, withdraw, report closed positions with
their PnL, and stake PAPER and claim its USDC rewards. A duty can use it too, for example to close a position at a stop or a target.

Two things shape how it works:

- **Opens and closes are signed by a session key, not the owner's wallet.** Papertrade
  refuses a trade the owner's wallet signs (`403 unauthorized_intent`, measured). The
  owner approves the key once with a card, and after that a close is never held up by
  one. The key cannot withdraw, so a leaked key can lose the Papertrade balance through
  trades but cannot move it anywhere. It lives in `~/.papertrade/session-key.json`, outside
  the skill directory that a hub update replaces. A duty signs with the same key through a
  copy of the helper kept beside it, under a lock so the two never reuse a nonce.
- **Registering the key, withdrawing and staking need the owner.** Each is an EIP-712
  signature from the owner's wallet, filed as an approval card. The key lasts 30 days,
  and the skill renews it a day before it expires, because the owner may not be there to
  approve the card.

One Butler skill, published by the
[Butler skill hub](https://github.com/Virtual-Protocol/butler-skills): the hub's
`skills.json` lists it by name, repo and ref.

- `SKILL.md` — the playbook (see the hub's
  [SKILL_STANDARD.md](https://github.com/Virtual-Protocol/butler-skills/blob/main/SKILL_STANDARD.md))
- `references/` — what the playbook points to: the account, the session key, the API,
  PAPER staking, running it from a duty, and `helper.md`, the helper script the agent
  extracts and runs
- `CHANGELOG.md` — one entry per version; every change bumps `version` in SKILL.md

`references/helper.md` holds the tested script verbatim. Change the script, test it, and
regenerate the file; never edit its code block by hand. Its secp256k1 constants are
decimal because the hub's secret check flags 64-character hex strings.

Validate locally:

```sh
curl -sSLO https://virtual-protocol.github.io/butler-skills/tools/validate.py
python3 validate.py --standalone .
```
