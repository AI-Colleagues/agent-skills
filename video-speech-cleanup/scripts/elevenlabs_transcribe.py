#!/usr/bin/env python3
"""Transcribe local media with ElevenLabs Scribe v2 and save JSON/text outputs."""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import ssl
import sys
import uuid
from pathlib import Path
from typing import Any
from urllib import request

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from env_loader import find_env_value  # noqa: E402


API_URL = "https://api.elevenlabs.io/v1/speech-to-text"


def _multipart(fields: dict[str, str], file_path: Path | None) -> tuple[bytes, str]:
    boundary = f"----video-speech-cleanup-{uuid.uuid4().hex}"
    chunks: list[bytes] = []

    for name, value in fields.items():
        chunks.extend(
            [
                f"--{boundary}\r\n".encode(),
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode(),
                value.encode(),
                b"\r\n",
            ]
        )

    if file_path is not None:
        mime = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
        chunks.extend(
            [
                f"--{boundary}\r\n".encode(),
                (
                    f'Content-Disposition: form-data; name="file"; '
                    f'filename="{file_path.name}"\r\n'
                ).encode(),
                f"Content-Type: {mime}\r\n\r\n".encode(),
                file_path.read_bytes(),
                b"\r\n",
            ]
        )

    chunks.append(f"--{boundary}--\r\n".encode())
    return b"".join(chunks), boundary


def transcribe(
    *,
    api_key: str,
    file_path: Path | None,
    source_url: str | None,
    model_id: str,
    language_code: str | None,
    diarize: bool,
    no_verbatim: bool,
    seed: int | None,
    timeout: int,
) -> dict[str, Any]:
    """Call the ElevenLabs synchronous speech-to-text endpoint."""
    if (file_path is None) == (source_url is None):
        raise ValueError("Provide exactly one of file_path or source_url.")

    fields = {
        "model_id": model_id,
        "timestamps_granularity": "word",
        "diarize": str(diarize).lower(),
        "no_verbatim": str(no_verbatim).lower(),
    }
    if language_code:
        fields["language_code"] = language_code
    if seed is not None:
        fields["seed"] = str(seed)
    if source_url:
        fields["source_url"] = source_url

    body, boundary = _multipart(fields, file_path)
    req = request.Request(
        API_URL,
        data=body,
        headers={
            "xi-api-key": api_key,
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        method="POST",
    )
    context = ssl.create_default_context()
    with request.urlopen(req, timeout=timeout, context=context) as response:
        payload = response.read().decode("utf-8")
    return json.loads(payload)


def write_outputs(result: dict[str, Any], output_json: Path, output_txt: Path | None) -> None:
    """Write transcript JSON and optional text."""
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    if output_txt is not None:
        output_txt.parent.mkdir(parents=True, exist_ok=True)
        output_txt.write_text(str(result.get("text") or ""), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", nargs="?", help="Local audio/video path")
    parser.add_argument("--source-url", help="Hosted audio/video URL")
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-txt")
    parser.add_argument("--api-key")
    parser.add_argument("--model-id", default="scribe_v2")
    parser.add_argument("--language-code")
    parser.add_argument("--diarize", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--no-verbatim", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--timeout", type=int, default=1800)
    args = parser.parse_args()

    file_path = Path(args.input).expanduser().resolve() if args.input else None
    if file_path is not None and not file_path.exists():
        parser.error(f"Input file does not exist: {file_path}")
    api_key, _api_key_source = find_env_value(
        "ELEVENLABS_API_KEY",
        file_path,
        args.output_json,
    )
    api_key = args.api_key or api_key
    if not api_key:
        parser.error("Provide --api-key, set ELEVENLABS_API_KEY, or store it in a nearby .env.")

    result = transcribe(
        api_key=api_key,
        file_path=file_path,
        source_url=args.source_url,
        model_id=args.model_id,
        language_code=args.language_code,
        diarize=args.diarize,
        no_verbatim=args.no_verbatim,
        seed=args.seed,
        timeout=args.timeout,
    )
    write_outputs(
        result,
        Path(args.output_json).expanduser().resolve(),
        Path(args.output_txt).expanduser().resolve() if args.output_txt else None,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
