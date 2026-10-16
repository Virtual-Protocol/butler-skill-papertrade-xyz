# The Papertrade helper

`SKILL.md` step 1 extracts the script below to `/tmp/papertrade.py` with `awk`, every turn,
so it always matches this version of the skill; never retype it. Stdlib only.
It keeps the session key, signs opens and closes with it, prepares owner steps for
`acp wallet sign-typed-data`, and reads the account. It never sends a trade itself: every
request it prepares lands in its own `bodyFile` and goes out with the `curl` in `SKILL.md`.

```sh
python3 /tmp/papertrade.py config
python3 /tmp/papertrade.py markets
python3 /tmp/papertrade.py account --owner <OWNER>
python3 /tmp/papertrade.py deposit-plan --owner <OWNER> --amount 20
python3 /tmp/papertrade.py key-status --owner <OWNER>
python3 /tmp/papertrade.py key-new --owner <OWNER>
python3 /tmp/papertrade.py register-typed-data --owner <OWNER>
python3 /tmp/papertrade.py register-body --owner <OWNER> --signature <SIGNATURE>
python3 /tmp/papertrade.py quote --owner <OWNER> --market BTC --side long --margin 20 --leverage 100
python3 /tmp/papertrade.py open --owner <OWNER> --market BTC --side long --margin 20 --leverage 100
python3 /tmp/papertrade.py close --owner <OWNER> --ids 756953
python3 /tmp/papertrade.py intents --owner <OWNER> --intent <intentId>
python3 /tmp/papertrade.py history --owner <OWNER> --limit 20
python3 /tmp/papertrade.py cashflows --owner <OWNER>
python3 /tmp/papertrade.py withdraw-typed-data --owner <OWNER> --amount 12.5
python3 /tmp/papertrade.py withdraw-body --owner <OWNER> --signature <SIGNATURE>
```

It prints one JSON object on stdout. Exit `0`: done. Exit `1`: refused or unreachable,
with a one-line `error: ...` on stderr written for the owner; nothing was sent. Exit `2`:
the command line was wrong.

## What it keeps, and where

| File | Holds |
| --- | --- |
| `~/.papertrade/session-key.json` (0600) | the session key: owner, address, private key, next nonce. **Never print, copy or move it** |
| `~/.papertrade/config.json` | Papertrade's contract addresses, read from its app and checked on-chain, for a day |
| `~/.papertrade/pending-*.json` | an owner step waiting for its signature |
| `typedDataFile` (`/tmp/pt-<id>-typed.json`) | the typed data for `acp wallet sign-typed-data --data` |
| `readingFile` (`/tmp/pt-<id>-reading.json`) | the card's plain-language reading of it, for `--reading`; computed from the signed fields, never edited |
| `bodyFile` (`/tmp/pt-<id>-body.json`) | the request to send to `/intents` |

Every build writes new files with a fresh `<id>` and prints their paths: use the paths it
printed, so two conversations building at once never send each other's request.

`config` finds the Exchange address in Papertrade's own app and refuses it unless the
chain agrees: its session-key manager must point back to it, and the signing domain must
match. A failure there means Papertrade changed its contracts; stop.

## Commands

| Command | Does |
| --- | --- |
| `markets` | the markets Papertrade lists, which are `openable`, `maxLeverage`, `maxPositionUsd`, and the minimums `minMarginUsd` / `minPositionUsd` |
| `account` | the balance, open positions, deposit address, withdrawal limits and the session key's state (`references/account.md`) |
| `deposit-plan` | the least to send so a deposit is credited (`sendAtLeastUsd`), counting USDC already waiting at the deposit address and the one-time 1 USDC fee to open it, with `why` to say to the owner. With `--amount`, refuses an amount that would sit uncredited, or confirms it with `amountUsd` and `depositAddress` for the `acp trade` |
| `key-status` | `action`: `ready`, `renew` (under a day left), `register` or `key-new`; `expiresIn`; and, whenever it is not `ready`, `todo`: the instruction to carry out in the same turn |
| `key-new` | makes a session key and prints only its address; refuses whenever one exists |
| `register-typed-data` / `register-body` | the owner's one signature that lets the key trade for 30 days |
| `quote` | every check an open makes, signing nothing: `positionUsd`, `wipedOutAtMovePct`, `wipedOutNearPrice` (about; the real bust price sits a little before it), `markPrice`, and `badCase`, the sentence to say to the owner |
| `open` | the same checks, then signs with the session key and writes the `bodyFile` |
| `close` | signs a close for 1 to 12 position ids |
| `history` | closed positions, newest first, with `pnlUsd` and `pnlPct` as Papertrade's app computes them (adjusted PnL less the fee; a liquidation is minus the margin), and a `summary` (`references/account.md`) |
| `cashflows` | deposits and withdrawals with their `status`; a withdrawal is done at `settled` |
| `intents` | Papertrade's queue for the owner; with `--intent`, `stillQueued` for one request. Neither queued nor in `account` means it did not go through |
| `withdraw-typed-data` / `withdraw-body` | the owner's signature for a withdrawal to their Hyperliquid account |

The `-body` commands check that the signature recovers to the owner before writing the
request; a signature from any other wallet is refused and nothing is written.

## The script

```python
"""Papertrade helper: session key, signing and reads for the papertrade-xyz skill.

Stdlib only. The session key lives in $HOME/.papertrade/session-key.json (0600)
and never leaves this process: no command prints it. Owner signatures are not
made here; this prints the typed data for `acp wallet sign-typed-data` and
assembles the request once the owner's signature comes back.

Exit 0: done, one JSON object on stdout. Exit 1: refused or unreachable, one
line `error: ...` on stderr. Exit 2: bad command line.
"""

import argparse
import hashlib
import hmac
import json
import math
import os
import re
import secrets
import sys
import time
import urllib.parse
import urllib.request

API = "https://exchange.papertrade.xyz"
RPC = "https://rpc.hyperliquid.xyz/evm"
HL_INFO = "https://api.hyperliquid.xyz/info"
CHAIN_ID = 999
DOMAIN_NAME = "String"  # Papertrade's EIP-712 domain name really is "String"
DOMAIN_VERSION = "1"
HOME = os.path.join(os.path.expanduser("~"), ".papertrade")
KEY_FILE = os.path.join(HOME, "session-key.json")
CONFIG_FILE = os.path.join(HOME, "config.json")
PENDING = os.path.join(HOME, "pending-{}.json")
SCRATCH_DIR = "/tmp"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
SESSION_TTL = 30 * 24 * 3600
# Renewal needs the owner to approve a card, so it is asked for a day ahead: a close
# must never be the first thing to find the key expired.
RENEW_BEFORE = 24 * 3600
DEADLINE = 3600
WAD = 10 ** 18
USDC = 10 ** 6
# Papertrade sweeps a deposit address into the account once it holds this much in all.
SWEEP_MIN = 10
# Hyperliquid's fee to open a new HyperCore account, paid by a deposit address's first arrival.
ACTIVATION_FEE = 1
# Relay's Base→Hyperliquid fee is not quoted to us; this is the margin kept above it.
BRIDGE_BUFFER = 1
# The trading bot's own floor for a deposit into Hyperliquid.
BOT_MIN_DEPOSIT = 5
ZERO_ADDRESS = "0x" + "0" * 40

TYPES = {
    "RegisterSessionKey": [("user", "address"), ("key", "address"), ("expiry", "uint64"),
                           ("feeAddress", "address"), ("nonce", "uint256"), ("deadline", "uint64")],
    "OpenPosition": [("user", "address"), ("instrumentId", "uint32"), ("isLong", "bool"),
                     ("size", "uint128"), ("leverage", "uint32"), ("useDebt", "bool"),
                     ("nonce", "uint256"), ("deadline", "uint64")],
    "Close": [("user", "address"), ("positionIds", "uint256[]"), ("nonce", "uint256"), ("deadline", "uint64")],
    "WithdrawToCore": [("user", "address"), ("amount", "uint256"), ("nonce", "uint256"), ("deadline", "uint64")],
}

INSTRUMENT_FIELDS = [
    "id", "symbol", "assetIndex", "priceScale", "active", "paused", "terminal", "retired", "closeOnly",
    "frozenBid", "frozenAsk", "pausedAt", "rateMultiplier", "positionMultiplier", "maxLeverage",
    "maxPositionNotional", "bustBuffer", "baseRate", "referenceNotional", "longOi", "shortOi", "longCap", "shortCap",
]


class Refused(Exception):
    pass


# ---- keccak-256 (Ethereum's, not hashlib's sha3_256) -------------------------

_RC = [0x1, 0x8082, 0x800000000000808A, 0x8000000080008000, 0x808B, 0x80000001, 0x8000000080008081,
       0x8000000000008009, 0x8A, 0x88, 0x80008009, 0x8000000A, 0x8000808B, 0x800000000000008B,
       0x8000000000008089, 0x8000000000008003, 0x8000000000008002, 0x8000000000000080, 0x800A,
       0x800000008000000A, 0x8000000080008081, 0x8000000000008080, 0x80000001, 0x8000000080008008]
_ROT = [[0, 36, 3, 41, 18], [1, 44, 10, 45, 2], [62, 6, 43, 15, 61], [28, 55, 25, 21, 56], [27, 20, 39, 8, 14]]
_M64 = (1 << 64) - 1


def _rol(x, n):
    return ((x << n) | (x >> (64 - n))) & _M64 if n else x


def _keccak_f(a):
    for rc in _RC:
        c = [a[x][0] ^ a[x][1] ^ a[x][2] ^ a[x][3] ^ a[x][4] for x in range(5)]
        d = [c[(x - 1) % 5] ^ _rol(c[(x + 1) % 5], 1) for x in range(5)]
        a = [[a[x][y] ^ d[x] for y in range(5)] for x in range(5)]
        b = [[0] * 5 for _ in range(5)]
        for x in range(5):
            for y in range(5):
                b[y][(2 * x + 3 * y) % 5] = _rol(a[x][y], _ROT[x][y])
        a = [[b[x][y] ^ ((~b[(x + 1) % 5][y]) & b[(x + 2) % 5][y]) for y in range(5)] for x in range(5)]
        a[0][0] ^= rc
    return a


def keccak(data: bytes) -> bytes:
    rate = 136
    buf = bytearray(data) + b"\x01"
    while len(buf) % rate:
        buf += b"\x00"
    buf[-1] |= 0x80
    a = [[0] * 5 for _ in range(5)]
    for i in range(0, len(buf), rate):
        block = buf[i:i + rate]
        for j in range(rate // 8):
            a[j % 5][j // 5] ^= int.from_bytes(block[8 * j:8 * j + 8], "little")
        a = _keccak_f(a)
    return b"".join(a[j % 5][j // 5].to_bytes(8, "little") for j in range(4))


# ---- secp256k1 ----------------------------------------------------------------

_P = 2 ** 256 - 2 ** 32 - 977
_N = 115792089237316195423570985008687907852837564279074904382605163141518161494337
_G = (55066263022277343669578718895168534326250603453777594175500187360389116729240,
      32670510020758816978083085130507043184471273380659243275938904335757337482424)


def _add(p, q):
    if p is None:
        return q
    if q is None:
        return p
    if p[0] == q[0] and (p[1] + q[1]) % _P == 0:
        return None
    if p == q:
        m = 3 * p[0] * p[0] * pow(2 * p[1], -1, _P) % _P
    else:
        m = (q[1] - p[1]) * pow(q[0] - p[0], -1, _P) % _P
    x = (m * m - p[0] - q[0]) % _P
    return x, (m * (p[0] - x) - p[1]) % _P


def _mul(k, p):
    r = None
    while k:
        if k & 1:
            r = _add(r, p)
        p = _add(p, p)
        k >>= 1
    return r


def _address_of_point(pt) -> str:
    return "0x" + keccak(pt[0].to_bytes(32, "big") + pt[1].to_bytes(32, "big"))[12:].hex()


def address_of(private_key: int) -> str:
    return _address_of_point(_mul(private_key, _G))


def _rfc6979_k(private_key: int, digest: bytes) -> int:
    x = private_key.to_bytes(32, "big")
    h = (int.from_bytes(digest, "big") % _N).to_bytes(32, "big")
    v, k = b"\x01" * 32, b"\x00" * 32
    k = hmac.new(k, v + b"\x00" + x + h, hashlib.sha256).digest()
    v = hmac.new(k, v, hashlib.sha256).digest()
    k = hmac.new(k, v + b"\x01" + x + h, hashlib.sha256).digest()
    v = hmac.new(k, v, hashlib.sha256).digest()
    while True:
        v = hmac.new(k, v, hashlib.sha256).digest()
        cand = int.from_bytes(v, "big")
        if 1 <= cand < _N:
            return cand
        k = hmac.new(k, v + b"\x00", hashlib.sha256).digest()
        v = hmac.new(k, v, hashlib.sha256).digest()


def sign_digest(private_key: int, digest: bytes):
    z = int.from_bytes(digest, "big")
    k = _rfc6979_k(private_key, digest)
    point = _mul(k, _G)
    r = point[0] % _N
    s = pow(k, -1, _N) * (z + r * private_key) % _N
    parity = point[1] & 1
    if s > _N // 2:
        s, parity = _N - s, parity ^ 1
    return {"v": str(27 + parity), "r": "0x%064x" % r, "s": "0x%064x" % s}


def recover(digest: bytes, v: int, r: int, s: int) -> str:
    x = r
    y_sq = (pow(x, 3, _P) + 7) % _P
    y = pow(y_sq, (_P + 1) // 4, _P)
    if (y & 1) != ((v - 27) & 1):
        y = _P - y
    z = int.from_bytes(digest, "big")
    r_inv = pow(r, -1, _N)
    q = _add(_mul(s * r_inv % _N, (x, y)), _mul((-z * r_inv) % _N, _G))
    return _address_of_point(q)


def split_signature(sig: str):
    raw = sig[2:] if sig.startswith("0x") else sig
    if not re.fullmatch(r"[0-9a-fA-F]{130}", raw):
        raise Refused("the signature must be 65 bytes of hex (0x + 130 characters)")
    v = int(raw[128:130], 16)
    if v < 27:
        v += 27
    return v, int(raw[:64], 16), int(raw[64:128], 16)


# ---- EIP-712 -------------------------------------------------------------------

def _encode_type(primary):
    return f"{primary}(" + ",".join(f"{t} {n}" for n, t in TYPES[primary]) + ")"


def _word(kind, value) -> bytes:
    if kind == "address":
        return bytes(12) + bytes.fromhex(value[2:])
    if kind == "bool":
        return (1 if value else 0).to_bytes(32, "big")
    if kind == "bytes32":
        return bytes.fromhex(value[2:])
    if kind.startswith("uint"):
        return int(value).to_bytes(32, "big")
    raise ValueError(kind)


def struct_hash(primary, message) -> bytes:
    out = keccak(_encode_type(primary).encode())
    for name, kind in TYPES[primary]:
        value = message[name]
        if kind.endswith("[]"):
            out += keccak(b"".join(_word(kind[:-2], v) for v in value))
        else:
            out += _word(kind, value)
    return keccak(out)


def domain_separator(exchange) -> bytes:
    th = keccak(b"EIP712Domain(string name,string version,uint256 chainId,address verifyingContract)")
    return keccak(th + keccak(DOMAIN_NAME.encode()) + keccak(DOMAIN_VERSION.encode())
                  + CHAIN_ID.to_bytes(32, "big") + _word("address", exchange))


def digest_of(exchange, primary, message) -> bytes:
    return keccak(b"\x19\x01" + domain_separator(exchange) + struct_hash(primary, message))


def wire(primary, message):
    out = {}
    for name, kind in TYPES[primary]:
        v = message[name]
        if kind.endswith("[]"):
            out[name] = [str(int(x)) for x in v]
        elif kind.startswith("uint"):
            out[name] = str(int(v))
        elif kind == "address":
            out[name] = v.lower()
        else:
            out[name] = v
    return out


def intent_id(digest: bytes, signer: str) -> str:
    return "0x" + keccak(keccak(b"papertrade:intent-id:v2") + digest + bytes.fromhex(signer[2:])).hex()


def typed_data(exchange, primary, message):
    """The JSON `acp wallet sign-typed-data --data` takes."""
    types = {"EIP712Domain": [{"name": "name", "type": "string"}, {"name": "version", "type": "string"},
                              {"name": "chainId", "type": "uint256"}, {"name": "verifyingContract", "type": "address"}],
             primary: [{"name": n, "type": t} for n, t in TYPES[primary]]}
    return {"domain": {"name": DOMAIN_NAME, "version": DOMAIN_VERSION, "chainId": CHAIN_ID,
                       "verifyingContract": exchange},
            "types": types, "primaryType": primary, "message": wire(primary, message)}


# ---- I/O -----------------------------------------------------------------------

def _http(url, body=None, headers=None, timeout=20):
    data = None if body is None else json.dumps(body).encode()
    h = {"Accept": "application/json", "User-Agent": UA}
    if body is not None:
        h["Content-Type"] = "application/json"
    h.update(headers or {})
    req = urllib.request.Request(url, data=data, headers=h, method="POST" if body is not None else "GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            return res.status, res.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode(errors="replace")
    except OSError as e:
        raise Refused(f"cannot reach {url.split('/')[2]}: {e}")


def api_get(path):
    status, text = _http(API + path)
    if status != 200:
        raise Refused(f"GET {path} answered {status}")
    return json.loads(text)


def eth_call(to, data):
    status, text = _http(RPC, {"jsonrpc": "2.0", "id": 1, "method": "eth_call", "params": [{"to": to, "data": data}, "latest"]})
    reply = json.loads(text) if status == 200 else {}
    if "result" not in reply:
        raise Refused(f"HyperEVM read failed: {reply.get('error') or status}")
    return reply["result"][2:]


def _words(hexdata):
    return [hexdata[i:i + 64] for i in range(0, len(hexdata), 64)]


def _addr_word(w):
    return "0x" + w[-40:]


def _sel(sig):
    return "0x" + keccak(sig.encode())[:4].hex()


def _read_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _write_private(path, obj):
    os.makedirs(HOME, mode=0o700, exist_ok=True)
    tmp = path + ".tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(obj, f)
    os.replace(tmp, path)


def _write_public(path, obj):
    with open(path, "w") as f:
        json.dump(obj, f)


def _scratch(kind, obj):
    """Each build gets its own file, so two conversations building at once never send each other's request."""
    path = os.path.join(SCRATCH_DIR, f"pt-{secrets.token_hex(4)}-{kind}.json")
    _write_public(path, obj)
    return path


def _owner(value):
    if not value or not re.fullmatch(r"0x[0-9a-fA-F]{40}", value):
        raise Refused("--owner must be the owner's wallet address (agentWalletAddress from `bevo-read me`)")
    return value.lower()


# ---- config: the Exchange address, read and checked on-chain -------------------

def config(refresh=False):
    cached = None if refresh else _read_json(CONFIG_FILE)
    if cached and cached.get("verifiedAt", 0) > time.time() - 86400:
        return cached
    nav = {"Accept": "text/html", "Sec-Fetch-Dest": "document", "Sec-Fetch-Mode": "navigate", "Sec-Fetch-Site": "none"}
    status, html = _http(API + "/trade", headers=nav)
    if status != 200:
        raise Refused(f"Papertrade's app answered {status}; cannot read its contract address")
    found = None
    for path in sorted(set(re.findall(r'/assets/[A-Za-z0-9_.-]+\.js', html)), key=lambda p: "wire" not in p):
        status, js = _http(API + path)
        m = re.search(r'contracts:\{exchange:`(0x[0-9a-fA-F]{40})`', js) if status == 200 else None
        if m:
            found = m.group(1).lower()
            break
    if not found:
        raise Refused("could not find the Exchange address in Papertrade's app")
    manager = _addr_word(eth_call(found, _sel("sessionKeyManager()")))
    if _addr_word(eth_call(manager, _sel("authorizedCaller()"))) != found:
        raise Refused("on-chain check failed: the session-key manager does not point back to this Exchange")
    if eth_call(manager, _sel("DOMAIN_SEPARATOR()")) != domain_separator(found).hex():
        raise Refused("on-chain check failed: the signing domain does not match; Papertrade changed its contracts")
    cfg = {"exchange": found, "sessionKeyManager": manager, "chainId": CHAIN_ID, "verifiedAt": int(time.time())}
    _write_private(CONFIG_FILE, cfg)
    return cfg


# ---- session key ----------------------------------------------------------------

def _load_key(owner):
    k = _read_json(KEY_FILE)
    if not k or k.get("owner") != owner or not re.fullmatch(r"[0-9a-f]{64}", str(k.get("privateKey", ""))):
        return None
    return k


def _take_nonce(k):
    n = int(k["nextNonce"])
    k["nextNonce"] = str(n + 1)
    _write_private(KEY_FILE, k)
    return n


def _onchain_expiry(cfg, owner, address):
    data = _sel("sessionKeys(address,address)") + _word("address", owner).hex() + _word("address", address).hex()
    return int(_words(eth_call(cfg["sessionKeyManager"], data))[0], 16)


def _left(seconds):
    if seconds >= 2 * 86400:
        return f"{seconds // 86400} days"
    if seconds >= 7200:
        return f"{seconds // 3600} hours"
    return f"{max(seconds, 0) // 60} minutes"


def key_status(owner):
    """`action` is the one thing to do next: key-new, register (none on-chain, or expired),
    renew (under a day left: register the same key again) or ready."""
    cfg = config()
    k = _load_key(owner)
    file_card = ("File the registration card now, in this turn: run register-typed-data, then "
                 "acp wallet sign-typed-data with the two files it prints (SKILL.md step 2). "
                 "Never tell the owner a card is coming before it is filed.")
    if not k:
        return {"key": None, "registered": False, "action": "key-new",
                "todo": "Run key-new once, then: " + file_card}
    expiry = _onchain_expiry(cfg, owner, k["address"])
    left = expiry - int(time.time())
    if left <= 0:
        return {"key": k["address"], "registered": False, "expiresAt": expiry or None, "action": "register",
                "todo": "Opens and closes are blocked until the owner approves. " + file_card}
    if left <= RENEW_BEFORE:
        return {"key": k["address"], "registered": True, "expiresAt": expiry, "expiresIn": _left(left),
                "action": "renew", "todo": "The key still works but ends soon. " + file_card}
    return {"key": k["address"], "registered": True, "expiresAt": expiry, "expiresIn": _left(left),
            "action": "ready"}


def key_new(owner, rotate):
    # --rotate is for a human recovering a key Papertrade no longer accepts; the skill
    # never passes it: an expired or expiring key is registered again, never replaced.
    if _load_key(owner) and not rotate:
        raise Refused("a session key already exists; never make another. Register it again with register-typed-data")
    priv = secrets.randbelow(_N - 1) + 1
    k = {"owner": owner, "address": address_of(priv), "privateKey": "%064x" % priv,
         "createdAt": int(time.time()), "nextNonce": str((secrets.randbelow(0xFFFFFF) + 1) * 256)}
    _write_private(KEY_FILE, k)
    return {"key": k["address"], "next": "register it: register-typed-data, then the owner's approval card"}


# ---- intents --------------------------------------------------------------------

def _now():
    return int(time.time())


def _utc_date(ts):
    return time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(int(ts)))


def owner_typed(owner, primary, extra, reading):
    """Owner-signed intents: write the typed data and the card's reading, keep the message for the body.

    The reading is computed here from the message itself, never written by the model, so
    the owner's card says in plain words what the signed fields do."""
    cfg = config()
    k = _load_key(owner)
    if not k:
        raise Refused("no session key: run `key-new` first")
    message = {"user": owner, **extra, "nonce": _take_nonce(k), "deadline": _now() + DEADLINE}
    td = typed_data(cfg["exchange"], primary, message)
    typed_file = _scratch("typed", td)
    reading_file = _scratch("reading", reading(message))
    _write_private(PENDING.format(primary), {"primary": primary, "message": wire(primary, message)})
    return {"typedDataFile": typed_file, "readingFile": reading_file, "primaryType": primary,
            "deadline": message["deadline"],
            "next": "file it with acp wallet sign-typed-data using these two files; the owner has 1 hour to approve"}


def register_reading(message):
    return {"Lets Butler": "open and close Papertrade positions for you",
            "Cannot": "withdraw or move your funds",
            "Session key": message["key"],
            "Lasts until": _utc_date(message["expiry"])}


def withdraw_reading(fee):
    def build(message):
        rows = {"Withdraws": f"{message['amount'] / USDC:g} USDC from Papertrade",
                "Goes to": "your own Hyperliquid account"}
        if fee:
            rows["Fee"] = f"{fee:g} USDC, once, to open your Hyperliquid account"
        return rows
    return build


def owner_body(owner, primary, signature, action, extras=None):
    cfg = config()
    pending = _read_json(PENDING.format(primary))
    if not pending:
        raise Refused(f"nothing pending for {primary}: build the typed data first")
    msg = pending["message"]
    if msg["user"] != owner:
        raise Refused("the pending request is for a different owner")
    if int(msg["deadline"]) <= _now():
        raise Refused("the signed request expired (1 hour); build it again and get a new signature")
    v, r, s = split_signature(signature)
    digest = digest_of(cfg["exchange"], primary, {**msg, "positionIds": msg.get("positionIds", [])} if primary == "Close" else msg)
    signer = recover(digest, v, r, s)
    if signer != owner:
        raise Refused(f"the signature is from {signer}, not the owner; nothing was sent")
    body = {"action": action, "signed": {**msg, "v": str(v), "r": "0x%064x" % r, "s": "0x%064x" % s}, **(extras or {})}
    body_file = _scratch("body", body)
    os.remove(PENDING.format(primary))
    return {"bodyFile": body_file, "action": action, "intentId": intent_id(digest, signer),
            "next": "send bodyFile once with curl"}


def session_body(owner, primary, action, extra):
    cfg = config()
    k = _load_key(owner)
    if not k:
        raise Refused("no session key: run `key-new`, then register it")
    st = key_status(owner)
    if not st["registered"]:
        raise Refused("the session key is not registered or has expired: the owner must approve a "
                      "registration card first (register-typed-data); nothing was built")
    message = {"user": owner, **extra, "nonce": _take_nonce(k), "deadline": _now() + DEADLINE}
    digest = digest_of(cfg["exchange"], primary, message)
    sig = sign_digest(int(k["privateKey"], 16), digest)
    body_file = _scratch("body", {"action": action, "signed": {**wire(primary, message), **sig}})
    return {"bodyFile": body_file, "action": action, "intentId": intent_id(digest, k["address"]),
            "next": "send bodyFile once with curl, then read account"}


# ---- reads ------------------------------------------------------------------------

def markets():
    state = api_get("/state/trading")
    out = []
    for row in state.get("instruments", []):
        m = dict(zip(INSTRUMENT_FIELDS, row))
        out.append({
            "id": m["id"], "symbol": m["symbol"],
            "openable": bool(m["active"] and not m["paused"]), "closeOnly": bool(m["closeOnly"]),
            "maxLeverage": m["maxLeverage"],
            "maxPositionUsd": int(m["maxPositionNotional"]) / WAD,
            "priceScale": int(m["priceScale"]),
        })
    return {"tradingPaused": state.get("tradingPaused"), "minMarginUsd": int(state["minimumTradeSizeRaw"]) / WAD,
            "minPositionUsd": int(state["minimumOpenNotionalRaw"]) / WAD, "markets": out}


def _mids():
    status, text = _http(HL_INFO, {"type": "allMids"})
    return json.loads(text) if status == 200 else {}


def _hl_info(kind, user):
    status, text = _http(HL_INFO, {"type": kind, "user": user})
    if status != 200:
        raise Refused(f"Hyperliquid did not answer ({status}); cannot read the deposit address")
    return json.loads(text)


def deposit_state(owner):
    """The owner's deposit address, the USDC already waiting there uncredited (it counts
    toward the next sweep), and whether its HyperCore account still needs opening."""
    status, text = _http(API + "/funding/deposits/check", {"user": owner})
    proxy = json.loads(text).get("proxy") if status == 200 else None
    if not proxy or not re.fullmatch(r"0x[0-9a-fA-F]{40}", proxy):
        raise Refused(f"Papertrade did not give a deposit address ({status}); nothing to deposit to")
    spot = sum(float(b.get("total") or 0) for b in _hl_info("spotClearinghouseState", proxy).get("balances", [])
               if b.get("coin") == "USDC")
    perp = float(_hl_info("clearinghouseState", proxy).get("withdrawable") or 0)
    opened = _hl_info("userRole", proxy).get("role") not in (None, "missing")
    return {"depositAddress": proxy.lower(), "pendingUsd": round(spot + perp, 6),
            "activationFeeUsd": 0 if opened else ACTIVATION_FEE}


def deposit_plan(owner, amount=None):
    """The least to send so a deposit is credited, and, given an amount, the acp trade for it
    or why it would sit uncredited. Credit needs SWEEP_MIN at the deposit address in all."""
    d = deposit_state(owner)
    pending, fee = d["pendingUsd"], d["activationFeeUsd"]
    missing = max(0.0, SWEEP_MIN - pending)
    least = max(BOT_MIN_DEPOSIT, math.ceil(missing + fee + BRIDGE_BUFFER - 1e-9))
    plan = {"depositAddress": d["depositAddress"], "pendingDepositUsd": pending, "activationFeeUsd": fee,
            "bridgeBufferUsd": BRIDGE_BUFFER, "sendAtLeastUsd": least}
    if pending >= SWEEP_MIN:
        plan["why"] = (f"{pending:g} USDC is already at your deposit address and is being credited; no "
                       f"deposit is needed for that. Anything more needs at least {least:g} USDC.")
    else:
        waiting = f"; {pending:g} USDC is already waiting there" if pending else ""
        first = f", plus the one-time {fee:g} USDC fee to open it" if fee else ""
        plan["why"] = (f"Papertrade credits a deposit once at least {SWEEP_MIN:g} USDC has arrived at your "
                       f"deposit address{first}{waiting}. The bridge from Base takes a small fee, so send at "
                       f"least {least:g} USDC.")
    if amount is None:
        return plan
    if amount + 1e-9 < least:
        raise Refused(f"{amount:g} USDC would sit at your deposit address uncredited. {plan['why']}")
    plan["amountUsd"] = amount
    return plan


def account(owner):
    cfg = config()
    ex = cfg["exchange"]
    mk = {m["id"]: m for m in markets()["markets"]}
    mids = _mids()
    balance = int(eth_call(ex, _sel("balances(address)") + _word("address", owner).hex())[:64], 16)
    ids_hex = _words(eth_call(ex, _sel("getUserOpenPositionIds(address)") + _word("address", owner).hex()))
    ids = [int(w, 16) for w in ids_hex[2:2 + int(ids_hex[1], 16)]] if len(ids_hex) > 1 else []
    positions = []
    for pid in ids:
        w = _words(eth_call(ex, _sel("positions(uint256)") + "%064x" % pid))
        inst, entry_raw, margin, lev, opened, is_long = int(w[1], 16), int(w[2], 16), int(w[3], 16), int(w[4], 16), int(w[5], 16), int(w[6], 16) == 1
        m = mk.get(inst, {})
        entry = entry_raw / m.get("priceScale", 1)
        notional = margin * lev / WAD
        mid = float(mids.get(m.get("symbol", ""), 0) or 0)
        move = ((mid - entry) / entry if is_long else (entry - mid) / entry) if mid and entry else None
        positions.append({
            "id": str(pid), "market": m.get("symbol", inst), "side": "long" if is_long else "short",
            "marginUsd": margin / WAD, "leverage": lev, "positionUsd": notional, "entryPrice": entry,
            "markPrice": mid or None,
            "pnlUsdBeforeFees": round(notional * move, 2) if move is not None else None,
            "wipedOutAtMovePct": round(100 / lev, 3),
            "openedAt": opened,
        })
    deposit = deposit_state(owner)
    funding = api_get(f"/query/accounts/{owner}/funding")
    withdrew = any(str(i.get("kind", i.get("type", ""))).lower().startswith("withdraw") for i in funding.get("items", []))
    fee = 0 if funding.get("coreAccount") or withdrew else 1
    available = balance / WAD  # balances() already leaves out margin locked in positions
    return {
        "owner": owner, "availableUsd": round(available, 6), "positions": positions,
        "depositAddress": deposit["depositAddress"], "pendingDepositUsd": deposit["pendingUsd"],
        "hyperCoreAccount": bool(funding.get("coreAccount")),
        "withdrawActivationFeeUsd": fee, "minWithdrawUsd": 10,
        "maxWithdrawUsd": max(0.0, round(available - fee, 6)),
        "withdrawNote": _withdraw_note(available, fee),
        "sessionKey": key_status(owner),
    }


def _withdraw_note(available, fee):
    """The sentence for an owner whose balance cannot go out: a model reasoning over two
    numbers offered '$9.72 now' against a $10 minimum."""
    if available - fee >= 10:
        return None
    if available <= 0:
        return "There is nothing in your Papertrade account to withdraw."
    need = round(10 + fee - available, 2)
    fee_part = f" plus the one-time {fee:g} USDC fee for a first withdrawal" if fee else ""
    return (f"Nothing can be withdrawn yet: Papertrade's minimum is 10 USDC{fee_part}, and "
            f"${available:.2f} is available. It needs ${need:g} more, which means a deposit of "
            f"at least 10 USDC, the least Papertrade credits.")


HISTORY_MAX = 200


def _pages(owner, kind, limit):
    """Papertrade's own history routes, newest first, 75 a page."""
    items, cursor = [], None
    while len(items) < limit:
        query = {"limit": "75", **({"cursor": cursor} if cursor else {})}
        reply = api_get(f"/query/accounts/{owner}/{kind}?{urllib.parse.urlencode(query)}")
        items += reply.get("items", [])
        nxt = reply.get("nextCursor")
        if nxt and nxt == cursor:
            # A cursor that repeats would loop for ever; what was read is real but not all of it.
            return items[:limit], True
        if not nxt:
            cursor = None
            break
        cursor = nxt
    return items[:limit], bool(cursor) or len(items) > limit


def _utc(ms):
    return time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(int(ms) // 1000))


def _held(seconds):
    seconds = max(0, int(seconds))
    if seconds < 120:
        return f"{seconds} seconds"
    if seconds < 7200:
        return f"{seconds // 60} minutes"
    if seconds < 172800:
        return f"{seconds // 3600} hours"
    return f"{seconds // 86400} days"


def history(owner, limit=20):
    """Closed positions with their result, as Papertrade's own table computes it: the
    adjusted PnL less the fee paid, and the whole margin for a liquidation."""
    rows, more = _pages(owner, "trades", max(1, min(limit, HISTORY_MAX)))
    trades, total, fees, wins, losses, liquidated = [], 0, 0, 0, 0, 0
    for e in rows:
        margin, fee = int(e["marginRaw"]), int(e.get("userPaidFeeRaw") or 0)
        is_liq = e.get("kind") == "Liquidated"
        net = -margin if is_liq else int(e.get("adjustedPnlRaw") or 0) - fee
        scale = int(e.get("priceScaleRaw") or 1)
        total, fees = total + net, fees + (0 if is_liq else fee)
        wins, losses, liquidated = wins + (net > 0), losses + (net < 0), liquidated + is_liq
        trades.append({
            "positionId": str(e["positionId"]), "market": e.get("symbol"),
            "side": "long" if e.get("isLong") else "short",
            "outcome": "liquidated" if is_liq else "closed",
            "marginUsd": margin / WAD, "leverage": e.get("leverage"),
            "positionUsd": round(margin * int(e.get("leverage") or 0) / WAD, 2),
            "entryPrice": int(e["entryPriceRaw"]) / scale, "exitPrice": int(e["exitPriceRaw"]) / scale,
            "pnlUsd": round(net / WAD, 6), "pnlPct": round(net * 100 / margin, 2) if margin else None,
            "feeUsd": round(fee / WAD, 6), "paperMinted": round(int(e.get("paperMintedRaw") or 0) / WAD, 6),
            "openedAt": _utc(e["openedAtMs"]), "closedAt": _utc(e["timestampMs"]),
            "heldFor": _held((int(e["timestampMs"]) - int(e["openedAtMs"])) / 1000),
            "txHash": e.get("txHash"),
        })
    return {"trades": trades, "more": more, "summary": {
        "count": len(trades), "wins": wins, "losses": losses, "liquidated": liquidated,
        "totalPnlUsd": round(total / WAD, 6), "totalFeesUsd": round(fees / WAD, 6),
        "covers": "these trades only; more exist" if more else "every closed trade"}}


def cashflows(owner, limit=20):
    """Deposits and withdrawals, newest first; a withdrawal is done at `settled`."""
    rows, more = _pages(owner, "cashflows", max(1, min(limit, HISTORY_MAX)))
    out = []
    for e in rows:
        recipient = e.get("recipientAmountRaw")
        out.append({
            "kind": str(e.get("kind", "")).lower(), "amountUsd": round(int(e["amountRaw"]) / WAD, 6),
            "receivedUsd": round(int(recipient) / WAD, 6) if recipient else None,
            "route": e.get("route"), "status": e.get("withdrawalStatus") or ("credited" if e.get("kind") == "Deposit" else None),
            "at": _utc(e["timestampMs"]), "txHash": e.get("txHash"),
        })
    return {"cashflows": out, "more": more}


def intents(owner, intent_id=None):
    """Papertrade's queue for this owner. An intent that is neither queued here nor shown
    in `account` did not go through: nothing moved, and its deadline has passed or it failed."""
    reply = api_get(f"/queue-rank/accounts/{owner}")
    queued = [e.get("intentId") for e in reply.get("entries", [])]
    out = {"queued": queued}
    if intent_id:
        out["intentId"] = intent_id.lower()
        out["stillQueued"] = intent_id.lower() in queued
    return out


def quote(owner, market, side, margin, leverage):
    """Every check an open makes, and the figures to put to the owner. Signs nothing."""
    mk = markets()
    m = next((x for x in mk["markets"] if x["symbol"].upper() == market.upper()), None)
    if not m:
        raise Refused(f"{market} is not a Papertrade market; markets: {', '.join(x['symbol'] for x in mk['markets'])}")
    if mk["tradingPaused"] or not m["openable"]:
        raise Refused(f"{m['symbol']} is not open for new positions now")
    if margin < mk["minMarginUsd"]:
        raise Refused(f"margin must be at least ${mk['minMarginUsd']:g}")
    if not 1 <= leverage <= m["maxLeverage"]:
        raise Refused(f"leverage must be 1 to {m['maxLeverage']}")
    if margin * leverage < mk["minPositionUsd"]:
        raise Refused(f"margin x leverage must be at least ${mk['minPositionUsd']:g}; "
                      f"${margin:g} needs at least {int(-(-mk['minPositionUsd'] // margin))}x")
    if margin * leverage > m["maxPositionUsd"]:
        raise Refused(f"margin x leverage must be at most ${m['maxPositionUsd']:g}")
    acct = account(owner)
    if margin > acct["availableUsd"] + 1e-9:
        raise Refused(f"only ${acct['availableUsd']} is available")
    mid = float(_mids().get(m["symbol"], 0) or 0)
    move = 100 / leverage
    q = {"market": m["symbol"], "side": side, "marginUsd": margin, "leverage": leverage,
         "positionUsd": round(margin * leverage, 2), "wipedOutAtMovePct": round(move, 3),
         "markPrice": mid or None,
         "wipedOutNearPrice": (round(mid * (1 - move / 100) if side == "long" else mid * (1 + move / 100), 2)
                               if mid else None),
         "availableUsd": acct["availableUsd"], "sessionKey": acct["sessionKey"]["action"],
         "badCase": f"a {move:g}% move against you and the whole ${margin:,.2f} is gone"}
    return q, m


# ---- command line ----------------------------------------------------------------

def main(argv):
    p = argparse.ArgumentParser(prog="papertrade.py")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("config").add_argument("--refresh", action="store_true")
    sub.add_parser("markets")
    for name in ("account", "key-status", "register-typed-data"):
        sub.add_parser(name).add_argument("--owner", required=True)
    kn = sub.add_parser("key-new")
    kn.add_argument("--owner", required=True)
    kn.add_argument("--rotate", action="store_true")
    for name in ("register-body", "withdraw-body"):
        b = sub.add_parser(name)
        b.add_argument("--owner", required=True)
        b.add_argument("--signature", required=True)
    w = sub.add_parser("withdraw-typed-data")
    w.add_argument("--owner", required=True)
    w.add_argument("--amount", required=True, type=float, help="USDC to receive, at least 10")
    dp = sub.add_parser("deposit-plan")
    dp.add_argument("--owner", required=True)
    dp.add_argument("--amount", type=float, help="USDC the owner wants to send from Base")
    for name in ("history", "cashflows"):
        hp = sub.add_parser(name)
        hp.add_argument("--owner", required=True)
        hp.add_argument("--limit", type=int, default=20, help=f"newest first, at most {HISTORY_MAX}")
    it = sub.add_parser("intents")
    it.add_argument("--owner", required=True)
    it.add_argument("--intent", help="the intentId a build printed")
    for name in ("quote", "open"):
        o = sub.add_parser(name)
        o.add_argument("--owner", required=True)
        o.add_argument("--market", required=True)
        o.add_argument("--side", required=True, choices=["long", "short"])
        o.add_argument("--margin", required=True, type=float, help="USD of margin")
        o.add_argument("--leverage", required=True, type=int)
    c = sub.add_parser("close")
    c.add_argument("--owner", required=True)
    c.add_argument("--ids", required=True, help="comma-separated position ids, at most 12")
    a = p.parse_args(argv)

    if a.cmd == "config":
        return config(a.refresh)
    if a.cmd == "markets":
        return markets()
    owner = _owner(a.owner)
    if a.cmd == "account":
        return account(owner)
    if a.cmd == "key-status":
        return key_status(owner)
    if a.cmd == "key-new":
        return key_new(owner, a.rotate)
    if a.cmd == "register-typed-data":
        k = _load_key(owner)
        if not k:
            raise Refused("no session key: run `key-new` first")
        return owner_typed(owner, "RegisterSessionKey",
                           {"key": k["address"], "expiry": _now() + SESSION_TTL, "feeAddress": ZERO_ADDRESS},
                           register_reading)
    if a.cmd == "register-body":
        return owner_body(owner, "RegisterSessionKey", a.signature, "registerSessionKey")
    if a.cmd == "withdraw-typed-data":
        if a.amount < 10:
            raise Refused("Papertrade's minimum withdrawal is 10 USDC")
        acct = account(owner)
        if a.amount > acct["maxWithdrawUsd"] + 1e-9:
            raise Refused(f"at most {acct['maxWithdrawUsd']} USDC can be withdrawn now "
                          f"(available {acct['availableUsd']}, activation fee {acct['withdrawActivationFeeUsd']})")
        return owner_typed(owner, "WithdrawToCore", {"amount": int(round(a.amount * USDC))},
                           withdraw_reading(acct["withdrawActivationFeeUsd"]))
    if a.cmd == "withdraw-body":
        return owner_body(owner, "WithdrawToCore", a.signature, "withdrawToCore", {"withdrawal": {"route": "hypercore"}})
    if a.cmd == "deposit-plan":
        return deposit_plan(owner, a.amount)
    if a.cmd == "history":
        return history(owner, a.limit)
    if a.cmd == "cashflows":
        return cashflows(owner, a.limit)
    if a.cmd == "intents":
        return intents(owner, a.intent)
    if a.cmd in ("quote", "open"):
        q, m = quote(owner, a.market, a.side, a.margin, a.leverage)
        if a.cmd == "quote":
            return q
        size = int(round(a.margin * 10 ** 6)) * 10 ** 12
        out = session_body(owner, "OpenPosition", "openPosition",
                           {"instrumentId": m["id"], "isLong": a.side == "long", "size": size,
                            "leverage": a.leverage, "useDebt": False})
        return {**out, **{k: q[k] for k in ("market", "side", "marginUsd", "leverage", "positionUsd", "wipedOutAtMovePct")}}
    if a.cmd == "close":
        ids = [x.strip() for x in a.ids.split(",") if x.strip()]
        if not 1 <= len(ids) <= 12 or len(set(ids)) != len(ids) or not all(x.isdigit() for x in ids):
            raise Refused("--ids takes 1 to 12 distinct position ids")
        return session_body(owner, "Close", "closePositions", {"positionIds": [int(x) for x in ids]})
    raise Refused(f"unknown command {a.cmd}")


if __name__ == "__main__":
    try:
        print(json.dumps(main(sys.argv[1:])))
    except Refused as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)
```
