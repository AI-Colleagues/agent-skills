# QA Artifact Schema

Each run directory should be self-contained and reproducible.

## manifest.json

Recommended fields:
- `created_at`: ISO-8601 UTC timestamp.
- `source_path`: original input path.
- `run_dir`: absolute run directory.
- `tools`: detected versions for `ffmpeg`, `ffprobe`, and `auto-editor`.
- `parameters`: pipeline options such as transcription model, label model, margin, edit expression, language code, prompt hint lists, and validation thresholds.
- `artifacts`: relative paths for produced files.
- `status`: `completed` or `failed`.
- `error`: present when the run fails after the manifest is created.

Recommended artifact entries:
- `source_video`
- `normalized_source_video`
- `normalize_source_log`
- `ffprobe`
- `normalized_ffprobe`
- `extracted_audio`
- `normalized_audio`
- `silence_removed_video`
- `verbatim_transcript_json`
- `verbatim_transcript_text`
- `clean_transcript_json`
- `clean_transcript_text`
- `words_csv`
- `removal_labels_json`
- `removal_labels_csv`
- `labeler_response_json`
- `render_validation_json`
- `final_video`

## removal_labels.json

Top-level shape:
```json
{
  "source": "openai_over_elevenlabs_verbatim",
  "labels": [
    {
      "id": "cut_0001",
      "type": "discourse_marker",
      "text": "这个的话",
      "start": 12.34,
      "end": 12.82,
      "confidence": 0.93,
      "reason": "Standalone discourse marker before the real clause begins.",
      "accepted": true,
      "start_word_index": 148,
      "end_word_index": 151
    }
  ]
}
```

Only labels with `accepted: true` should be rendered by default. Preserve the rest for QA if you extend the schema later.

## labeler_response.json

Recommended contents:
- `provider`: for example `openai`
- `model_id`
- `request_id`: API request identifier when available
- `developer_prompt`
- `user_prompt`
- `raw_response`

## render_validation.json

Recommended contents:
- source and output paths
- source and output durations
- source and output stream counts
- source and output video bitrate when available
- black-frame statistics
- warnings
- errors
