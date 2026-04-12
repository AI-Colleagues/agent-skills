# Environment

Run this preflight before processing media:
```bash
python3 /path/to/video-speech-cleanup/scripts/process_video.py \
  /path/to/input.mp4 \
  --output-root /path/to/qa-runs \
  --check-only
```

Required:
- `ELEVENLABS_API_KEY`: ElevenLabs API key used by Scribe v2 transcription.
- `OPENAI_API_KEY`: OpenAI API key used for structured removal labeling over transcript text.

Optional:
- `VIDEO_SPEECH_CLEANUP_OUTPUT_ROOT`: default QA run root if the user does not pass `--output-root`.

Lookup order for `ELEVENLABS_API_KEY`:
- explicit `--api-key`
- first `ELEVENLABS_API_KEY` found in a nearby `.env` when walking upward from the current working directory, input path, and output path
- current shell environment

Lookup order for `OPENAI_API_KEY`:
- explicit `--label-api-key`
- first `OPENAI_API_KEY` found in a nearby `.env` when walking upward from the current working directory, input path, and output path
- current shell environment

If a required key is missing, stop before any expensive or destructive work and ask the user to set it in their shell or `.env`:
```bash
export ELEVENLABS_API_KEY="..."
export OPENAI_API_KEY="..."
```

Or add them to a nearby `.env`:
```bash
ELEVENLABS_API_KEY="..."
OPENAI_API_KEY="..."
```

Then ask the user to rerun the request or confirm the variables are available in the current terminal session. Do not print or store secrets in run artifacts.
