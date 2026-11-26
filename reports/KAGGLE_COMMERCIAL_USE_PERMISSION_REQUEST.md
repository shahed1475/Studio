# DRAFT: request to Kaggle for written permission (NOT SENT)

Status: draft prepared 24 Nov 2026 by a Claude Code session. **Not sent.** Sending it is the owner's decision. No permission exists until Kaggle answers in writing.
Suggested channel: support@kaggle.com (the address the Terms of Use give for support; the contact page at kaggle.com/contact has no category for commercial-use permission, so "Other" or the e-mail address). Send from the account holder's own e-mail; fill the bracketed fields yourself.

---

**Subject:** Request for written permission: running my own downloaded models on Kaggle Notebook GPUs for a monetised YouTube channel

Dear Kaggle Support,

I run a small YouTube channel that publishes history and legend documentaries. The channel is, or may become, monetised. Before I use Kaggle for any of this work, I would like to know whether it is permitted, because your Terms of Use (version of 22 June 2025) say the Services are for "your own internal, personal, non-commercial use", and your Acceptable Use Policy (22 June 2025) rules out using resources for "activity unrelated to ML data science" and "server farming".

What I would like to do:
1. Run AI models I have already downloaded (open-weight models under licences that allow commercial use, for example Apache-2.0 image and language models) on a Kaggle Notebook with the T4 x2 accelerator.
2. Use them for inference only: generating still images, and possibly narration audio or text checks, for my own videos. No training on Kaggle data, no scraping, no crypto-mining, no long-running servers, no tunnels, and only my single Kaggle account [account name].
3. Work in normal finite notebook sessions within the weekly GPU quota, stopping each session when the batch is finished.
4. Download the resulting files and include them in videos published on my monetised YouTube channel.

My questions:
1. Is this inference and asset-generation workload, whose outputs go into monetised YouTube videos, permitted under the Terms of Use, or does it require a separate written agreement?
2. May I upload model weight files I lawfully obtained (for example as a private Kaggle Dataset or private Model) into a private notebook for this purpose? Is there a size or licence condition?
3. May the generated outputs (images, audio) be used commercially, and does Kaggle claim any right in outputs created in a private notebook?
4. Is generating media assets (rather than training or evaluating models) considered "activity related to ML data science" under the Acceptable Use Policy?
5. Which limits apply: the weekly GPU quota (your documentation says 30 hours or sometimes higher), the 12-hour session limit, 20 GB of saved output in /kaggle/working, internet access in sessions, and any limit on how often sessions may be started?
6. If this use is not permitted, is there a paid or commercial Kaggle offering that allows it?

I will not use Kaggle for this work unless you confirm in writing that it is allowed.

Kind regards,
[Name]
[Kaggle username]
[Channel name and link]

---

## What was verified before writing this (24 Nov 2026, the owner's Chrome, signed out, read only)
- Terms of Use, kaggle.com/terms, version June 22, 2025 (active): "You will only use the Services for your own internal, personal, non-commercial use, and not on behalf of or for the benefit of any third party".
- Acceptable Use Policy, kaggle.com/aup, June 22, 2025: no use of resources for "server farming" or "activity unrelated to ML data science"; no circumventing any aspect of the Services.
- Notebook docs, kaggle.com/docs/notebooks: 12 hours execution for CPU and GPU sessions (9 hours TPU), 20 GB auto-saved disk in /kaggle/working, 4 CPU cores and 30 GB RAM; extra 15/30 GPU hours a week only for linked Colab Pro/Pro+ accounts (an experimental promotion). The page still describes a P100.
- kaggle.com/docs/efficient-gpu-usage: weekly GPU quota "30 hours or sometimes higher depending on demand and resources"; interactive sessions idle-time out after 60 minutes.
- Product announcement 735239 (Kaggle staff, about 3 months old): the P100 was retired on 15 September 2026; T4 x2 (two GPUs, 16 GB each) remains; the L4 is limited to a small set of competitions.
- The account's own quota page was not seen (the browser was not signed in to Kaggle).

This is a reading of published terms, not legal advice.
