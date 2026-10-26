# Growth plan, 27 Oct 2026 (research, decisions, what was built)

## 1. Evidence (all from the official YouTube Data API and Studio, public numbers; limits stated)
**Our channel (Studio, 28 days to 25 Oct):** 670 views, 6 subscribers, thumbnail click rate 2.8% on about 2,000 impressions. Shorts gave 79.7% of views and 92 of 98 new viewers; search gave 8.2%. Per video: Shorts hold 50 to 68% of viewers (Skinwalker only 21%), documentaries get 25 to 591 impressions at 1.5 to 2.8% click rate.

**Competitors (457 videos, 356 channels, 24 searches, about 2,400 quota units; English titles only; searching by "most viewed" favours winners, so these are correlations):**
| | winners (20,000+ views) | the rest |
|---|---|---|
| Long: median length | 11:39 | 9:48 |
| Long: titles with a colon or pipe | 38% | 57% |
| Long: median title length / tags | 56 / 20 | 62 / 15 |
| Short: median length | 0:51 | 0:56 |
| Short: question in title / hashtag in title | 22% / 69% | 0% / 58% |

Small channels that broke out did it with a concrete detail in the title (a date, a number, a surprising fact): "(No Rats in the Oldest Version)" 206K views for a 24K-subscriber channel; "What Really Happened on December 27?" 436K for a 4K channel. A close competitor (Legendforgetales, 23.9K subs, about one 9-minute documentary a day) mostly gets 30 to 500 views per video; only high-search topics with a twist break out.
**Thumbnails:** the 16 most-viewed documentary-style thumbnails show one clear subject with a strong mood, saturated or cinematic light, 1 to 4 big words, often an arrow or circle. Ours were archive photos, engravings and maps.
**Not proven:** that any of this raises our views. The first real test is the click rate of Bell Witch, La Llorona and Pied Piper around 29 to 30 Oct.

## 2. Built (commit d2c7830, deployed)
- `aiart.thumbnail_art` and `thumbnail.make_art` / `art_subject`: a freshly drawn picture (about $0.034, capped by the daily budget, cached, labelled with the AI credit) is the first thumbnail; the video's own frames stay as the fallback and as options. Teotihuacan and Heungbu kept their frame-based thumbnails on purpose (the AI pyramid had a temple on top that Teotihuacan's pyramids lack; a swallow did not match the hook).
- Shorts are written to 110 to 135 words (about a minute).
- Titles are asked for a concrete detail from the story and at most two colons, under 60 characters.
- Live: Pied Piper retitled "...The Earliest Accounts Have No Rats" (narration line 4 supports it); thumbnails changed on Pied Piper, Bell Witch, La Llorona (Studio), Delphi pending (below).

## 3. Blocked by YouTube: custom thumbnail limit
Studio showed "One-time verification needed ... to create more custom thumbnails daily". The channel is not phone-verified, so thumbnail changes are limited per day (6 went through on 26 to 27 Oct, the 7th was refused). Delphi and Pied Piper still need their AI thumbnails (files are in the session scratchpad; regenerate with `thumbnail.make_art`). Owner action: verify the channel at youtube.com/verify (needs the owner's phone). Autopilot's own daily upload sets one thumbnail and fits the limit.

## 4. Playwright for the research agent: decision
The research agent already reads YouTube through the official API (search, video statistics, channel size, autocomplete). That gives everything the experiments above needed, with no scraping. A browser inside the worker would add: about 400 MB of Chromium on a shared 4-core server, a new way for untrusted web pages to reach prompts (they must stay data), YouTube page layouts that change, and scraping that YouTube's terms do not allow (the API is the allowed route). It adds little data the API cannot give.
Recommendation: do not install Playwright in the worker. Next steps in order: (1) enrich `seo.competitors` with length, likes, channel size and views per subscriber and show the model the winners' pattern (API only, small change); (2) keep deeper browser research as a Claude session job (Claude in Chrome, a visible window) before big decisions; (3) only if a need appears that the API cannot meet, run Playwright in a separate container with no secrets and no access to the studio's data, returning plain text that is cleaned like any outside text. Owner decides.

## 5. Backlog and measurement
- Compare click rate and views per video on 29 to 30 Oct (Studio, Advanced mode, last 7 days) and keep or revert each packaging change.
- After phone verification: Delphi and Pied Piper thumbnails; consider AI-art thumbnails for Mami Wata after it has data.
- Idea, unproven: Mami Wata and other African legends do very well in French and Wolof (90K+ views from small channels). A French-narrated version would need its own research and review.
- Shorts: watch the share of viewers held; the target is 50 to 68% like the best four.
