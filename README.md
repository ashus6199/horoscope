# Elemental Horoscope Video Pipeline

Automated daily short-form horoscope video pipeline — see `PRD.md` for full
requirements/phased plan, and `AGENTS.md` for standing project context.

## Structure
```
manifest/        clip metadata (element tags, last-used rotation)
scripts/          pipeline steps: pick clip, generate horoscope, TTS
remotion/         video assembly (background + captions + audio)
```

## Setup
```bash
pip install -r requirements.txt
cd remotion && npm install
```

## Sprint 1 — content generation (run from scripts/)
```bash
python3 pick_clip.py --element fire --manifest ../manifest/manifest.json --mark-used

export OPENAI_API_KEY=sk-...
python3 generate_horoscope.py --sign Sagittarius --element fire

python3 generate_tts.py --text "<generated text>" --output ../output/sagittarius.mp3
```

## Sprint 2 — render (run from remotion/)
Put your real background clip + audio into `public/assets/`, then:
```bash
npx remotion render src/index.ts HoroscopeVideo out/sagittarius.mp4 --props=example-props.json
```
Edit `example-props.json` with the real `captionText`, `backgroundVideoPath`,
`audioPath`, and `durationInSeconds` (from `generate_tts.py`'s output) first.

## Not yet built
Publishing (Instagram Reel + Story-from-Reel, YouTube Short), GitHub Actions
orchestration/cron, multi-account credential setup. See `PRD.md` Sprints 3-7.
