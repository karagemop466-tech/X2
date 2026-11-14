# Correlation Values

Correlation values determine whether multi-leg parlay and player-prop-combo
strategies are genuinely diversifying or are double-counting the same underlying
risk. Correlations are **computed from official historical data** — they are never
assumed.

## Correlations to determine

{{TABLE: correlations}}

## Method

For each pair, the Pearson correlation is computed over the official historical
data window from the linked sources:

- **C-01** same-game side vs. total: correlates a game's spread result with its
  total result.
- **C-02** QB passing yards vs. team total: correlates a QB's passing output with
  the game total.
- **C-03** RB rushing vs. WR receiving (same offense): correlates same-offense rush
  and receive output.
- **C-04** team offense vs. team defense efficiency: correlates offensive and
  defensive efficiency metrics.
- **C-05** injury-impact score vs. line movement: correlates the computed
  backup-replacement deficiency score with observed opening-to-closing line movement.
- **C-06** moneyline vs. point spread: correlates moneyline-implied and spread-
  implied team strength.

## Why the values are blank

**No official pre-computed correlation values exist to cite.** Correlations must be
computed from the connected official data feed. Because the primary odds feed and
the historical settlement data are not yet connected, every `correlation_value` is
left **blank and flagged as unverified** rather than inferred or filled in with a
guess. This is recorded on the [Flagged for Review](../flagged-for-review/) page.

Once the data feed is connected, these values will be computed and populated, and
the correlation-bound gate (G-04) will then accept or reject multi-leg strategies
based on them.
