# Seven Sleepers rescript: two-family fact-check (24 Nov 2026, 22:50-23:25 UTC)

Script: `data/rescript/ss_script.py` (written in a Claude Code session from the film's three source articles). Sources: Wikipedia "Seven Sleepers",
"Cave of the Seven Sleepers", "Seven Sleepers' Day" as cached 21 Nov 02:33 UTC (cache/wiki/*.txt, 25,602 characters). Every run is in
`data/rescript/ss_factcheck_24nov*.json` with each judge's own answer. No model rewrote any line: every change below was made by hand from a source passage.

## Method
1. Deterministic checks (no model): claim ledger (`ledger.build`: every name, number, year and quotation looked up in the sources), the script rules
   (`scriptreview.rows` with the sources), a strict scan of every number, capitalised name and quotation.
2. Two judges of different model families through the fixed production path (`scriptgen.unsupported` -> `llm._free_review`, see Phase B), 30 lines per part,
   prompt: "SOURCES is the only truth ... knowledge from outside SOURCES counts as unsupported even when it is true".
3. Every flag was checked against the exact source passage: a flag the passage refutes is recorded as refuted; a fair flag was fixed in the script and the
   whole script was checked again by two fresh judges (never only the changed lines).
4. Independent outside checks (web search, 23 Nov): the Qur'an middle-word tradition, the Ephesus excavation dates, the 1951/1963 Jordan discovery, the
   Seven Sleepers' Day hit rate.

## Rounds
| Run | Fingerprint | Judges (family) | Flags | Outcome |
|---|---|---|---|---|
| own check | 197d78b5ce77 | none (sources + web) | 6 | fixed: 5 (legend narrated as fact), 31 ("the middle chapter": Al-Kahf is chapter 18 of 114; the source and the tradition speak of the middle by words), 33 (quote marks around words the verse does not quote), 51 (dig dates differ between sources: 1926-28, 1926-29, 1927-30 -> "the late 1920s"), 55 (Jordan Awqaf dates the discovery to the 1963 excavation -> "by one account ... 1951"), 84 (hedged) |
| 1 | 146914b8cd16 | nemotron-3-ultra (nvidia) + gemini-3.5-flash-lite (google) on every part | 34, 62, 64, 65, 81, 84, 85, 86 | fixed 3: 62 ("argued" -> "tried to place"), 81 (declaration not dated to the Crusades), 85 (no "meteorologists"); refuted 5 by passage: 34, 64, 65, 84, 86 |
| 2 | 0fd07ca3b386 | nvidia + google, then nvidia + particle-1 | 45, 49, 56, 86, 89, 90, 91 | all 7 fair (words the sources do not say): fixed; plus line 14 found by me ("earliest Syriac manuscript copy", not the oldest copy of all) |
| 3 | 8725f8e53865 | nvidia + particle-1, then google + nvidia | 1, 62, 81, 85, 86, 87 | fixed 1 (line 1 promised "where the story was first written down", which is lost); refuted 5: 62 ("favoured by al-Ṭabarī ... and al-Wāqidī"), 81 (the source's own sentence: "became common during the Crusades ..., and June 27 was declared"), 85 ("a high-pressure ridge ... over Scandinavia, which may coalesce with the subtropical Azores High"), 86 ("the meandering flow of the polar jet stream in the Northern Hemisphere"), 87 (John 24 June, Medardus 8 June, Swithun 15 July are all in the source) |
| 4 | 20967dd6893d | google+nvidia, nvidia+particle | lines 60-89 BLOCKED (only NVIDIA answered; particle 429) | correct BLOCKED, not a pass; stopped (old code) and rerun |
| 5 | 20967dd6893d | nvidia+particle on every part (fixed code: both judges must return a verdict list) | 69, 76 | both fair: fixed (69 overgeneral; 76 "jokes" -> "surmises", as the source says) |
| 6 | 99efe0767289 | nvidia+particle, google+nvidia | lines 60-89 BLOCKED (nemotron-3.5-lightning replied one item, no list); 31, 32, 34, 36, 42, 55, 62, 84 | 32 fair ("alleged piety" -> "piety attributed to"): fixed; 7 refuted by passage |
| 7 | c9a5ca23ed40 | attempt 1 BLOCKED (same malformed reply); attempt 2 nvidia+google, google+nvidia, nvidia+particle | 56, 62, 67, 84 (gemini) + 60-89 all (lightning: "not the exact phrasing") | 67 fair (the apostle refused to ENTER the city): fixed; the rest refuted by passage |
| 8 | ee95a92092bb | nvidia+particle on every part | lightning flagged 48 lines, writing "Supported by SOURCES" for 28 of them; particle: 92 | 92 fair ("their Lord knows best" read as a quote; source: "God knows best"): fixed; lightning's list is self-contradicting |
| **9 (final)** | **e93dc43d643f** | **nemotron-3-ultra (nvidia) + particle-1 on every part** | **none** | **passed; lines hash 1639ba97b2df; record data/rescript/ss_factcheck_24nov_run9_FINAL_fpe93dc43d643f.json** |

## Legend, tradition and history
The script frames the Christian story as legend ("the story says", "the legend tells us", "in the story"), the Qur'anic account as what the Qur'an says, later
numbers and names as tradition, and the caves as claims ("none has been proven to be the original"; "there is no consensus"). The only plain historical
statements are dated records (Decius died in 251, Jacob of Serugh, Gregory of Tours, the Golden Legend, the relics at Marseille, the excavations).

## Finding about the judges (not fixed)
`nvidia/nemotron-3.5-lightning:free` twice returned a malformed reply (one item instead of a list) and twice flagged whole parts while calling the lines supported.
Because the stricter answer counts (llm.strictest: every item either judge lists), one degenerate judge can flag everything; the malformed replies are now BLOCKED
(24 Nov fix), but a judge that lists "supported" lines as unsupported is not detected. Candidate fix (owner's decision): drop items whose own reason says
"supported", or rank judges by such contradictions in freemodels.

## Limits
- The judges are free models; their flags were noisy (11 of 26 refuted by the sources). Wikipedia is a secondary source; the outside checks were web searches,
  not a historian's review.
- "particle-ai/particle-1" is a maker the family table does not know: the code counts an unknown line as its own family. Its base model is not documented,
  so its independence from NVIDIA is assumed, not shown. The google + nvidia parts have no such doubt.
- Not checked by a model: the narration audio and pictures (that is the review after the render).
