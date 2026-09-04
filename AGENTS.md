# AGENTS.md — Elemental Horoscope Video Pipeline

## What this project is
An automated pipeline that generates a daily 35-50s horoscope short-form video
per zodiac sign, publishes it as an Instagram Reel + auto-shared Story, and as
a YouTube Short. Currently validating the full pipeline end-to-end on a single
sign (Sagittarius) before scaling to all 12. Full requirements and phased plan
are in `PRD.md` — read that first for context on what phase we're in.

## Current status
- Sprint 1 (content generation) done and tested: `scripts/pick_clip.py`,
  `scripts/generate_horoscope.py`, `scripts/generate_tts.py`
- Sprint 2 (video assembly) in progress: `remotion/` composition built,
  renders correctly given real props, not yet wired to real pipeline output
- Not yet started: publishing (IG Reel + Story-from-Reel, YouTube Short),
  GitHub Actions orchestration, multi-account scale-out

## Standing rules
- Every pipeline step must run unattended, no manual editing or manual
  triggering steps. If a task would require a human to click something in an
  app UI, flag it rather than silently working around it.
- Keep scripts CLI-driven with clear argparse flags and JSON stdout output,
  matching the existing scripts — this pipeline will be orchestrated by
  GitHub Actions, not run interactively.
- Video duration must always be derived from the actual TTS audio duration,
  never hardcoded — see `remotion/src/Root.tsx`'s `calculateMetadata`.
- Voice is fixed: `en-GB-SoniaNeural`, rate `-8%`, pitch `-4Hz`. Don't change
  without asking.
- The "Pokemon" / creature-video concept is a placeholder, not final IP —
  don't hardcode Pokemon names/references into code; keep it generic
  ("element", "creature", "clip") so it's easy to reskin later.
- Target horoscope length: 85-145 words (≈35-50s spoken across 5 visual cards).
- Prefer editing/extending existing scripts over introducing new frameworks
  or dependencies not already in `requirements.txt` / `remotion/package.json`.
- When touching credentials/secrets (IG tokens, YouTube OAuth, API keys),
  never hardcode them — read from environment variables, and note in code
  comments which GitHub Actions secret name is expected.
