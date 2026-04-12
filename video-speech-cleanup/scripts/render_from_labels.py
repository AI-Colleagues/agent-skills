#!/usr/bin/env python3
"""Render a final cut from accepted removal labels using auto-editor."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


BLACK_DURATION_RE = re.compile(r"black_duration:(?P<duration>\d+(?:\.\d+)?)")


def _accepted_spans(labels_doc: dict[str, Any], padding: float) -> list[tuple[float, float]]:
    spans: list[tuple[float, float]] = []
    for label in labels_doc.get("labels", []):
        if not label.get("accepted", False):
            continue
        start = max(0.0, float(label["start"]) - padding)
        end = max(start, float(label["end"]) + padding)
        if end > start:
            spans.append((start, end))
    spans.sort()

    merged: list[tuple[float, float]] = []
    for start, end in spans:
        if not merged or start > merged[-1][1]:
            merged.append((start, end))
        else:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
    return merged


def _probe(path: Path) -> dict[str, Any]:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def _duration(probe: dict[str, Any]) -> float:
    return float(probe.get("format", {}).get("duration") or 0.0)


def _streams(probe: dict[str, Any], codec_type: str) -> list[dict[str, Any]]:
    return [stream for stream in probe.get("streams", []) if stream.get("codec_type") == codec_type]


def _bitrate(stream: dict[str, Any] | None) -> int | None:
    if not stream:
        return None
    value = stream.get("bit_rate")
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _black_stats(path: Path) -> dict[str, float]:
    result = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-i",
            str(path),
            "-vf",
            "blackdetect=d=0.5:pic_th=0.98",
            "-an",
            "-f",
            "null",
            "-",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    combined = result.stdout + "\n" + result.stderr
    black_duration = sum(float(match.group("duration")) for match in BLACK_DURATION_RE.finditer(combined))
    probe = _probe(path)
    duration = _duration(probe)
    black_ratio = black_duration / duration if duration > 0 else 0.0
    return {
        "duration": duration,
        "black_duration": black_duration,
        "black_ratio": black_ratio,
    }


def validate_render(
    input_video: Path,
    output_video: Path,
    *,
    max_black_ratio: float,
) -> dict[str, Any]:
    source_probe = _probe(input_video)
    output_probe = _probe(output_video)
    source_video_streams = _streams(source_probe, "video")
    source_audio_streams = _streams(source_probe, "audio")
    output_video_streams = _streams(output_probe, "video")
    output_audio_streams = _streams(output_probe, "audio")
    black_stats = _black_stats(output_video)

    warnings: list[str] = []
    errors: list[str] = []

    if len(output_video_streams) != 1:
        errors.append(f"expected exactly one output video stream, found {len(output_video_streams)}")
    if source_audio_streams and len(output_audio_streams) != 1:
        errors.append(f"expected exactly one output audio stream, found {len(output_audio_streams)}")
    if black_stats["black_ratio"] > max_black_ratio:
        errors.append(
            "output appears mostly black "
            f"(black_ratio={black_stats['black_ratio']:.3f}, threshold={max_black_ratio:.3f})"
        )

    source_video_bitrate = _bitrate(source_video_streams[0] if source_video_streams else None)
    output_video_bitrate = _bitrate(output_video_streams[0] if output_video_streams else None)
    if source_video_bitrate and output_video_bitrate and output_video_bitrate < max(64000, int(source_video_bitrate * 0.05)):
        warnings.append(
            "output video bitrate dropped sharply compared with the source "
            f"({output_video_bitrate} vs {source_video_bitrate} bps)"
        )

    validation = {
        "input_video": str(input_video),
        "output_video": str(output_video),
        "source_duration": _duration(source_probe),
        "output_duration": _duration(output_probe),
        "source_video_streams": len(source_video_streams),
        "source_audio_streams": len(source_audio_streams),
        "output_video_streams": len(output_video_streams),
        "output_audio_streams": len(output_audio_streams),
        "source_video_bitrate": source_video_bitrate,
        "output_video_bitrate": output_video_bitrate,
        "black_stats": black_stats,
        "warnings": warnings,
        "errors": errors,
    }
    if errors:
        raise RuntimeError(f"Render validation failed: {json.dumps(validation, ensure_ascii=False)}")
    return validation


def render(
    input_video: Path,
    labels_json: Path,
    output_video: Path,
    padding: float,
    *,
    edit: str = "none",
    margin: str | None = None,
    validation_json: Path | None = None,
    max_black_ratio: float = 0.75,
) -> list[str]:
    labels_doc = json.loads(labels_json.read_text(encoding="utf-8"))
    spans = _accepted_spans(labels_doc, padding)
    output_video.parent.mkdir(parents=True, exist_ok=True)
    command = ["auto-editor", str(input_video), "--edit", edit, "-o", str(output_video)]
    if margin is not None:
        command.extend(["--margin", margin])
    if spans:
        for start, end in spans:
            command.extend(["--cut-out", f"{start:.3f}sec,{end:.3f}sec"])
    subprocess.run(command, check=True)
    validation = validate_render(input_video, output_video, max_black_ratio=max_black_ratio)
    if validation_json is not None:
        validation_json.parent.mkdir(parents=True, exist_ok=True)
        validation_json.write_text(json.dumps(validation, indent=2, ensure_ascii=False), encoding="utf-8")
    return command


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_video")
    parser.add_argument("labels_json")
    parser.add_argument("--output-video", required=True)
    parser.add_argument("--padding", type=float, default=0.04)
    parser.add_argument("--edit", default="none")
    parser.add_argument("--margin")
    parser.add_argument("--command-log")
    parser.add_argument("--validation-json")
    parser.add_argument("--max-black-ratio", type=float, default=0.75)
    args = parser.parse_args()

    command = render(
        Path(args.input_video).expanduser().resolve(),
        Path(args.labels_json).expanduser().resolve(),
        Path(args.output_video).expanduser().resolve(),
        args.padding,
        edit=args.edit,
        margin=args.margin,
        validation_json=Path(args.validation_json).expanduser().resolve() if args.validation_json else None,
        max_black_ratio=args.max_black_ratio,
    )
    if args.command_log:
        Path(args.command_log).expanduser().resolve().write_text(
            " ".join(command) + "\n",
            encoding="utf-8",
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
