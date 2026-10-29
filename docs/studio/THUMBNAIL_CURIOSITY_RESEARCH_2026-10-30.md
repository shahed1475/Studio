# Thumbnails that make people curious, and do not all look the same: research record (30 Oct 2026)

Asked by the owner: "the thumbnails are looking the same in every video"; research properly how to make a thumbnail unique, attractive, hookable and clicky, so the audience feels curiosity before the click. Adds to `VIDEO_CRAFT_RESEARCH_2026-10-29.md` (YouTube Help sources) and `DOC_PACKAGING_AND_MOTION_RESEARCH_2026-10-29.md` (competitors for one story). Labels as in CLAUDE.md section A. Web results here are mostly vendor blogs; nothing below says a design raises clicks.

## 1. Our own thumbnails (VERIFIED: looked at all ten documentary thumbnails on the server, 30 Oct)
All ten use one template: a white line over a yellow line at the bottom left, on a dark fade, in one font at one size. Only the picture changes, and several pictures show nothing of the story (an old engraving, a street, a bedroom). The owner's complaint is right. Cause: `thumbnail.py` has three layouts (bottom left, centred, left panel) and the yellow accent is a constant.

## 2. What makes curiosity (PARTIALLY_VERIFIED: citation confirmed, details from secondary summaries; the paper's full text was not read)
- Loewenstein 1994, "The psychology of curiosity: a review and reinterpretation", Psychological Bulletin 116(1) 75 to 98: curiosity is a response to a perceived gap between what one knows and what one wants to know. Summaries add: some prior knowledge is needed (no curiosity about what one knows nothing of), it is strongest when the person is partly informed and the gap feels closeable (a good guess, not sure), and it is mildly unpleasant, which is the pull to resolve it.
- Le Quéré and Matias 2025 (Scientific Reports, registered report, meta-analysis of 8,977 headline experiments; the PMC page needs a browser check and was not read, so this is from search summaries): concreteness reconciles the mixed findings on curiosity-gap headlines. Making a headline more concrete raises clicks when it was too vague and lowers them when it was already too concrete. Penn State, CHI 2021: clickbait labels did not predict curiosity; detectors agreed 47% of the time.
- **Design consequence (the studio's reading, not a measured rule):** give one concrete anchor (a number, a year, a named thing) and leave one gap that the viewer can almost answer: a choice between two candidate answers, a number without its explanation, an object without its story. Not vague ("this changes everything"), not complete (the answer in the thumbnail).

## 3. Evidence on thumbnails (mostly absent)
- No peer-reviewed click-through study of thumbnail features was found. Blog figures (a face adds 33%, high contrast adds 38%) have no checkable method and are **not used**. One dataset write-up (1,043 channels over 100,000 subscribers, 11,223 thumbnails, 21 features) uses views per day, not click rate, as its outcome; secondary only.
- YouTube Help (VERIFIED, support.google.com/youtube/answer/16391400): Test & Compare picks by watch time share, up to three variants, and "testing titles and thumbnails that are too similar to each other can cause tests to run for longer"; small differences often give no winner. So variants should differ clearly.
- Outliers in our niche (VERIFIED as observation, YouTube API, 16 recent videos 5 to 600 times their channel's subscriber count, thumbnails viewed): a year or number as the headline ("3100 YEARS AGO", "7,000 BC"), one cinematic scene with one focal point, two to four bold words admitting a mystery ("THEY ALL FAILED", "WE CAN'T EXPLAIN"), sometimes an arrow at the thing to wonder about. Several differ in layout, colour and text position from one another.

## 4. Brand against sameness (UNVERIFIED effect; marketing advice only)
Sources agree on a middle path: keep a few brand constants (a family of colours, one type family, a small mark) and vary the layout and composition per video. One source warns that identical thumbnails lose attention over time; none measured it. The studio keeps the type family and a colour family and varies everything else, and ranks candidates for difference from the channel's recent thumbnails.

## 5. Curiosity devices that stay honest (the studio's list; each must be true to the video)
number or year headline; a choice between two answers the video really weighs; a detail marked with a ring or arrow ("what is that?"); legend against record split; a redacted word only when the video answers it; one object close up. Not allowed: a moment or object the video does not contain, a promised result, a face or emotion the story does not earn (YouTube Help, VERIFIED earlier: misleading thumbnails are a policy problem).

## Limits
All of this is design judgement on weak evidence. The only real test is the owner's Test & Compare on live videos, decided by watch time.
