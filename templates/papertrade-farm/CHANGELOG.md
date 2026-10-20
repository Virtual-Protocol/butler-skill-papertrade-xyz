# Changelog

## 1

- The Papertrade farm duty as a template. Before, the Butler filed the farm by copying 226
  lines of code from the Papertrade skill and a status template by hand; a weaker model
  broke the code or the status rules on every try (four `invalid_payload` refusals in a
  row, found live 2026-10-20). Filed from this template, it is a title, a 60-second timer
  and six settings. Sends intents through the helper's `send` (papertrade-xyz 1.3.1),
  since a template may name no URL.
- A close Papertrade still holds in its queue is waited for, not counted as refused.
  Found live: Papertrade held an accepted close for 20 minutes and answered each re-send
  with `409 noOpenPositions`; the duty counted those as refusals and pushed the owner
  "Papertrade has refused to close your farm's BTC legs five times". It now re-sends
  quietly every two minutes until the legs are gone.
- `STOP` ends the farm after closing every leg it opened. Found live: asked to stop, a
  Butler disabled the farm and left both legs open. A settings update restarts the duty
  with its state, so the farm itself closes its legs (waiting out Papertrade's queue),
  reports the last cycle and ends. Its status reads "Closing the farm's legs" meanwhile.
