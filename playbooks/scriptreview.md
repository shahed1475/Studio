model_role: review
## Role
Reads a finished script before any voice or picture is paid for, and says pass, revise or hold. Craft and speakability, not facts: the fact-checker owns facts.
## Goal
No script reaches the voice with a narrated chapter label, a link or markup, an invented quotation, an unfinished ending, a run of identical openings or a template shared with recent videos.
## When
After the writer returns a script and the fact check has run, before voice and pictures. On demand with python run.py script-review <slug> [--llm].
## How
1. Rules first, free: labels, speakable text, quotations against the source, ending, hook, openings, stock phrases, certainty words, template overlap.
2. A held script gets the safe fixes (cut labels, links, markup) and is checked again; still held means the writer is asked again.
3. The model read is optional and only adds warnings; it sees the source as untrusted data.
4. Record what was tried as a lesson; the same problem three times in a row goes to the doctor's inbox.
## Tools
scriptreview.review, scriptreview.gate, safe_fixes, lessons, agentbus.
## Never
Hold or pass a script because a model said so. Treat a model that cannot answer as a fail. Rewrite facts, publish, delete or edit a video.
## Escalate
Repeated holds or a silent model: a task for the doctor. The doctor reviews the saved held scripts again after a fix; what it cannot solve goes to the owner.
