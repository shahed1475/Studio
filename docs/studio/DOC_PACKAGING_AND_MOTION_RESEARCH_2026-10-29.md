# Documentary packaging, voice, loudness and free 3D/2D motion: research record (29 Oct 2026)

Asked by the owner for the Cambyses documentary: research how to make a thumbnail people are curious to click, check the voice speed and sound of the other videos, and follow the earlier research on free 3D and 2D animation; keep the pictures as they are; store how it was done so Autopilot can repeat it. This file adds to `VIDEO_CRAFT_RESEARCH_2026-10-29.md` (which holds the YouTube Help sources on thumbnails, retention and the 3D options) and does not repeat it.

Labels follow CLAUDE.md section A: `VERIFIED` (a page was read or a thing was measured), `PARTIALLY_VERIFIED`, `CONFLICTING`, `UNVERIFIED`. Web search results here are mostly vendor blogs and forums; they are labelled as such and nothing below claims a technique raises views.

## 1. What ranks for this story today (measured: YouTube Data API, public metadata, 10 results for "lost army of cambyses")

| Video (views, channel size, length) | What its thumbnail shows (8 viewed) |
|---|---|
| "The Ancient Army Of 50,000 Men That Vanished" (1.6 M views, 5.9 M subscribers, 48 min) | A rider on a horse in sand; the channel name only. |
| "Finding The Remains Of 50,000 Persian Soldiers That Vanished In A Sandstorm" (765 k, 548 k subscribers, 49 min) | A large skull in front, marching silhouettes in a haze, text "50,000 MEN VANISHED". |
| "Ancient Lost Army Found?" (Discovery, 407 k, 3 min) | A photo of a pile of bones, no text. |
| "The Ancient Army That Disappeared Without A Trace" (34 k, 291 k subscribers, 49 min) | A bearded king's face, text "VANISHED PERSIAN ARMY". |
| Small channels (56 to 5,161 views, 1 to 31 min) | "NEVER FOUND" over a wave of sand; "THE LOST ARMY WHAT HAPPENED?"; "WHERE ARE THEY? 50,000 MEN VANISHED" with a king and an army. |

Label: VERIFIED (read from the API and the thumbnails). What it shows: the ones that do well are 48 to 49 minutes long from channels with hundreds of thousands of subscribers, so views here say little about the thumbnail alone. **Observed patterns, not causes:** one large focal object (skull, face, wall of sand); two to four words of text built on the number and a verb (50,000, vanished, never found, where are they); and every thumbnail uses the same warm orange and brown, so composition and contrast are the only things that set one apart.

## 2. What the search results say about curiosity thumbnails (PARTIALLY_VERIFIED: vendor blogs and forums, no peer-reviewed study found)

- "Hide the answer, not the topic": give enough to understand what the video is, keep back what only the video tells. Several sources agree; none measured it.
- Short bold text, one focal point, believable emotion over a generic shocked face; a misleading thumbnail may win the click and lose retention.
- One summary reports a title analysis of 3,357 mature videos finding curiosity-gap titles do not reliably get more views. Secondary summary only; it concerns titles.
- Typical click rate is quoted as 2% to 10% depending on niche and source. Anecdotal.
- A "+2 to 3 times" lift for curiosity gaps and a "same reward pathway as food or money" claim have no checkable source: **not used**.

**What the studio takes from it (design rules, labelled as the studio's judgement):** (1) one focal point; (2) text of 2 to 4 words that adds something the title lacks and offers a choice instead of giving the answer; (3) only what the video really contains; a legend is shown as a legend; (4) colour that stands out from the crowded warm desert look (a dark storm against one bright gold element); (5) read it at 120 pixels; (6) make two or three versions that differ in one big thing and let YouTube's Test & Compare (Studio, by hand, decided by watch time) judge.

## 3. Voice speed and sound of every video (VERIFIED: measured on the server, 29 Oct 2026, `ffmpeg ebur128`, `words.json`)

- Documentaries (10): speech speed 149 to 169 words per minute (median about 152); with the pauses between lines included 133 to 148.
- Shorts (15): 140 to 176 words per minute of speech; the energetic Cambyses Short 176.
- Loudness: almost every video sits at -16.0 to -16.5 LUFS; Bell Witch, Delphi, Pied Piper, Voynich and the energetic Short at -14.8 to -15.2. Loudness range 3.4 to 3.8 LU, true peak -1.0 to -1.5 dBFS (no clipping).
- Rules of thumb found (vendor calculators and audiobook guides, **no peer-reviewed source**): measured documentary narration about 110 to 130 words per minute, standard narration 140 to 160. Our speech speed is at or above the standard band, and the all-in speed is near 135, so the voice speed is not the problem. The Short's lag was dead air (fixed earlier today).
- YouTube's Help describes Stable volume (on by default for most viewers, not for every video, off with Voice boost) and does not state a LUFS target (VERIFIED, support.google.com/youtube/answer/14106294 and 16619284). Forums and blogs say about -14 LUFS integrated, that louder videos are turned down, and quieter ones are not boosted; one source says the opposite. **PARTIALLY_VERIFIED, conflicting.** Consequence: at -16 a video is at most 2 dB quieter than one at -14. The channel is calm bedtime listening, so the default (-16) is left for the owner; this documentary is set to -14 (inside the reviewer's -17.5 to -12) so it is not the quiet one next to the others.

## 4. Free 3D and 2D motion (follows the earlier research, Point 1)

- Depth Anything V2 Small: Apache-2.0 (VERIFIED, model card of `onnx-community/depth-anything-v2-small` reads "license: apache-2.0", base model `depth-anything/Depth-Anything-V2-Small`; the authors' README says only Small is Apache-2.0). File used: `onnx/model_uint8.onnx`, 27,258,801 bytes, SHA-256 `fcf51f1b230362b28690bb9d1809bf0431f29cad20534e3f589bd7285547f20d` (measured when downloaded). ONNX is a data format, not code. Runs on a CPU: 0.34 s per picture on this PC.
- Method (PARTIALLY_VERIFIED: glossary pages and a research paper's excerpts): a depth map says how near each pixel is; near parts move more than far parts when the camera moves, which reads as depth; the problem is disocclusion at depth edges, so the move is kept small.
- The server has Pillow and ffmpeg but no numpy or onnxruntime. Decision: the depth maps are made on the owner's PC (or any machine with the model) and stored as small pictures in `cache/depth/`; the server only needs Pillow to warp a picture and ffmpeg to encode it. A video with no depth map gets an approximate depth (far at the top, near at the bottom) and is labelled so. No server dependency is added; a server job to make depth maps itself would need the owner's yes.
- 2D animation: chapter title cards and date badges drawn as animated ASS subtitles (vector shapes, fades, moves), burned in by the existing renderer. Everything shown is text already in the script or the chapter list.
- Not used: paid image-to-video clips (about $0.24 each; credit is $2.00), Blender (no GPU on the server), 3D stereo uploads.

## Limits
Nothing here shows the new motion or thumbnail will raise clicks or watch time. The depth map is an estimate from one picture and can be wrong on an unusual scene; the move is small so a wrong estimate looks like a slight wobble, and every scene is looked at after the render.
