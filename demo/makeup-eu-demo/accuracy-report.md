# Accuracy test: EU Cosmetics Regulation Q&A demo

Test date: 2026-09-26. Data: makeup-eu extraction of Annexes II–VI, consolidated text of 18 May 2026 (2,410 entries, 64 flagged for review).

**Result: 21 of 22 passed on the first live run; 22 of 22 plus the bonus question after two prompt fixes (retested 2026-09-27).** All 7 questions that should be refused were refused. On the first run, one Chinese answer reversed the meaning of one condition, and a bonus trade-name question missed (the page refused instead of answering wrongly). Both pass after the fixes below.

## How the demo answers

1. **Scope check first.** Questions about other countries' rules, or asking for safety or formulation advice, are refused without calling the model.
2. **Lookup.** The page matches full substance names, INCI names, CAS and EC numbers against the annex tables. If nothing matches, the model only maps the question to English substance names (used for French and Chinese questions and trade names). Nothing found means a refusal.
3. **Answer from the rows found.** The model sees only the matching rows. It must return which rows it used; the page draws the citation tags from those rows, not from the model's text. Rows in `review_queue.csv` always show a "flagged for review" notice.

## Results

Pass means: the right entry was cited, the key figure was correct, and the review notice appeared where expected.

| # | Question | Expected | Result |
|---|---|---|---|
| 1 | Max concentration of thioglycolic acid in depilatories? | 5 %, Annex III / 2a · p. 140 | Pass |
| 2 | Thioglycolic acid limit in eyelash waving products? | 11 %, Annex III / 2a · p. 140 | Pass |
| 3 | Is p-Phenylenediamine restricted? | Restricted, review notice, p. 144–146 | Pass (III/8a and 8b, notice shown) |
| 4 | Is this ingredient allowed in Canada? | Refuse: EU only | Pass |
| 5 | Is Zorbitaxol allowed in face creams? (made up) | Refuse: not found | Pass |
| 6 | Maximum concentration of phenoxyethanol as a preservative? | 1,0 %, Annex V / 29 · p. 421 | Pass |
| 7 | Salicylic acid limit in rinse-off hair products? | 3,0 %, Annex III / 98 · p. 200 | Pass |
| 8 | Can hydroquinone be used in skin creams? | Annex II ban, only exception artificial nail systems (III/14) | Pass |
| 9 | Can formaldehyde be used in cosmetic products? | Prohibited, Annex II / 1577 · p. 128 | Pass |
| 10 | Maximum zinc oxide concentration as a UV filter? | 25 %, Annex VI / 30 and 30a | Pass |
| 11 | Is triclosan allowed in toothpaste? | 0,3 %, Annex V / 25 · p. 420 | Pass |
| 12 | Hydrogen peroxide limit in hair products? | 12 %, Annex III / 12 · p. 153–154 | Pass |
| 13 | Which annexes list CAS 69-72-7? | Annex III / 98 and Annex V / 3 | Pass |
| 14 | Retinol limit in body lotion? | 0,05 % RE, Annex III / 376, review notice | Pass |
| 15 | Benzophenone-3 limit in face products? | 6 %, Annex VI / 4 · p. 429–430 | Pass |
| 16 | Quelle est la concentration maximale de phénoxyéthanol ? (FR) | 1,0 %, V / 29, answer in French | Pass |
| 17 | 水杨酸在淋洗类发用产品中的最高浓度是多少？(ZH) | 3,0 %, III / 98, answer in Chinese | First run **fail**: limit and citation correct, but "for purposes other than inhibiting micro-organisms" was translated as the opposite. Pass after fix |
| 18 | What does the FDA say about talc? | Refuse: EU only | Pass |
| 19 | Give me a recipe for a sunscreen with zinc oxide | Refuse: advice | Pass |
| 20 | 甲醛在中国国内能用吗？(ZH) | Refuse: EU only | Pass |
| 21 | Is methylparaben safe for pregnant women? | Refuse: advice | Pass |
| 22 | Is Glowmaxin-7 permitted in lipsticks? (made up) | Refuse: not found | Pass |
| B | Is Lilial banned? (trade name) | Banned, Annex II / 1666 | First run **miss**: name mapping picked an unrelated substance; the answer step noticed and refused. Pass after fix |

The lookup and refusal logic (steps 1–2) was also run offline against the same 22 questions: 22/22.

## Fixes and retest

| Change | Retest |
|---|---|
| Answer prompt: keep each condition's exact meaning, including "not", "except" and "other than"; explain the recurring phrase "for purposes other than inhibiting the development of micro-organisms"; in French and Chinese answers, add each condition's original English wording in parentheses so the reader can check it | #17 now correct: "适用于除抑制产品中微生物生长以外的用途 (For purposes other than inhibiting…)" |
| Name-mapping prompt: for trade names, return both the INCI name and the systematic chemical name (the prompt's example uses a different substance, not Lilial) | Bonus now correct: banned, Annex II / 1666 · p. 133 |
| Regression check | #16 (French) still correct: 1,0 %, V / 29 · p. 421 |

A wording-only reversal like #17 is the kind of error this test is meant to catch. Quoting the source wording next to translated conditions keeps it checkable even if it recurs.

## Known limits

- It answers questions about named substances. "List all preservatives allowed in leave-on products" is refused, because no single substance is named.
- A substance that is not in Annexes II–VI gets "not found". That does not mean it is allowed.
- Rows flagged for review have names and CAS/EC numbers that could not be paired one-to-one in the source table, so their answers always carry a warning.
- This is a demo on public data and not legal advice.
