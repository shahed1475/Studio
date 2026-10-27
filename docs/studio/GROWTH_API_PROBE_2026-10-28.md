# Growth APIs: what was probed on 28 Oct 2026

Read-only probe from the server with the saved login (`upload.load_creds()`), plus Google's documentation pages read through a fetch tool (which summarises: quotes below are what it returned).

| Question | Result | Evidence |
|---|---|---|
| Token scopes | `youtube`, `youtube.readonly`, `youtube.upload`, `yt-analytics.readonly` | probe output, scope names only |
| Analytics API per-video totals | works: views, averageViewPercentage, estimatedMinutesWatched, subscribersGained (10 videos) | live query, last 90 days |
| Retention curve | works: `audienceWatchRatio` by `elapsedVideoTimeRatio`, 100 points. Early points can exceed 1 (re-watches) | live query |
| Traffic sources | works: SHORTS 431, SUBSCRIBER 115, YT_SEARCH 55, YT_CHANNEL 35, EXT_URL 11, YT_OTHER_PAGE 9 views | live query |
| Unique viewers | **not available**: `uniques` answered "Unknown identifier", `viewerPercentage` is invalid for a per-video query | live query |
| Thumbnail impressions and CTR in the Analytics API | **not available**: not on the Analytics metrics page | developers.google.com/youtube/analytics/metrics |
| Thumbnail impressions and CTR in the Reporting API | **available in the docs**: reach reports `channel_reach_basic_a1` and `channel_reach_combined_a1` with `video_thumbnail_impressions` and `video_thumbnail_impressions_ctr`. Current report ids are `channel_basic_a3` and `channel_traffic_source_a3` | developers.google.com/youtube/reporting/v1/reports/channel_reports |
| Reporting API enabled for this project | **no**: 403 "YouTube Reporting API has not been used in project 711498937155 before or it is disabled" | live call |

Owner step: enable the YouTube Reporting API for that project (console link in the 403 message). Reports only exist from the day the job is created, so the first CTR appears after Google generates the first report (expect about a day or two).

Still unverified: setting a Short's related video, pinning a comment and Test and Compare through the API; the unit of `video_thumbnail_impressions_ctr` (the collector reads values above 1 as percent); that CTR matches Studio within 5% (checked once the first report exists).
