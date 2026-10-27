# Trends, timing, training data and the visual mix (27 Oct 2026)

Written after reading the owner's request, the Studio "Trends" tab, YouTube's API pages and the code. Status line for each part: BUILT, STAGED (designed, waits for the owner's yes) or CHECKED (no change needed).

## 1. Trending videos in the niche. BUILT (public API), the Studio tab itself is NOT usable by Autopilot
- The Studio tab "Trends > Get ideas for your next video" shows a short feed of new, well-viewed videos from the niche (title, length, channel, views, age). It is a personalised screen with no API; reading it from the worker would mean browser automation of a logged-in Studio, which this project decided against (fragile, tied to the owner's login). The tab on 27 Oct showed four ancient-mystery documentaries of 25 to 62 minutes at 100K to 320K views.
- The official "Research" tab (searches viewers make, with a "content gap" label) is also Studio-only, English, five countries.
- What Autopilot uses instead: `trendwatch.search_fresh` (YouTube Data API, public numbers only). Videos published in the last 14 days, scored by `outlier_score` = views per day divided by the channel's size (tiny channels floored at 500 subscribers, hidden counts treated as 50,000), so a small channel that is taking off ranks above a giant with the same views. Documentaries (4 minutes or more) and Shorts (90 seconds or less) are searched separately. Cost: 4 searches a day (400 quota units of the usual 10,000), once a day, recorded in the weekly digest under `fresh`, with a length hint.
- `topicrank.signals` gives such a video up to double the weight of an old hit with the same views. The choice of topic still goes through the existing checks: source article must exist, premise check, one story one video per format, the pace governor.
- The Studio feed stays a human-assisted source: the owner can ask an assistant session to read it and add topics to the queue.

## 2. One long video and one Short from the chosen topic. Already how Autopilot works
`topicrank.pop_best` picks a topic; a documentary is made; `clipper.make_next` / `run.py remake-short` cut a Short from it (one story, one video per format). The Short may sit beside its documentary.

## 3. Length, so viewers are not bored. CHECKED, no change
No source gives an official best length; guidance says retention percentage falls as length grows and the right length is what the story needs. Our documentaries are about 6 minutes, Shorts about 57 seconds. The trend feed shows long videos (25 to 62 minutes) working for big channels, but this channel has 6 subscribers and no retention curve long enough to justify longer. The digest now records the typical length of what is taking off (`fresh.hint`) so a later decision uses data. Rule kept: a video ends when its story ends.

## 4. Posting and upload timing. CHECKED, no change
Documentaries 18:00 US Eastern, Shorts 12:30 US Eastern, uploaded private 12 hours ahead, finished and reviewed 2 hours ahead, made starting 12 hours before that. Basis: published analyses of about 300,000 videos put long-form in evenings and Shorts at lunch, recommend publishing 2 to 3 hours before the peak so HD processing and indexing finish, and say the effect of the exact hour is small next to thumbnail, title and retention (and YouTube says publish time does not change long-term performance). Uploading 12 hours ahead also lets copyright claims show up while the video is still private. The channel's own audience-by-hour report has too little data at 6 subscribers; re-check it after about 1,000 views a week.

## 5. Training a small model. FIRST STEP BUILT (data), training is the owner's step on the owner's GPU
- Owner's hardware: GeForce GTX 1050 Ti, 4 GB. That fits QLoRA fine-tuning of models of about 0.5 to 1.5 billion parameters on short examples (a short packaging task: title, description lead, tags, thumbnail words). It does not fit a script writer (a script example is about 4,000 tokens with its source text). No rented GPU, as the owner decided.
- Honest limits: one rule blocks the obvious data. Anthropic's commercial terms forbid using its services to train competing models unless it approves, and every script so far was written by Claude. `trainset.py` therefore excludes Claude output and any video whose writer was not recorded (the writer model is now recorded in each new script, `script_model`). Usable data comes from open-licence writer models (Llama, Qwen and similar via OpenRouter), human-written or human-edited text, or after Anthropic's approval. Wikipedia text is CC BY-SA, so the set carries attribution and stays private.
- Size: practitioner guidance is a few hundred clean examples for style. At two examples per video that is 150 or more videos from a non-Claude writer: months away at the new pace. Until then the training set only grows; nothing is trained.
- "A model that knows how the whole system works" is not worth training: playbooks and code do that and cannot invent it. A small model is for narrow repeatable jobs only, and the fact-checker and reviewer stay strong models.
- `run.py trainset` builds and checks (schema, size, keys and tokens, emails, markup, copied-from-source, exact and near duplicates, claim ledger, provenance, train/validation split by video) with no network and no cost. Next steps, each needing the owner: (a) an `HF_TOKEN` copied to the server with `scp` for a private dataset push; (b) a choice of the writer model whose output may be used; (c) a training script run on the owner's computer.

## 6. Footage and visuals mixed to the story's emotion. STAGED
Designed, not built (needs the owner's yes because it changes how every video renders and costs money per scene):
1. A scene planner turns each script line into an emotion and a picture kind: real archive footage or photo (public domain: Wikimedia Commons, Internet Archive, NASA, Library of Congress), AI picture, AI clip, 3D, 2D, or a data card (timeline, map, chart, comparison) when the line carries numbers or dates.
2. Real footage only with recorded provenance and licence (the licence check already exists); licensed or public-domain material can still receive a Content ID claim, so every clip's source stays on record and uploads stay private for 12 hours first.
3. Quality gate: a resolution and sharpness check on every picture and clip before render, on top of the existing frame review.
4. A "what is different here" step before writing: compare the chosen topic with the top fresh videos and competitors, and require one angle none of them has (source-based, what is known versus legend).
Cost control: the planner is rules plus one cheap-model call per video; paid clips stay budgeted as now (`house_style` budgets).

## Owner decisions that remain
- Approve the visual-mix design (section 6) so it can be built.
- Name the writer model whose output may be used for training, or approve asking Anthropic.
- Put an `HF_TOKEN` on the server only if a private dataset push is wanted.
