# T14 — Netherlands jurisdiction review (flag only)

**Claimed by:** session 30beeb55 · **Status:** needs review (publish as a Flagged for Review item)
**Accessed:** 2026-11-14 (UTC) · **Scope:** what official Dutch sources say on the lines of the project; **not legal advice and not a legal conclusion.**

## Why this is flagged

The project owner's stated location is the Netherlands (Naaldwijk, South Holland). The
existing register flags only Japan (F09 / T07). Nothing in the repository addresses Dutch
law, so the wagering, reward and leaderboard features need a Dutch-law review before any
use by a person located in the Netherlands.

## Official sources checked

| # | Official source | What it says (verified text) | Link |
|---|---|---|---|
| NL-1 | Wet op de kansspelen (Wok), Titel I, art. 1 lid 1 (current consolidated text, "Geldend van 12-02-2025 t/m heden", retrieved 14-11-2026) | "Behoudens het in Titel Va ... bepaalde is het verboden: a. gelegenheid te geven om mede te dingen naar prijzen of premies, indien de aanwijzing der winnaars geschiedt door enige kansbepaling waarop de deelnemers in het algemeen geen overwegende invloed kunnen uitoefenen, tenzij daarvoor ... vergunning is verleend; b. de deelneming ... te bevorderen, daartoe middelen te verschaffen ...; c. gebruik te maken van een onder a bedoelde gelegenheid, wetende dat voor het geven daarvan geen vergunning ... is verleend; d. ..." | https://wetten.overheid.nl/BWBR0002469/2025-02-12 |
| NL-2 | Kamerstuk 33996, nr. 3 (Memorie van toelichting, wetsvoorstel kansspelen op afstand), section I.1 | "Het gesloten stelsel van de Wok staat kansspelen op afstand nog niet toe. Sedert jaren nemen honderdduizenden Nederlanders echter al «online» deel aan dergelijke kansspelen waarbij de doelstellingen van het Nederlandse kansspelbeleid niet zijn gewaarborgd." (Pre-2021 background; the licensed online regime is described in the same statute, Titel Va.) | https://zoek.officielebekendmakingen.nl/kst-33996-3.html |
| NL-3 | Kansspelautoriteit (Ksa), Kansspelwijzer page | "Hier vindt u alle aanbieders die kansspelen mogen aanbieden in Nederland. Zoek op naam en/of verfijn de resultaten ... en kijk of wij een vergunning gaven." | https://kansspelautoriteit.nl/kansspelwijzer |
| NL-4 | Kansspelautoriteit (Ksa), home page | "Online of offline gokken? Check eerst of de aanbieder een vergunning heeft." | https://www.kansspelautoriteit.nl/ |

## Points for qualified Dutch-law review (open questions)

1. **Skill vs. chance.** Art. 1 lid 1 sub a applies only where winners are chosen by a chance
   mechanism that participants cannot exert dominant influence over. Whether a
   forecasting leaderboard with prizes or rewards falls inside or outside that test is a
   legal question. The repository does not answer it. Do not treat skill framing as a
   legal safe harbour without review.
2. **Participation.** Sub c prohibits knowingly using an unlicensed gambling opportunity.
   The applicability to a user located in NL of any offer made from outside NL needs review.
3. **Promotion.** Sub b prohibits promoting participation in an unlicensed opportunity,
   including supplying means for it. Referral links, affiliate content and "bet here"
   suggestions would need review.
4. **Sportsbook use.** Only KSA-licensed providers are listed in the Kansspelwijzer (NL-3).
   Any sportsbook or price feed the project may connect should be checked against it.
5. **Tax.** Secondary sites say winnings from unlicensed operators may have to be declared.
   **Not verified** against an official Belastingdienst page; not stated as fact here.

## Recommended handling (for the integration session)

- Add a flag (F19 proposal): "Netherlands jurisdiction not reviewed — wagering, referral,
  reward and leaderboard features remain disabled pending qualified Dutch-law review."
- Keep wagering, referral, and reward features disabled, as the README already says for F09.
- Do not state that any activity is legal or illegal in NL based on this file.
