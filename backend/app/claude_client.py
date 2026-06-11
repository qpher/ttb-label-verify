"""Claude Vision extraction: label image -> structured fields.

The model only *extracts* what it sees; all pass/fail decisions are made by
deterministic, unit-tested code in matching.py. This keeps results auditable
and consistent — important for a compliance tool.
"""
import base64
import json
import os

import anthropic

from .schemas import ExtractedLabel

# Haiku keeps single-label latency well under the ~5s budget Sarah set.
MODEL = os.environ.get("CLAUDE_MODEL", "claude-haiku-4-5-20251001")

EXTRACTION_PROMPT = """You are reading an alcohol beverage label image for a TTB compliance check.

Extract EXACTLY what is printed on the label — do not correct, normalize, or guess at
text you cannot read. Preserve original capitalization and punctuation.

Return ONLY a JSON object with this shape (use null for anything not visible):
{
  "brand_name": string|null,
  "class_type": string|null,            // e.g. "Kentucky Straight Bourbon Whiskey"
  "alcohol_content": string|null,       // exactly as printed, e.g. "45% Alc./Vol. (90 Proof)"
  "net_contents": string|null,          // e.g. "750 mL"
  "producer_name_address": string|null,
  "country_of_origin": string|null,
  "government_warning": {
    "present": boolean,
    "text": string|null,                // the FULL warning text exactly as printed, including the header
    "header_all_caps": boolean|null,    // is the "GOVERNMENT WARNING:" header printed in ALL CAPITAL letters?
    "header_bold": boolean|null         // does the header appear bold/heavier than surrounding text? null if unsure
  },
  "image_quality_issues": string|null,  // glare, angle, blur, low light, etc.
  "legibility": "ok"|"partial"|"unreadable"
}"""

_MEDIA_TYPES = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "gif": "image/gif",
    "webp": "image/webp",
}


def _client() -> anthropic.Anthropic:
    return anthropic.Anthropic()  # reads ANTHROPIC_API_KEY


def extract_label(image_bytes: bytes, filename: str = "") -> ExtractedLabel:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "png"
    media_type = _MEDIA_TYPES.get(ext, "image/png")

    message = _client().messages.create(
        model=MODEL,
        max_tokens=1500,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": base64.standard_b64encode(image_bytes).decode(),
                        },
                    },
                    {"type": "text", "text": EXTRACTION_PROMPT},
                ],
            }
        ],
    )

    raw = message.content[0].text.strip()
    # Tolerate accidental markdown fencing.
    if raw.startswith("```"):
        raw = raw.strip("`")
        raw = raw[raw.index("{") :]
        raw = raw[: raw.rindex("}") + 1]
    data = json.loads(raw)
    return ExtractedLabel.model_validate(data)
