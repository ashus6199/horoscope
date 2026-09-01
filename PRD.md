# PRD: Elemental Horoscope Short-Form Video Pipeline

**Owner:** Tosh
**Status:** Draft — Phase 1 in planning
**Last updated:** 2026-09-01

---

## 1. Overview

An automated pipeline that generates and publishes a daily 15-30 second short-form horoscope video for each of the 12 zodiac signs. Each sign has its own Instagram account and YouTube channel ("page"). Each day, the pipeline:

1. Picks an elemental creature video clip matching the sign's element from a tagged repository (element-creature concept is a **placeholder**, subject to reskinning before public launch — see Risks).
2. Generates a short AI horoscope script for that sign.
3. Converts the script to speech in an elegant, mysterious female voice.
4. Renders a final vertical video: background clip + burned-in captions + voiceover, fully automated (no manual editing).
5. Publishes the video as a Reel on Instagram and a Short on YouTube.
6. Auto-shares the published Reel to that account's Instagram Story, as a same-day teaser/reminder.

**North star:** Zero manual intervention after setup. A cron trigger at 7am produces and publishes 12 finished videos with no human touching a single step.

---

## 2. Goals

- Fully automated, no-touch daily publishing across 12 IG + 12 YouTube accounts.
- Consistent output quality (audio sync, caption timing, video framing) without per-video manual editing.
- Reliable enough to run unattended for weeks without breaking silently.
- Cheap to operate: free/low-cost TTS, free-tier hosting/compute where possible.

## 3. Non-goals (for now)

- Interactive Story stickers (link/poll) — not supported by Instagram's API; out of scope until Meta adds it.
- Original creature art/IP — placeholder Pokemon-style content only; final IP decision deferred.
- Analytics dashboard, engagement tracking, A/B testing of scripts — later phase at earliest.
- TikTok or other platforms — IG + YouTube only for v1.

---

## 4. Sign → Element Mapping

| Element | Signs |
|---|---|
| Fire | Aries, Leo, Sagittarius |
| Earth | Taurus, Virgo, Capricorn |
| Air | Gemini, Libra, Aquarius |
| Water | Cancer, Scorpio, Pisces |

---

## 5. System Architecture (v1)

```
[Video Repo: bucket + manifest.json, tagged by element]
        |
        v
[Daily Orchestrator: GitHub Actions cron, matrix job per sign]
        |
   1. Pick clip (element match, least-recently-used)
   2. Generate horoscope text (LLM API, 15-30s target length)
   3. TTS (Edge-TTS, tuned voice) -> audio file + duration
   4. Remotion headless render (clip + captions + audio, sized to audio duration)
   5. Upload rendered video to public bucket URL
   6. Publish Reel (Instagram Graph API)
   7. Share published Reel to Story (Instagram Graph API)
   8. Upload as YouTube Short (YouTube Data API v3)
        |
        v
[Per-sign credentials store: GitHub Actions Secrets]
[YouTube quota split across 3-4 GCP projects, ~3-6 channels each]
```

---

## 6. Key Risks & Open Constraints

| Risk | Detail | Mitigation |
|---|---|---|
| IP/copyright | Pokemon-styled content risks takedown/ban at scale once public | Placeholder only; decide on original creature designs before Phase 2 rollout |
| IG Story stickers | No link/poll stickers via API | Story is a plain teaser clip with baked-in text, not a tappable link |
| YouTube quota | ~1,600 units/upload; 10,000/day per GCP project caps ~6 channels/project | Split 12 channels across 3-4 GCP projects |
| Meta App Review | `instagram_business_content_publish` needs review | One review covers all 12 IG accounts once approved; budget 2-4 weeks lead time |
| Token expiry | IG long-lived tokens (~60 days), YouTube refresh tokens | Add a token-refresh/health-check step before Phase 2 scale-out |
| Silent pipeline failure | Unattended daily run could fail without anyone noticing | Add failure notification (e.g. GitHub Actions failure email/Slack) in Phase 1 |

---

## 7. Phased Delivery Plan (Scrum)

### Phase 1 — Single-Sign Validation (Sagittarius)
**Goal:** Prove the entire pipeline end-to-end, unattended, for one account before spending setup effort on the other 11.

**Sprint 1 — Content Generation Foundation**
- Story 1.1: As the pipeline, I can select a fire-element clip from a tagged manifest that hasn't been used recently.
  - AC: manifest JSON with element tags + last-used date; picker script returns a valid, unused-in-N-days clip path.
- Story 1.2: As the pipeline, I can generate a 15-30s horoscope script for Sagittarius via an LLM API call.
  - AC: prompt enforces word count band (~40-70 words) and a mysterious/elegant tone; output validated for length before proceeding.
- Story 1.3: As the pipeline, I can convert the script to speech in an elegant, mysterious female voice and get the audio's exact duration.
  - AC: Edge-TTS call produces an audio file; duration is programmatically extracted for downstream sizing.

**Sprint 2 — Automated Video Assembly**
- Story 2.1: As the pipeline, I can render a finished vertical video with no manual editing, given a clip, captions, and audio as input props.
  - AC: Remotion composition accepts a props JSON (clip path, caption text, audio path); headless CLI render produces an .mp4 with correct duration and burned-in captions, run start-to-finish via one command/script.
- Story 2.2: As the pipeline, I can size the caption timing and clip length to match the audio duration automatically.
  - AC: no hardcoded scene durations remain; changing the audio length changes the render output correctly without code edits.

**Sprint 3 — Publishing Automation (Sagittarius account only)**
- Story 3.1: As the pipeline, I can upload the rendered video to a public bucket URL usable by the IG and YouTube APIs.
  - AC: uploaded file is reachable via public HTTPS URL; used successfully as `video_url` in a test IG container.
- Story 3.2: As the pipeline, I can publish the video as an Instagram Reel on the Sagittarius account.
  - AC: container created, polled to FINISHED, published; post is live and inspectable via the Graph API.
- Story 3.3: As the pipeline, I can auto-share that published Reel to the account's Instagram Story.
  - AC: Story container references the just-published Reel media (no separate story asset needed); Story is live.
- Story 3.4: As the pipeline, I can upload the same video as a YouTube Short on the Sagittarius channel.
  - AC: video appears correctly tagged as a Short (vertical, <3 min); quota usage logged.

**Sprint 4 — Orchestration & Unattended Reliability**
- Story 4.1: As the pipeline, I run automatically every day at 7am IST via a scheduled job with zero manual trigger.
  - AC: GitHub Actions `schedule:` cron fires at the correct UTC-offset time; full pipeline runs end-to-end unattended.
- Story 4.2: As the operator, I get notified if any pipeline step fails, instead of silently missing a day.
  - AC: failed job triggers a visible notification (Actions failure email at minimum).
- Story 4.3: As the operator, I can confirm the pipeline ran correctly for N consecutive days without intervention before moving to Phase 2.
  - AC: defined validation window (e.g. 5-7 consecutive successful unattended runs) as the exit criterion for Phase 1.

**Phase 1 exit criteria:** Sagittarius account receives a correctly formatted Reel + auto-shared Story + YouTube Short, unattended, at 7am, for the full validation window, with no manual steps and no silent failures.

---

### Phase 2 — Scale to All 12 Signs
**Goal:** Replicate the validated pipeline across the remaining 11 accounts without re-deriving the architecture.

**Sprint 5 — Multi-Account Infrastructure**
- Story 5.1: As the pipeline, I can run the same logic across all 12 signs via a matrix job, each using its own account credentials.
  - AC: GitHub Actions matrix strategy parameterized by sign; secrets namespaced per account; no shared-state bugs between signs.
- Story 5.2: As the operator, I have 3-4 separate GCP projects set up so YouTube quota never blocks a day's uploads.
  - AC: channels distributed so no single project exceeds ~6 uploads/day; documented mapping of channel → project.

**Sprint 6 — Credential & Account Setup**
- Story 6.1: All 12 Instagram accounts are Business/Creator, linked to Pages, and granted access to the single reviewed Meta app.
- Story 6.2: All 12 YouTube channels have valid OAuth refresh tokens stored as scoped secrets.
- Story 6.3: Video manifest is populated with enough tagged clips per element to avoid visible repetition across signs sharing an element.

**Sprint 7 — Full-Scale Validation**
- Story 7.1: As the operator, I confirm all 12 accounts post correctly, unattended, for a full validation window.
  - AC: same exit criterion as Phase 1, applied per-account; any account-specific failures triaged before calling Phase 2 done.

---

### Phase 3 — Hardening & Polish (post-launch, lower priority)
- Token refresh automation (IG long-lived token renewal, YouTube refresh-token health checks).
- Basic run-history logging (what was posted, when, to which account) for debugging without digging through Actions logs.
- Revisit the creature-IP placeholder decision before any public/marketing push.
- Optional: engagement-based clip rotation, script quality review sampling, Story link-sticker support if Meta adds it.

---

## 8. Success Metrics

- **Reliability:** ≥95% of scheduled daily runs complete all steps (script → TTS → render → IG Reel → IG Story → YouTube) with zero manual intervention.
- **Latency:** Full 12-sign run completes well within the morning window (define target, e.g. under 30 minutes total).
- **Cost:** TTS and hosting stay within free/near-free tiers as scoped (Edge-TTS, free-tier bucket storage).
- **Zero silent failures:** every failed run produces a notification within the same run.
