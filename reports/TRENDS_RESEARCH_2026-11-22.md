# Trend research (22 Nov 2026, real data only)

Sub-plan 4 of the owner's master mission. Skill loaded first: youtube-research (`~/studio/.claude/skills/youtube-research`).
Fetched 2026-11-22 08:53 UTC. Raw responses, the script and `summary.json` are kept in `data/research/trends-2026-11-22/` (not in git).

## How, and why not a robot browser
- Google's terms forbid automated access to its pages, and the studio's rules bar a headless browser on Google and YouTube. No Chrome session tied to the owner (Claude in Chrome) was connected in this session. So: no page of trends.google.com was driven by a script.
- Used instead, all real data: (1) Google Trends' public "Trending now" RSS feed (`trends.google.com/trending/rss?geo=..`, published for feed readers), 5 countries; (2) Wikimedia's official pageview API (yesterday's 500 most-read English articles, their short descriptions, and a 35-day daily series for each history-like one), identified with the studio's own Wikipedia bot name; (3) the studio's daily YouTube Data API scan of 23 reference channels (`data/channels/2026-W47.json`, 06:00 UTC today); (4) the studio's demand check (`run.py demand`, autocomplete plus pageviews, no YouTube quota spent).
- Failures, recorded: the first two Wikimedia runs were refused with HTTP 429 (rate limit) under a generic client name; with the studio's bot name and 2 s between requests the third run had 0 errors.

## Findings
**Google Trends (50 trending searches in US, GB, IN, CA, AU):** none is a history or legend topic. The 5 that matched history words were news: "us iran war" (IN, 2000+ searches), a missing child in Saskatoon (CA), the death of a children's TV presenter (AU), a footballer (AU), Thanksgiving travel (US). Daily Google trends are news and sport; they are not a source of topics for this channel.

**Wikipedia (most-read 21 Nov 2026, 15 history-like articles, rise = average of the last 7 days over the 28 before):**
| Article | Read 21 Nov | Last 7 days / day | Before / day | Rise | Fit for the channel |
|---|---|---|---|---|---|
| Murder of Steven Cozzi (2023) | 48,734 | 8,363 | 455 | 18.4x | No: a recent crime with private people and living families |
| The Nightingale (2015 novel) | 18,777 | 17,705 | 1,043 | 17.0x | No: fiction |
| **Maximilian I of Mexico** | 23,624 | 27,810 | 3,903 | **7.1x** | **Yes: 19th-century emperor, a documentary-length story** |
| P versus NP problem | 14,512 | 3,521 | 2,262 | 1.6x | No |
| Queen Victoria, Cleopatra, World War II, Elizabeth II | 11,000 to 19,000 | steady | steady | about 1.0x | Evergreen, not trending |

**YouTube (reference channels, fastest videos of the last 14 days, official API):** Forgotten History "Why The U.S. Marines Became the World's Most Feared Fighting Force" (score 32.0, 163,580 views), "One SAS Soldier Against an Army of Terrorists" (16.9), "The USS Akron: America's Deadliest Airship Disaster" (10.4); Uncharted Mysteries "The 12,000 Year Old Megaliths Nobody Can Explain" (3.45, 460,091 views); Kings and Generals "10,000 Nubian Archers..." (2.47). Military disasters and ancient mysteries are what moves on similar channels this fortnight.

**Studio demand check:** Maximilian I of Mexico 0.749 (autocomplete 5/10; Wikipedia 9,859 a day over 30 days, 6.2x the 30 before). For comparison the highest queued evergreen topics score 0.89 (The Lost Roanoke Colony), 0.88 (Codex Gigas), 0.84 (Mohenjo-daro): more searched, but not rising.

## Recommendation for the documentary (sub-plan 5)
- **Maximilian I of Mexico**: the only measured riser that fits. Rich sources (an Austrian archduke made emperor after a doubtful referendum, the French withdrawal, Carlota's journey to Europe, the court-martial and execution at Querétaro in 1867), enough for 20 to 25 minutes from two or more articles. Not made or queued before (checked `output/`, `output_old/` and the queue).
- Alternative: The Lost Roanoke Colony, the strongest evergreen demand.
- Not known: WHY Maximilian is being read now. A web search found no news event in November 2026; the rise is measured, its cause is not.

## Limits
- Wikipedia pageviews measure reading, not YouTube searches; the demand score is the studio's own estimate, not a Google or YouTube number.
- The history filter is a keyword match on article descriptions; it can miss topics with plain descriptions.
- YouTube Studio's own Trends tab (no API) was not read: it needs the owner's Chrome, attended.
