# ElevenLabs Notes

Use `POST https://api.elevenlabs.io/v1/speech-to-text` with multipart form data.

Core fields:
- `model_id=scribe_v2`
- `file=@<audio-or-video>` for local files, or `source_url=<url>` for hosted media.
- `timestamps_granularity=word` for word-level QA spans.
- `diarize=true` when speaker IDs matter.
- `language_code=<ISO code>` only when known.
- `seed=<int>` for best-effort deterministic sampling.
- `no_verbatim=false` for the primary QA transcript.

Use `no_verbatim=true` only for a secondary comparison transcript. It removes filler words, false starts, and non-speech sounds, which is useful for readable text but can hide evidence needed for cut labels.

Save the full JSON response, not just `text`, because `words[]` contains `text`, `start`, `end`, `type`, and optional speaker/logprob fields.
