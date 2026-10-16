# The session key

Papertrade only takes opens and closes signed by a **session key**, never by the owner's
wallet. The owner's wallet signs once to register it; after that the key trades for 30
days with no approval card. It **cannot withdraw**: withdrawals always need the owner's
own signature, through an approval card.

## Where it lives

`~/.papertrade/session-key.json`, made by `key-new` and readable only by its owner. The
helper reads it to sign and never prints it. Never open, `cat`, copy, move, upload or paste
it, and never put it in a message, a note or a duty. Anyone holding it can trade, and lose,
the owner's Papertrade balance.

## What `sessionKey.action` means

| `action` | State | Do |
| --- | --- | --- |
| `ready` | registered, more than a day left (`expiresIn`) | nothing |
| `renew` | registered, under a day left; still works | register the **same** key again now. Ask the owner to approve it even mid-conversation about something else |
| `register` | not registered on-chain, or expired | register it; nothing can open **or close** until the owner approves |
| `key-new` | no key on this butler | `key-new` once, then register |

Registering the same key again resets its 30 days; measured on Papertrade, with the
expiry moving forward and the key never interrupted. **There is never a reason to make a
second key:**
- each registered key counts against a limit (`sessionKeyLimit`);
- an old key cannot be cancelled from here, so it stays able to trade until it expires;
- `key-new` refuses while a key exists.

## Why renewal is a day early

Renewal is an approval card, and the owner may not be there to tap it. Papertrade's own
app renews an hour before, because its owner is at the screen. Butler asks a day ahead so
a close is never the first thing to find the key expired.

## Registering

1. `register-typed-data` writes the typed data and the card's reading, and prints both
   paths.
2. `acp wallet sign-typed-data` with those files becomes an approval card. The owner sees
   that it lets Butler open and close Papertrade positions, that it cannot withdraw, the
   key's address, and its end date.
3. `bevo-read request <KEY>:register --route sign` gives the signature once approved.
4. `register-body` checks the signature is the owner's and writes the request.
5. `curl` sends it. `key-status` shows `ready` about 30 seconds later.

The prepared registration is good for one hour. Past that, run `register-typed-data`
again and file a new card.
