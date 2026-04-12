#!/usr/bin/env python3
"""Run the local video speech cleanup pipeline and preserve QA artifacts."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from env_loader import find_env_value  # noqa: E402
from elevenlabs_transcribe import transcribe, write_outputs  # noqa: E402
from label_removals import (  # noqa: E402
    DEFAULT_CATCHPHRASES,
    DEFAULT_FILLERS,
    DEFAULT_PROTECTED_TERMS,
    DEFAULT_SEMANTIC_TERMS,
    build_labels,
    write_csv,
    write_words_csv,
)
from render_from_labels import render  # noqa: E402


def _slug(value: str) -> str:
    slug = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in value).strip("-")
    return slug[:80]


def _run(command: list[str], log_path: Path | None = None) -> None:
    if log_path is None:
        subprocess.run(command, check=True)
        return
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8") as log:
        log.write("$ " + " ".join(command) + "\n\n")
        try:
            subprocess.run(command, check=True, stdout=log, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(f"Command failed (exit {exc.returncode}), see log: {log_path}") from exc


def _version(command: str) -> str | None:
    path = shutil.which(command)
    if not path:
        return None
    try:
        result = subprocess.run(
            [command, "-version"] if command != "auto-editor" else [command, "--version"],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return path
    first_line = (result.stdout or result.stderr).splitlines()
    return first_line[0] if first_line else path


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _require_tools() -> None:
    missing = [tool for tool in ("ffmpeg", "ffprobe", "auto-editor") if shutil.which(tool) is None]
    if missing:
        raise RuntimeError(f"Missing required tool(s): {', '.join(missing)}")


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


def _normalize_source_video(source_copy: Path, normalized_source: Path, log_path: Path) -> None:
    _run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(source_copy),
            "-map",
            "0:v:0",
            "-map",
            "0:a:0?",
            "-sn",
            "-dn",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "18",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-movflags",
            "+faststart",
            str(normalized_source),
        ],
        log_path,
    )


def _env_available(name: str, *, cli_value: str | None, search_roots: tuple[Path | str | None, ...]) -> tuple[bool, str]:
    value, source = find_env_value(name, *search_roots)
    if cli_value:
        return True, "cli-arg"
    return bool(value), source or "environment"


def preflight(args: argparse.Namespace) -> dict[str, Any]:
    """Return preflight diagnostics without creating run artifacts."""
    source = Path(args.input_video).expanduser().resolve()
    tools = {tool: shutil.which(tool) for tool in ("ffmpeg", "ffprobe", "auto-editor")}
    missing_tools = [tool for tool, path in tools.items() if path is None]
    search_roots: tuple[Path | str | None, ...] = (source, args.output_root)
    elevenlabs_available, elevenlabs_source = _env_available(
        "ELEVENLABS_API_KEY",
        cli_value=args.api_key,
        search_roots=search_roots,
    )
    openai_available, openai_source = _env_available(
        "OPENAI_API_KEY",
        cli_value=args.label_api_key,
        search_roots=search_roots,
    )
    diagnostics = {
        "ok": source.exists() and not missing_tools and elevenlabs_available and openai_available,
        "input_video": str(source),
        "input_exists": source.exists(),
        "tools": tools,
        "missing_tools": missing_tools,
        "elevenlabs_api_key_available": elevenlabs_available,
        "elevenlabs_api_key_source": elevenlabs_source,
        "openai_api_key_available": openai_available,
        "openai_api_key_source": openai_source,
    }
    if not diagnostics["ok"]:
        missing: list[str] = []
        if not source.exists():
            missing.append(f"input file not found: {source}")
        if missing_tools:
            missing.append("commands: " + ", ".join(missing_tools))
        if not elevenlabs_available:
            missing.append("ELEVENLABS_API_KEY")
        if not openai_available:
            missing.append("OPENAI_API_KEY")
        diagnostics["missing"] = missing
    return diagnostics


def process(args: argparse.Namespace) -> Path:
    _require_tools()
    source = Path(args.input_video).expanduser().resolve()
    if not source.exists():
        raise FileNotFoundError(source)

    elevenlabs_api_key, _ = find_env_value("ELEVENLABS_API_KEY", source, args.output_root)
    elevenlabs_api_key = args.api_key or elevenlabs_api_key
    if not elevenlabs_api_key:
        raise RuntimeError("Provide --api-key, set ELEVENLABS_API_KEY, or store it in a nearby .env.")

    label_api_key, _ = find_env_value("OPENAI_API_KEY", source, args.output_root)
    label_api_key = args.label_api_key or label_api_key
    if not label_api_key:
        raise RuntimeError("Provide --label-api-key, set OPENAI_API_KEY, or store it in a nearby .env.")

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = Path(args.output_root).expanduser().resolve() / f"{_slug(source.stem)}-{timestamp}"
    input_dir = run_dir / "input"
    audio_dir = run_dir / "audio"
    silence_dir = run_dir / "silence"
    transcripts_dir = run_dir / "transcripts"
    labels_dir = run_dir / "labels"
    renders_dir = run_dir / "renders"
    for directory in (input_dir, audio_dir, silence_dir, transcripts_dir, labels_dir, renders_dir):
        directory.mkdir(parents=True, exist_ok=True)

    source_copy = input_dir / f"source_video{source.suffix}"
    if args.symlink_input:
        source_copy.symlink_to(source)
    else:
        shutil.copy2(source, source_copy)

    normalized_source = input_dir / "normalized_source.mp4"
    ffprobe_original_path = input_dir / "ffprobe.json"
    ffprobe_normalized_path = input_dir / "normalized_ffprobe.json"
    normalize_log_path = input_dir / "normalize_source.log"

    manifest: dict[str, Any] = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_path": str(source),
        "run_dir": str(run_dir),
        "tools": {
            "ffmpeg": _version("ffmpeg"),
            "ffprobe": _version("ffprobe"),
            "auto_editor": _version("auto-editor"),
        },
        "parameters": {
            "model_id": args.model_id,
            "language_code": args.language_code,
            "diarize": args.diarize,
            "auto_editor_margin": args.margin,
            "auto_editor_edit": args.edit,
            "skip_no_verbatim": args.skip_no_verbatim,
            "label_model_id": args.label_model_id,
            "fillers": [item.strip() for item in args.fillers.split(",") if item.strip()],
            "catchphrases": [item.strip() for item in args.catchphrases.split("|") if item.strip()],
            "protected_terms": [item.strip() for item in args.protected_terms.split("|") if item.strip()],
            "semantic_terms": [item.strip() for item in args.semantic_terms.split("|") if item.strip()],
            "use_comparison_hint": args.use_comparison_hint,
            "max_auto_discourse_duration": args.max_auto_discourse_duration,
            "max_black_ratio": args.max_black_ratio,
        },
        "artifacts": {},
        "status": "running",
    }
    manifest_path = run_dir / "manifest.json"
    _write_json(manifest_path, manifest)

    try:
        _write_json(ffprobe_original_path, _probe(source_copy))
        _normalize_source_video(source_copy, normalized_source, normalize_log_path)
        _write_json(ffprobe_normalized_path, _probe(normalized_source))

        extracted_audio = audio_dir / "extracted.wav"
        normalized_audio = audio_dir / "normalized.wav"
        _run(["ffmpeg", "-y", "-i", str(normalized_source), "-vn", "-ac", "1", "-ar", "16000", str(extracted_audio)])
        _run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(extracted_audio),
                "-af",
                "loudnorm=I=-16:TP=-1.5:LRA=11",
                str(normalized_audio),
            ]
        )

        silence_video = silence_dir / "silence_removed.mp4"
        _run(
            [
                "auto-editor",
                str(normalized_source),
                "--margin",
                args.margin,
                "--edit",
                args.edit,
                "-o",
                str(silence_video),
            ],
            silence_dir / "auto_editor.log",
        )

        verbatim_json = transcripts_dir / "elevenlabs_verbatim.json"
        verbatim_txt = transcripts_dir / "transcript_verbatim.txt"
        verbatim = transcribe(
            api_key=elevenlabs_api_key,
            file_path=normalized_audio,
            source_url=None,
            model_id=args.model_id,
            language_code=args.language_code,
            diarize=args.diarize,
            no_verbatim=False,
            seed=args.seed,
            timeout=args.timeout,
        )
        write_outputs(verbatim, verbatim_json, verbatim_txt)

        comparison_text = None
        if not args.skip_no_verbatim:
            clean_json = transcripts_dir / "elevenlabs_no_verbatim.json"
            clean_txt = transcripts_dir / "transcript_clean.txt"
            clean = transcribe(
                api_key=elevenlabs_api_key,
                file_path=normalized_audio,
                source_url=None,
                model_id=args.model_id,
                language_code=args.language_code,
                diarize=args.diarize,
                no_verbatim=True,
                seed=args.seed,
                timeout=args.timeout,
            )
            write_outputs(clean, clean_json, clean_txt)
            if args.use_comparison_hint:
                comparison_text = str(clean.get("text") or "")

        labels_doc, label_debug = build_labels(
            verbatim,
            api_key=label_api_key,
            model_id=args.label_model_id,
            comparison_text=comparison_text,
            language_hint=args.label_language or args.language_code,
            fillers=tuple(item.strip() for item in args.fillers.split(",") if item.strip()),
            catchphrases=tuple(item.strip() for item in args.catchphrases.split("|") if item.strip()),
            protected_terms=tuple(item.strip() for item in args.protected_terms.split("|") if item.strip()),
            semantic_terms=tuple(item.strip() for item in args.semantic_terms.split("|") if item.strip()),
            max_auto_discourse_duration=args.max_auto_discourse_duration,
            timeout=args.label_timeout,
        )
        labels_json = labels_dir / "removal_labels.json"
        labels_csv = labels_dir / "removal_labels.csv"
        label_debug_json = labels_dir / "labeler_response.json"
        words_csv = transcripts_dir / "words.csv"
        _write_json(labels_json, labels_doc)
        _write_json(label_debug_json, label_debug)
        write_csv(labels_doc, labels_csv)
        write_words_csv(verbatim, words_csv)

        final_video = renders_dir / "final.mp4"
        render_validation_json = renders_dir / "render_validation.json"
        render(
            normalized_source,
            labels_json,
            final_video,
            args.render_padding,
            edit=args.edit,
            margin=args.margin,
            validation_json=render_validation_json,
            max_black_ratio=args.max_black_ratio,
        )

        manifest["artifacts"] = {
            "source_video": str(source_copy.relative_to(run_dir)),
            "normalized_source_video": str(normalized_source.relative_to(run_dir)),
            "normalize_source_log": str(normalize_log_path.relative_to(run_dir)),
            "ffprobe": str(ffprobe_original_path.relative_to(run_dir)),
            "normalized_ffprobe": str(ffprobe_normalized_path.relative_to(run_dir)),
            "extracted_audio": str(extracted_audio.relative_to(run_dir)),
            "normalized_audio": str(normalized_audio.relative_to(run_dir)),
            "silence_removed_video": str(silence_video.relative_to(run_dir)),
            "verbatim_transcript_json": str(verbatim_json.relative_to(run_dir)),
            "verbatim_transcript_text": str(verbatim_txt.relative_to(run_dir)),
            "words_csv": str(words_csv.relative_to(run_dir)),
            "removal_labels_json": str(labels_json.relative_to(run_dir)),
            "removal_labels_csv": str(labels_csv.relative_to(run_dir)),
            "labeler_response_json": str(label_debug_json.relative_to(run_dir)),
            "render_validation_json": str(render_validation_json.relative_to(run_dir)),
            "final_video": str(final_video.relative_to(run_dir)),
        }
        if not args.skip_no_verbatim:
            manifest["artifacts"]["clean_transcript_json"] = str(clean_json.relative_to(run_dir))
            manifest["artifacts"]["clean_transcript_text"] = str(clean_txt.relative_to(run_dir))
        manifest["status"] = "completed"
        _write_json(manifest_path, manifest)
        return run_dir
    except Exception as exc:
        manifest["status"] = "failed"
        manifest["error"] = str(exc)
        _write_json(manifest_path, manifest)
        raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_video")
    parser.add_argument(
        "--output-root",
        default=os.environ.get("VIDEO_SPEECH_CLEANUP_OUTPUT_ROOT", "runs"),
    )
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--api-key")
    parser.add_argument("--label-api-key")
    parser.add_argument("--model-id", default="scribe_v2")
    parser.add_argument("--label-model-id", default="gpt-4.1-mini")
    parser.add_argument("--language-code")
    parser.add_argument("--label-language")
    parser.add_argument("--diarize", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--timeout", type=int, default=1800)
    parser.add_argument("--label-timeout", type=int, default=300)
    parser.add_argument("--margin", default="0.2sec")
    parser.add_argument("--edit", default="audio:threshold=0.04,stream=all")
    parser.add_argument("--skip-no-verbatim", action="store_true")
    parser.add_argument("--fillers", default=",".join(DEFAULT_FILLERS))
    parser.add_argument("--catchphrases", default="|".join(DEFAULT_CATCHPHRASES))
    parser.add_argument("--protected-terms", default="|".join(DEFAULT_PROTECTED_TERMS))
    parser.add_argument("--semantic-terms", default="|".join(DEFAULT_SEMANTIC_TERMS))
    parser.add_argument("--use-comparison-hint", action="store_true")
    parser.add_argument("--max-auto-discourse-duration", type=float, default=1.0)
    parser.add_argument("--render-padding", type=float, default=0.04)
    parser.add_argument("--max-black-ratio", type=float, default=0.75)
    parser.add_argument("--symlink-input", action="store_true")
    args = parser.parse_args()

    if args.check_only:
        diagnostics = preflight(args)
        print(json.dumps(diagnostics, indent=2, ensure_ascii=False))
        return 0 if diagnostics["ok"] else 2

    run_dir = process(args)
    print(run_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
