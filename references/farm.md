# Farming PAPER

Papertrade mints PAPER when a position closes at a loss. A farm holds a long and a short
of the same size on one market at once, so one side's loss is the other side's gain: the
losing leg mints PAPER, and the cycle costs what Papertrade keeps back from the winning
leg. A duty runs the cycles until the owner's budget is spent or they stop it, so they
fill in one ticket and approve it once:

```text
open a long + a short → price moves ±MOVE_PCT → close both → note the cycle → again
```

**The cost is what the winning leg gives back.** A winning leg is paid back about 10%
less than it made (much less on small moves), then Papertrade keeps its win fee (2%
today) of the rest; a loss costs nothing extra. On BTC a 1% cycle keeps about 86% of the
win, a 0.3% cycle about 82%. So a cycle costs about $1.36 per $1,000 leg at 1%, and $0.53
at 0.3%. `farm-quote` works it out; never do the arithmetic yourself.

## The ticket

"I want to farm PAPER" means a farm duty. **One farm per market:** read the owner's duties
first, and if a farm on that market is running (titled "Farm PAPER on <MARKET>, ..."), say so
and show it instead of a new ticket. A second one would take the first one's legs for its
own. A farm on the other market is fine. Never assume a setting: no leverage, size, move
or budget is the owner's until they say it. Show the ticket with every field blank, its
limits beside it, and this turn's `availableUsd`, and ask them to fill it in:

```text
Farm ticket — Papertrade (you have $<availableUsd>)
  Market             ___     BTC or ETH
  Margin per leg     $___    at least $10, and margin x leverage at least $1,000;
                             each cycle holds two legs (a long and a short)
  Leverage           ___x    the losing leg is wiped out at about a (100 / leverage)% move
  Move per cycle     ±___%   both legs close once price moves this far, either way
  Budget             $___    the most the farm may lose; it runs until this is spent
                             or they say "stop farming"
```

Ask again for only the fields still blank, showing what they have filled.

**Never fill a field for them, even when asked.** Not a value, not a "what I'd go with",
not a list of picks to confirm: the farm opens legs with no one asking, so every number
has to be one they typed. "You pick", "default", "whatever" or "go" is not a value:

> I can't choose these for you: the farm trades on its own once it starts, so each number
> has to be yours. Still blank: leverage, move per cycle, budget.

Never suggest a leverage higher than one they named. A field they gave earlier in the conversation
counts once you repeat it back in the ticket.

**Never judge Papertrade's room yourself.** A leg needs room for its whole position
(margin x leverage, such as $1,000), so $16 of room is full, not "room". Leave
`longRoomUsd`/`shortRoomUsd` out of the ticket; `farm-quote` says when a side is full.

Then quote it. It signs nothing, refuses settings that cannot work (and says which value
to change), and works out the cycle:

```sh
python3 /tmp/papertrade.py farm-quote --owner <OWNER> --market <MARKET> --margin <USD> --leverage <N> --move <PCT> --budget <USD>
```

Quote only once every field has their value. A refusal is said as written, and the ticket
shown again with that field marked for them to change. A refusal for funds is not a field
to change: it already says the least to send, with the bridge fee on top. Offer that
deposit (`SKILL.md` step 3, with `--target` set to the farm's need it names), and quote
again once `availableUsd` has risen. Never offer the bare gap: the bridge keeps a little
of it, and Papertrade credits nothing under 10 USDC.
Otherwise say, from its fields only:

> **{badCase}**
>
> **{summary}** {breakEven} That is {costPer1kPaperUsd} per 1,000 PAPER. The losing leg pays
> {losingLegsPayUsd}; the winning leg keeps {winningLegsKeepUsd} ({winningKeepsPct}%).
>
> BTC is at {markPrice}; this cycle closes at {exitDownPrice} or {exitUpPrice}. Your
> {budgetUsd} budget is about {cyclesForBudget} cycles and {paperForBudget} PAPER. It runs
> until that is spent or you say "stop farming", and stops by itself if BTC moves 1%
> inside a minute. Each cycle holds {cycleHoldsUsd} while it runs. Start it?

Say each of `warnings` after it, word for word. When `paperPerCycle` is null, say the
summary as written and skip the PAPER figures. Their yes, after you said the bad case, is
their yes to every leg the farm opens: a duty asks no one before it opens.

## Filing it

1. The key must be `ready` (`SKILL.md` step 1); otherwise do step 2 first and file the
   farm once it is.
2. Get the path the duty runs:

   ```sh
   python3 /tmp/papertrade.py duty-helper --owner <OWNER>
   ```

3. Check again that no farm runs on that market. Then file it from the template
   `papertrade-farm@1` (`duty_create` with `recipe`), **never with `code`**: the template
   is the whole program and words its own status line. Send only:
   - `recipe`: `papertrade-farm@1`;
   - a `timer` trigger every 60 seconds;
   - `params`: `PAPERTRADE_HELPER` (the `helper` path), `MARKET`, `MARGIN_USD`,
     `LEVERAGE`, `MOVE_PCT` and `BUDGET_USD`, as numbers, exactly as quoted;
   - the title `Farm PAPER on {MARKET}, ${BUDGET_USD} budget`.

   A refusal names the setting or field it wants: fix that one and send again. Never
   switch to writing the code yourself.
4. Tell them it is running, that each cycle lands in its thread with what it cost and
   minted, and that "stop farming" ends it.

## While it runs

- **"How's my farm?"** Read the duty's status and log, then `history`. The status has the
  budget spent so far; the log has one `cycle` line per closed cycle with its PnL and PAPER.
- **"Stop farming."** Pause the duty first, so it opens nothing more, then read `account`.
  The farm's legs are the positions on its `MARKET` at its `MARGIN_USD` and `LEVERAGE`:
  say their PnL before fees and close them all in one `close --ids` (`SKILL.md` step 7).
  If the owner holds other positions of that shape, ask which first.
- **A change** ("make it ETH", "bigger"): stop it as above, show the ticket with the new
  values, quote it, and file a new farm once they agree.

## What the duty does

Each minute it reads `account`, then:

- **Stops** (closing every farm leg first) when the price moved 1% or more since the
  last minute. With nothing open it also stops once its closed cycles have lost
  `BUDGET_USD` in all, or when a cycle no longer fits in `availableUsd`. It checks the
  budget between cycles, so the last cycle can take it a little past; a wiped-out leg,
  up to that leg's margin past.
- **Opens** a cycle when none is open and both sides have room under Papertrade's
  open-interest cap: the tighter side first, so a refusal leaves nothing open. When a side
  is full it waits, with one note to the owner, and starts once both have room. A cap
  that fills between the check and the open is not counted as a failure.
- **Just opened:** waits for all the legs. Some missing after two minutes means Papertrade
  took only part of it: it closes what did open and tries a fresh cycle; three in a row
  and it stops.
- **Cycle open:** closes every leg in one request once price is `MOVE_PCT` from the
  legs' average entry. A leg gone on its own (wiped out) closes the rest at once.
- **Cycle closed:** reads `history` for its legs and notes the cycle (PnL, PAPER) in the
  duty's thread without a push.

The template `papertrade-farm` is this program. It never touches a position it did not
open. A refused close is sent again every minute, never given up on, with one note to the
owner after five. A key that is not `ready` gets one note and no request until it is;
`renew` still trades. After a request is accepted it waits two minutes before sending
another for the same legs.

Its settings: `PAPERTRADE_HELPER`, `MARKET`, `MARGIN_USD`, `LEVERAGE`, `MOVE_PCT` and
`BUDGET_USD`.
