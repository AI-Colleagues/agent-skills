---
name: video-speech-cleanup
description: Local video speech cleanup with ElevenLabs Scribe v2, OpenAI LLM labeling, auto-editor, and FFmpeg. Use when Codex needs to remove silences, filler words, catchphrases, stutters, false starts, or repetitions from local audio/video files while saving QA artifacts such as normalized sources, extracted audio, transcripts, word timestamps, removal labels, manifests, and final renders.
---

# Video Speech Cleanup

## Overview

Use this skill for local-machine cleanup of speech-heavy videos. Prefer the bundled scripts over building an Orcheo workflow unless the user needs hosted triggers, queues, dashboards, or multi-user execution.

Default providers:
- ElevenLabs Scribe v2 for verbatim transcription and word timestamps.
- OpenAI for structured removal labeling over the verbatim transcript.

Use a verbatim transcript for QA and cut labelling. Generate `no_verbatim` only as a comparison artifact because it can suggest cleanup areas, but it must not replace the verbatim timestamp source.

## Quick Start

1. Confirm required local tools:
```bash
command -v ffmpeg
command -v ffprobe
command -v auto-editor
```

If tools are missing, ask before installing, then read `references/local_setup.md`.

2. Confirm both credentials are available through CLI flags, a nearby `.env`, or the current shell environment:
- `ELEVENLABS_API_KEY`
- `OPENAI_API_KEY`

3. Run a preflight before processing media:
```bash
python3 /path/to/video-speech-cleanup/scripts/process_video.py \
  /path/to/input.mp4 \
  --output-root /path/to/qa-runs \
  --check-only
```

If preflight reports missing tools or API keys, stop and tell the user exactly what to set or install. Resume only after the user confirms the environment is ready.

4. Run the complete pipeline:
```bash
python3 /path/to/video-speech-cleanup/scripts/process_video.py \
  /path/to/input.mp4 \
  --output-root /path/to/qa-runs
```

5. Inspect the run folder before trusting the final render:
```text
runs/<video-stem>-<timestamp>/
├── manifest.json
├── input/source_video.*
├── input/normalized_source.mp4
├── input/normalize_source.log
├── input/ffprobe.json
├── input/normalized_ffprobe.json
├── audio/extracted.wav
├── audio/normalized.wav
├── silence/silence_removed.mp4
├── silence/auto_editor.log
├── transcripts/elevenlabs_verbatim.json
├── transcripts/elevenlabs_no_verbatim.json
├── transcripts/words.csv
├── transcripts/transcript_verbatim.txt
├── transcripts/transcript_clean.txt
├── labels/removal_labels.json
├── labels/removal_labels.csv
├── labels/labeler_response.json
├── renders/final.mp4
└── renders/render_validation.json
```

## Workflow

1. Create a timestamped run directory and write `manifest.json`.
2. Copy the source video to `input/` for reproducibility unless the user requests symlinks or no copy.
3. Run `ffprobe` on the original source and save full metadata.
4. Normalize the source into a single-video-stream, single-audio-stream MP4 before any edits.
5. Extract mono 16 kHz WAV with FFmpeg and create a loudness-normalized WAV.
6. Run auto-editor as the first-pass silence remover on the normalized source and save `silence/silence_removed.mp4`.
7. Transcribe normalized audio with ElevenLabs Scribe v2 using word timestamps and diarization.
8. Optionally transcribe again with `no_verbatim=true` for comparison only. Do not feed this comparison transcript into the labeler unless you explicitly opt in.
9. Ask an OpenAI model to label removals over verbatim transcript word indices, then apply a safety filter that rejects long or semantically loaded discourse-marker cuts by default.
10. Render a final cut from the normalized source with accepted labels and validate that the output is not mostly black or structurally broken.
11. Review labels, prompt traces, and rendered outputs. If a cut is questionable, edit `labels/removal_labels.json` and rerun `render_from_labels.py`.

## Scripts

- `scripts/process_video.py`: end-to-end local pipeline with preflight, source normalization, transcription, LLM labeling, render, and validation.
- `scripts/elevenlabs_transcribe.py`: standalone ElevenLabs Scribe v2 transcription helper.
- `scripts/label_removals.py`: label removals from verbatim word timestamps with OpenAI structured output plus a post-label safety filter.
- `scripts/render_from_labels.py`: render a video from accepted label spans and validate the output.

Use `--help` on each script for options.

## References

- Read `references/artifact_schema.md` when changing output files or QA conventions.
- Read `references/elevenlabs.md` when changing ElevenLabs request parameters.
- Read `references/local_setup.md` when installing or troubleshooting required local commands.
- Read `references/environment.md` when checking required environment variables.

## Guardrails

- Do not send video or audio to any provider except ElevenLabs unless the user explicitly changes scope.
- Use OpenAI only on transcript text and timestamp metadata, not raw media.
- Do not use `no_verbatim` as the only labelling source.
- Do not delete intermediate artifacts unless the user explicitly requests cleanup.
- Do not start media processing if required environment variables or commands are missing.
- Treat LLM-proposed removals as QA artifacts with explicit reasoning and confidence, not unreviewable truth.
- Prefer local file paths and local run folders over Orcheo state for large media.
