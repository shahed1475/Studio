# Brief for Claude (free web plan): write a spec, the studio builds the video for $0

You do the thinking and writing. The studio does the rest (voice, pictures, render, thumbnails). **Read only this file** (the rest of the repo is large). You never upload, publish, approve or change channel settings, and you put no keys or secrets in the repo.

## What you produce: one folder `specs/inbox/<name>/` (`<name>` = lowercase letters, digits, dashes)
- `doc.json` (a 16:9 film, 8 to 10 minutes) **or** `short.json` (a 9:16 Short, under 58 seconds)
- `pictures.json`: one picture prompt per scene: `[{"id":"p01","prompt":"..."}]` (nothing else needed; the studio draws them free)
- `src/<page>.txt`: each source page saved as plain text. If you can run code: `python tools/fetchsrc.py "Wikipedia page title" --out specs/inbox/<name>/src`. If you cannot, paste the page text you read into the file. **Every passage you quote must be in these files, word for word.**

## doc.json shape
```
{"slug":"...","title":"<=70 chars","topic":"...","kind":"mystery|legend|person|place|event","description":"...","tags":["8 to 12"],
 "thumb_picture":"p05","thumb_hooks":["WHO LIES HERE?","THREE WORDS","..."],
 "lines":[{"chapter":"Chapter title (only on the first line of a chapter)","text":"One spoken sentence or two.","src":["s1"],"picture":"p01"}],
 "sources":[{"id":"s1","title":"Page title - Wikipedia","url":"https://...","passage":"verbatim sentence(s) from the saved page","file":"src/page.txt","read":"YYYY-MM-DD"}]}
```
A Short is the same with 10 to 14 short `lines`, no chapters, and a final `credits` list only if you used one.

## Rules the checker enforces (a failing spec is rejected and nothing is built)
- Line 1 is an open question (who, what, where, why, how) of 14 words or fewer. It names the subject and does not give the answer.
- Film: 400 to 1,500 words (aim 1,100 to 1,400, 50 to 58 lines). Shape: hook, curiosity, story, closing value. **No outro** ("thanks for watching", "subscribe"): the studio adds a subscribe pop-up. Short: the line before the last answers the hook or says what the sources disagree on (never a new question); the last line invites to **subscribe** (never "follow").
- At least 2 sources. Every factual claim (names, dates, numbers, quotations) must be supported by a `passage` that is in the saved page. Anything you cannot source: leave it out. Say what is documented, what is belief and what is disputed. Do not state a dispute as flat fact. Quotations only verbatim and attributed.
- Each line names its `src` ids and a `picture` id from pictures.json. Use many different pictures (about one per line in a film).
- No third-party video, pictures or downloads (do not add keys such as `video`, `images`, `download`).
- Names the voice may mispronounce: `"say": {"Ahmoon": "Amun"}` (one word for one word).

## Picture prompts
Photorealistic documentary photograph, natural light, place or objects, **no people, no faces, no text, no map labels, nothing violent**. Name the place, era, light and one clear subject. A different scene per line.

## Search packaging (YouTube SEO)
- Title: 40 to 62 characters, the 2 to 4 word search phrase in the first 40 characters, no shouting, no promise the film cannot keep.
- Description: the first 150 characters contain the phrase and a real reason to watch; 2 or 3 sentences. (Sources and chapter times are added by the studio.)
- Tags: 8 to 12, the phrase first, then people, places, era. Thumbnail hooks: 3 options, 2 to 5 words each, not repeating the title, honest.

## How it gets built
Push the folder to `main` (or open a pull request; only `main` is read). Within 20 minutes the studio checks it, draws the pictures, and builds a **held draft** (activity feed: "Spec built" or "Spec rejected" with reasons). The owner watches it and releases it. If you cannot push, give the owner the files to paste into the dashboard server folder `data/specs/inbox/<name>/` or the GitHub web editor.

Check before you push, if you can run code: `python run.py specrun check specs/inbox/<name>`.

## One story, one video per format
Do not repeat a story already on the channel (the owner's queue is in the dashboard). One film and one Short per story; a Short may be cut from its film.
