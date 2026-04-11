#!/usr/bin/env python3
"""Generate removal labels from verbatim transcript words using an OpenAI model."""

from __future__ import annotations

import argparse
import csv
import json
import ssl
import sys
import uuid
from pathlib import Path
from typing import Any
from urllib import request

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from env_loader import find_env_value  # noqa: E402


API_URL = "https://api.openai.com/v1/chat/completions"
DEFAULT_FILLERS = (
    "um",
    "uh",
    "uhh",
    "umm",
    "er",
    "erm",
    "ah",
    "eh",
    "hmm",
    "mm",
    "呃",
    "啊",
    "嗯",
    "哦",
    "诶",
    "哎",
)
DEFAULT_CATCHPHRASES = (
    "you know",
    "i mean",
    "kind of",
    "sort of",
    "basically",
    "actually",
    "literally",
    "然后",
    "这个",
    "那个",
    "就是",
    "对吧",
    "是吧",
    "对对对",
    "你看",
    "实际上",
    "这个的话",
    "我这里呢",
    "说来着",
)
DEFAULT_PROTECTED_TERMS = (
    "我",
    "你",
    "它",
    "应该",
    "不知道",
    "我知道",
)
DEFAULT_SEMANTIC_TERMS = (
    "点击",
    "创建",
    "监听",
    "回复",
    "使用",
    "设置",
    "生成",
    "复制",
    "粘贴",
    "回到",
    "打开",
    "上传",
    "需要",
    "消息",
    "账号",
    "工作流",
    "token",
    "listener",
    "reply",
    "discord",
    "openai",
    "canvas",
    "application",
    "bot",
    "credential",
    "save",
    "copy",
    "reset",
)
LABEL_SCHEMA: dict[str, Any] = {
    "name": "video_cleanup_labels",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "labels": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "start_word_index": {"type": "integer", "minimum": 0},
                        "end_word_index": {"type": "integer", "minimum": 0},
                        "type": {
                            "type": "string",
                            "enum": [
                                "filler",
                                "discourse_marker",
                                "repetition",
                                "false_start",
                                "restart",
                                "self_correction",
                                "stutter",
                                "other",
                            ],
                        },
                        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                        "reason": {"type": "string"},
                        "accepted": {"type": "boolean"},
                    },
                    "required": [
                        "start_word_index",
                        "end_word_index",
                        "type",
                        "confidence",
                        "reason",
                        "accepted",
                    ],
                },
            }
        },
        "required": ["labels"],
    },
}


def _words(transcript: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        word
        for word in transcript.get("words", [])
        if word.get("type") == "word"
        and isinstance(word.get("start"), int | float)
        and isinstance(word.get("end"), int | float)
        and str(word.get("text") or "").strip()
    ]


def _serialize_words(words: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for index, word in enumerate(words):
        item: dict[str, Any] = {
            "index": index,
            "text": str(word.get("text") or ""),
            "start": round(float(word["start"]), 3),
            "end": round(float(word["end"]), 3),
        }
        if word.get("speaker_id") is not None:
            item["speaker_id"] = word["speaker_id"]
        items.append(item)
    return items


def _span_text(words: list[dict[str, Any]], start_index: int, end_index: int) -> str:
    return "".join(str(word.get("text") or "") for word in words[start_index : end_index + 1]).strip()


def _developer_prompt() -> str:
    return (
        "You are labeling removal candidates for speech-video cleanup. "
        "Your job is to identify spans of spoken transcript that should be removed "
        "to improve fluency while preserving the speaker's meaning and instructional content. "
        "Return only valid JSON matching the schema. "
        "Use the provided verbatim transcript words as the sole source of truth for indices and timing. "
        "Be precise, not aggressive. "
        "Auto-accept only clearly safe removals such as standalone fillers, obvious false starts, restarts, "
        "self-corrections, and repeated clauses with preserved meaning. "
        "For borderline discourse markers, you may emit a label but set accepted=false. "
        "Be conservative on meaning-bearing words, especially pronouns, nouns, commands, explanatory clauses, and factual content. "
        "If a risky word is removable only because it is part of a larger false start or repeated fragment, "
        "label the larger span rather than the isolated word. "
        "Do not invent indices. Do not emit punctuation-only spans."
    )


def _user_prompt(
    *,
    words: list[dict[str, Any]],
    comparison_text: str | None,
    language_hint: str | None,
    fillers: tuple[str, ...],
    catchphrases: tuple[str, ...],
    protected_terms: tuple[str, ...],
) -> str:
    parts = [
        "Label removals for a speech-heavy instructional video.",
        "Use the indexed verbatim words below.",
        "Accepted labels should be safe default cuts.",
        "Use accepted=false for plausible but borderline cuts that need QA review.",
        "",
        "Rules:",
        "- Prefer longer phrase spans when removing false starts, repeated starts, or self-corrections.",
        "- Remove standalone fillers aggressively only when they are clearly non-semantic.",
        "- Keep discourse-marker cuts short unless the span is plainly redundant or repeated.",
        "- Remove repeated words and repeated short clauses when clearly redundant.",
        "- Keep semantically important words unless they are inside a larger redundant fragment.",
        "- Do not remove content that changes instructions, entity names, arguments, or examples.",
        "- If a span contains a core action or requirement, prefer accepted=false unless the content is obviously duplicated nearby.",
    ]
    if language_hint:
        parts.extend(["", f"Primary language hint: {language_hint}."])
    if fillers:
        parts.extend(["", "Filler examples to target aggressively:", ", ".join(fillers)])
    if catchphrases:
        parts.extend(["", "Discourse markers and removable phrases to consider:", ", ".join(catchphrases)])
    if protected_terms:
        parts.extend(
            [
                "",
                "Protected terms that are often meaningful on their own. "
                "Only remove them if they are part of a larger false start, restart, or repeated fragment:",
                ", ".join(protected_terms),
            ]
        )
    if comparison_text:
        parts.extend(
            [
                "",
                "Comparison transcript from a non-verbatim cleanup pass. "
                "Use it only as a hint for likely cleanup areas, never as timestamp truth:",
                comparison_text,
            ]
        )
    parts.extend(
        [
            "",
            "Indexed verbatim words JSON:",
            json.dumps(_serialize_words(words), ensure_ascii=False, separators=(",", ":")),
        ]
    )
    return "\n".join(parts)


def _chat_completion(
    *,
    api_key: str,
    model_id: str,
    developer_prompt: str,
    user_prompt: str,
    timeout: int,
) -> tuple[dict[str, Any], str | None]:
    payload = {
        "model": model_id,
        "messages": [
            {"role": "developer", "content": developer_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": LABEL_SCHEMA,
        },
    }
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(
        API_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "X-Client-Request-Id": f"video-speech-cleanup-{uuid.uuid4()}",
        },
        method="POST",
    )
    context = ssl.create_default_context()
    with request.urlopen(req, timeout=timeout, context=context) as response:
        response_body = response.read().decode("utf-8")
        request_id = response.headers.get("x-request-id")
    return json.loads(response_body), request_id


def _extract_message_text(response: dict[str, Any]) -> str:
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        raise RuntimeError("OpenAI response did not contain any choices.")
    message = choices[0].get("message") or {}
    refusal = message.get("refusal")
    if refusal:
        raise RuntimeError(f"OpenAI labeling request was refused: {refusal}")
    content = message.get("content")
    if isinstance(content, str) and content.strip():
        return content
    raise RuntimeError("OpenAI response did not contain structured label content.")


def _contains_semantic_term(text: str, semantic_terms: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(term and term.lower() in lowered for term in semantic_terms)


def _safety_filter_label(
    label: dict[str, Any],
    *,
    max_auto_discourse_duration: float,
    semantic_terms: tuple[str, ...],
) -> dict[str, Any]:
    filtered = dict(label)
    duration = float(filtered["end"]) - float(filtered["start"])
    text = str(filtered["text"])
    label_type = str(filtered["type"])
    accepted = bool(filtered["accepted"])
    reasons: list[str] = []

    if label_type in {"discourse_marker", "other"}:
        if duration > max_auto_discourse_duration:
            accepted = False
            reasons.append(
                f"auto-rejected by safety filter because discourse-marker span is long ({duration:.2f}s)"
            )
        if _contains_semantic_term(text, semantic_terms):
            accepted = False
            reasons.append("auto-rejected by safety filter because span contains protected instructional terms")

    if accepted != bool(filtered["accepted"]) and reasons:
        filtered["accepted"] = accepted
        filtered["reason"] = f"{filtered['reason']} [{'; '.join(reasons)}]"
    return filtered


def build_labels(
    transcript: dict[str, Any],
    *,
    api_key: str,
    model_id: str,
    comparison_text: str | None,
    language_hint: str | None,
    fillers: tuple[str, ...],
    catchphrases: tuple[str, ...],
    protected_terms: tuple[str, ...],
    semantic_terms: tuple[str, ...],
    max_auto_discourse_duration: float,
    timeout: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    words = _words(transcript)
    if not words:
        raise RuntimeError("Transcript did not contain any verbatim words with timestamps.")

    developer_prompt = _developer_prompt()
    user_prompt = _user_prompt(
        words=words,
        comparison_text=comparison_text,
        language_hint=language_hint,
        fillers=fillers,
        catchphrases=catchphrases,
        protected_terms=protected_terms,
    )
    response, request_id = _chat_completion(
        api_key=api_key,
        model_id=model_id,
        developer_prompt=developer_prompt,
        user_prompt=user_prompt,
        timeout=timeout,
    )
    raw_labels = json.loads(_extract_message_text(response))
    labels: list[dict[str, Any]] = []
    last_index = len(words) - 1
    for candidate in raw_labels.get("labels", []):
        start_index = int(candidate["start_word_index"])
        end_index = int(candidate["end_word_index"])
        if start_index < 0 or end_index < start_index or end_index > last_index:
            raise RuntimeError(
                f"Label indices out of range: start={start_index}, end={end_index}, word_count={len(words)}"
            )
        span_text = _span_text(words, start_index, end_index)
        if not span_text:
            continue
        labels.append(
            _safety_filter_label(
                {
                "id": f"cut_{len(labels) + 1:04d}",
                "type": str(candidate["type"]),
                "text": span_text,
                "start": float(words[start_index]["start"]),
                "end": float(words[end_index]["end"]),
                "confidence": float(candidate["confidence"]),
                "reason": str(candidate["reason"]),
                "accepted": bool(candidate["accepted"]),
                "start_word_index": start_index,
                "end_word_index": end_index,
                },
                max_auto_discourse_duration=max_auto_discourse_duration,
                semantic_terms=semantic_terms,
            )
        )

    labels.sort(key=lambda item: (item["start"], item["end"], item["type"]))
    for index, label in enumerate(labels, start=1):
        label["id"] = f"cut_{index:04d}"
    labels_doc = {"source": "openai_over_elevenlabs_verbatim", "labels": labels}
    debug_doc = {
        "provider": "openai",
        "model_id": model_id,
        "request_id": request_id,
        "developer_prompt": developer_prompt,
        "user_prompt": user_prompt,
        "raw_response": response,
    }
    return labels_doc, debug_doc


def write_csv(labels_doc: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "id",
                "type",
                "text",
                "start",
                "end",
                "confidence",
                "reason",
                "accepted",
                "start_word_index",
                "end_word_index",
            ],
        )
        writer.writeheader()
        for label in labels_doc["labels"]:
            writer.writerow(label)


def write_words_csv(transcript: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["text", "start", "end", "type", "speaker_id", "logprob"],
        )
        writer.writeheader()
        for word in transcript.get("words", []):
            writer.writerow({field: word.get(field) for field in writer.fieldnames})


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("transcript_json")
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-csv")
    parser.add_argument("--words-csv")
    parser.add_argument("--output-debug-json")
    parser.add_argument("--comparison-transcript")
    parser.add_argument("--api-key")
    parser.add_argument("--model-id", default="gpt-5.4-mini")
    parser.add_argument("--language-hint")
    parser.add_argument("--fillers", default=",".join(DEFAULT_FILLERS))
    parser.add_argument("--catchphrases", default="|".join(DEFAULT_CATCHPHRASES))
    parser.add_argument("--protected-terms", default="|".join(DEFAULT_PROTECTED_TERMS))
    parser.add_argument("--semantic-terms", default="|".join(DEFAULT_SEMANTIC_TERMS))
    parser.add_argument("--max-auto-discourse-duration", type=float, default=1.0)
    parser.add_argument("--timeout", type=int, default=300)
    args = parser.parse_args()

    transcript_path = Path(args.transcript_json).expanduser().resolve()
    transcript = json.loads(transcript_path.read_text(encoding="utf-8"))
    api_key, _api_key_source = find_env_value(
        "OPENAI_API_KEY",
        transcript_path,
        args.output_json,
    )
    api_key = args.api_key or api_key
    if not api_key:
        parser.error("Provide --api-key, set OPENAI_API_KEY, or store it in a nearby .env.")

    comparison_text = None
    if args.comparison_transcript:
        comparison_text = Path(args.comparison_transcript).expanduser().resolve().read_text(encoding="utf-8")
    labels_doc, debug_doc = build_labels(
        transcript,
        api_key=api_key,
        model_id=args.model_id,
        comparison_text=comparison_text,
        language_hint=args.language_hint,
        fillers=tuple(item.strip() for item in args.fillers.split(",") if item.strip()),
        catchphrases=tuple(item.strip() for item in args.catchphrases.split("|") if item.strip()),
        protected_terms=tuple(item.strip() for item in args.protected_terms.split("|") if item.strip()),
        semantic_terms=tuple(item.strip() for item in args.semantic_terms.split("|") if item.strip()),
        max_auto_discourse_duration=args.max_auto_discourse_duration,
        timeout=args.timeout,
    )

    output_json = Path(args.output_json).expanduser().resolve()
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(labels_doc, indent=2, ensure_ascii=False), encoding="utf-8")
    if args.output_csv:
        write_csv(labels_doc, Path(args.output_csv).expanduser().resolve())
    if args.words_csv:
        write_words_csv(transcript, Path(args.words_csv).expanduser().resolve())
    if args.output_debug_json:
        output_debug_json = Path(args.output_debug_json).expanduser().resolve()
        output_debug_json.parent.mkdir(parents=True, exist_ok=True)
        output_debug_json.write_text(json.dumps(debug_doc, indent=2, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
