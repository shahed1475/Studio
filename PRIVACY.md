# Privacy Policy for Story Studio

Last updated: 20 October 2026

Story Studio is a personal tool that makes and schedules videos for one YouTube channel. It is run by its owner on the owner's own server. It is not a public service and has no other users.

## What it accesses
When the owner connects the channel, Google asks for two permissions:
- **Upload videos to YouTube** (`youtube.upload`), to upload and schedule the owner's own videos.
- **Read YouTube channel data** (`youtube.readonly`), to read the channel's own numbers such as subscribers, views and video list so the tool can show progress, to confirm after each upload that YouTube stored the title, privacy setting and scheduled time that were sent, and to check after the publish time that the video became public and has no claim or block. It is never used to change anything.

## How the data is used and stored
- The Google sign-in token is stored in a private file on the owner's own server. It is used only to upload videos and read channel numbers for that channel.
- Nothing is sold, shared with other people, used for advertising, or sent to any third party.
- Videos, scripts and settings stay on the owner's server. Text of scripts may be sent to an AI model provider (OpenRouter) to write them; no Google user data is sent there.
- Story Studio's use of information received from Google APIs follows the [Google API Services User Data Policy](https://developers.google.com/terms/api-services-user-data-policy), including the Limited Use requirements.

## Your choices
The owner can remove the app's access at any time at https://myaccount.google.com/permissions, or press "Disconnect" in the app, which deletes the stored token.

## Contact
Open an issue at https://github.com/shahed1475/Studio/issues.
