"""
VisualConsistencyChecker — post-generation VLM audit of storyboard frames.

Pipeline:
  1. Generate N frames via Seedream/Gemini/FLUX.
  2. For each frame, ask Gemini 2.5 Flash (vision) to compare against character_card.
  3. Returns score 0-100 + list of mismatches per frame.
  4. Caller decides whether to regenerate low-score frames with reinforced prompts.

Why Gemini and not Claude:
  - Claude Opus vision via LaoZhang reverse-proxy times out (>120s for one image).
  - Gemini 2.5 Flash returns in 2-4s and we already have GEMINI_API_KEY for storyboard.
"""

import base64
import json
import os
import re
import requests
from dataclasses import dataclass
from typing import List, Optional
from app.core.config import settings


@dataclass
class FrameReport:
    index: int  # 0-based
    score: int  # 0-100
    mismatches: List[str]  # ["hair color: brown not blonde", ...]
    needs_regen: bool


class VisualConsistencyChecker:
    """VLM-based consistency audit for storyboard frames."""

    SCORE_THRESHOLD = 80  # below this → flag for regen
    MODEL = "gemini-2.5-flash"
    API_URL_TMPL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"

    def __init__(self):
        self.api_key = settings.GEMINI_API_KEY
        if not self.api_key:
            print("[VISUAL CHECKER] GEMINI_API_KEY missing — checker disabled")
        self.enabled = bool(self.api_key)

    def _read_image_b64(self, path_or_url: str) -> Optional[tuple[str, str]]:
        """Returns (mime, base64) or None on failure."""
        try:
            # Local file via static URL → real path
            if path_or_url.startswith("http://localhost:8000/static/"):
                rel = path_or_url.split("/static/", 1)[1]
                full = os.path.join(
                    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
                    "static",
                    rel,
                )
                with open(full, "rb") as f:
                    data = f.read()
                mime = "image/png" if full.endswith(".png") else "image/jpeg"
                return mime, base64.b64encode(data).decode()
            elif path_or_url.startswith("/static/") or path_or_url.startswith("static/"):
                full = path_or_url.lstrip("/")
                full = os.path.join(
                    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
                    full,
                )
                with open(full, "rb") as f:
                    data = f.read()
                mime = "image/png" if full.endswith(".png") else "image/jpeg"
                return mime, base64.b64encode(data).decode()
            else:
                # Remote URL — fetch
                r = requests.get(path_or_url, timeout=15)
                r.raise_for_status()
                mime = r.headers.get("content-type", "image/jpeg").split(";")[0]
                return mime, base64.b64encode(r.content).decode()
        except Exception as e:
            print(f"[VISUAL CHECKER] Failed to read {path_or_url}: {e}")
            return None

    def _build_check_prompt(self, character_card: str) -> str:
        return (
            "You are a film continuity supervisor checking storyboard consistency.\n\n"
            f"REFERENCE CHARACTER CARD:\n{character_card}\n\n"
            "Look at the image and answer with ONE JSON object:\n"
            "{\n"
            '  "score": <int 0-100, how well the visible character matches the card>,\n'
            '  "mismatches": [<short string per visible mismatch — e.g. "hair color: brown not blonde", "age: 35 not 24">]\n'
            "}\n\n"
            "Score 100 = perfect match. Score below 70 means regeneration needed.\n"
            "Ignore camera angle, action, location — focus ONLY on character identity (hair, eyes, age, ethnicity, outfit).\n"
            "If the character is partially visible or hidden, give 60 with mismatch 'character not clearly visible'.\n"
            "Return ONLY the JSON object, no markdown fences."
        )

    def check_frame(self, image_path_or_url: str, character_card: str) -> Optional[dict]:
        """Check a single frame. Returns {score, mismatches} or None on failure."""
        if not self.enabled:
            return None
        img = self._read_image_b64(image_path_or_url)
        if not img:
            return None
        mime, b64 = img

        url = self.API_URL_TMPL.format(model=self.MODEL, key=self.api_key)
        body = {
            "contents": [{
                "parts": [
                    {"text": self._build_check_prompt(character_card)},
                    {"inline_data": {"mime_type": mime, "data": b64}},
                ]
            }]
        }
        try:
            r = requests.post(url, json=body, timeout=60)
            r.raise_for_status()
            data = r.json()
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            # Strip optional ```json fences
            text = re.sub(r"^```(?:json)?\s*|\s*```\s*$", "", text.strip(), flags=re.MULTILINE).strip()
            if "{" in text:
                text = text[text.find("{"):text.rfind("}") + 1]
            return json.loads(text)
        except Exception as e:
            print(f"[VISUAL CHECKER] Check failed: {e}")
            return None

    def check_storyboard(
        self,
        frame_urls: List[str],
        character_card: str,
    ) -> List[FrameReport]:
        """Check all frames and return per-frame reports."""
        reports: List[FrameReport] = []
        if not self.enabled or not character_card:
            return reports

        print(f"[VISUAL CHECKER] Auditing {len(frame_urls)} frames against character card")
        for idx, url in enumerate(frame_urls):
            if not url:
                continue
            res = self.check_frame(url, character_card)
            if res is None:
                continue
            score = int(res.get("score", 0))
            mismatches = res.get("mismatches", []) or []
            needs_regen = score < self.SCORE_THRESHOLD
            reports.append(FrameReport(
                index=idx,
                score=score,
                mismatches=[str(m) for m in mismatches if m],
                needs_regen=needs_regen,
            ))
            tag = "FAIL" if needs_regen else "ok"
            print(f"[VISUAL CHECKER] Frame {idx + 1}: {score}/100 [{tag}] {mismatches if mismatches else ''}")
        return reports

    @staticmethod
    def build_reinforcement(mismatches: List[str]) -> str:
        """Turn mismatch list into a positive prompt reinforcement to append."""
        if not mismatches:
            return ""
        bullets = "; ".join(mismatches)
        return f" CRITICAL CORRECTIONS: previous attempt had wrong {bullets}. This time match the character card EXACTLY."


# Singleton
_visual_checker: Optional[VisualConsistencyChecker] = None


def get_visual_consistency_checker() -> VisualConsistencyChecker:
    global _visual_checker
    if _visual_checker is None:
        _visual_checker = VisualConsistencyChecker()
    return _visual_checker
