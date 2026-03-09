"""
Quality Check Agent - validates and auto-fixes episode prompts before video generation.

Checks for:
1. Logical consistency between episodes
2. Character description consistency
3. Completeness (enough detail for video generation)
4. Quality of writing (no glitches, truncation)
5. Structured audio (SFX/Ambient/Music)
6. Negative prompt (noun format)
7. Dialogue colon syntax (no quotes)
8. Inline (no subtitles)
9. Single camera movement (no flicker)
10. English-only prompts (Veo requirement)
11. Technical constraints (aspect ratio, resolution, duration)

Note: Moderation/banned words check removed — handled by PromptSoftener at generation time.
"""
import os
import re
import json
from typing import List, Optional
from dataclasses import dataclass


@dataclass
class QualityIssue:
    """Represents a quality issue found in a prompt"""
    episode_number: int
    issue_type: str  # 'consistency', 'incomplete', 'moderation', 'logic', 'quality', 'audio', 'language', 'dialogue'
    severity: str  # 'low', 'medium', 'high'
    description: str
    suggested_fix: Optional[str] = None


@dataclass
class QualityReport:
    """Quality report for an episode prompt"""
    episode_number: int
    score: int  # 0-100
    issues: List[QualityIssue]
    fixed_prompt: Optional[str] = None


class QualityChecker:
    """
    Agent that checks quality of generated prompts and auto-fixes issues.
    Validates Veo 3.1 best practices compliance.
    """

    CAMERA_MOVEMENTS = ['dolly', 'pan', 'tilt', 'crane', 'tracking', 'truck', 'arc', 'zoom', 'whip']

    def __init__(self):
        self.api_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")
        self.use_llm = bool(self.api_key)
        self.client = None
        self.model = "deepseek/deepseek-chat-v3-0324"

        if self.use_llm:
            try:
                from openai import OpenAI
                if os.getenv("OPENROUTER_API_KEY"):
                    self.client = OpenAI(
                        api_key=self.api_key,
                        base_url="https://openrouter.ai/api/v1"
                    )
                else:
                    self.client = OpenAI(api_key=self.api_key)
                print("[QUALITY CHECKER] Initialized with LLM support")
            except ImportError:
                print("[QUALITY CHECKER] Warning: openai not installed, using rule-based checks only")
                self.use_llm = False

    def check_and_fix_prompts(
        self,
        prompts: List[dict],
        main_character: str = ""
    ) -> tuple[List[dict], List[QualityReport]]:
        """
        Check all prompts for quality issues and auto-fix them.
        """
        print(f"[QUALITY CHECKER] Checking {len(prompts)} prompts...")

        reports = []
        fixed_prompts = []

        for prompt in prompts:
            report = self._check_single_prompt(prompt, main_character, prompts)

            if report.score < 70:
                fixed_prompt = self._auto_fix_prompt(prompt, report, main_character)
                report.fixed_prompt = fixed_prompt.get('visual_prompt')
                fixed_prompts.append(fixed_prompt)
                print(f"[QUALITY CHECKER] Episode {prompt.get('number')}: {report.score}/100 - AUTO-FIXED")
            else:
                fixed_prompts.append(prompt)
                print(f"[QUALITY CHECKER] Episode {prompt.get('number')}: {report.score}/100 - OK")

            reports.append(report)

        if len(fixed_prompts) > 1 and self.use_llm:
            print(f"[QUALITY CHECKER] Checking story continuity...")
            fixed_prompts, continuity_issues = self._check_story_continuity(fixed_prompts, main_character)
            if continuity_issues:
                print(f"[QUALITY CHECKER] Fixed {len(continuity_issues)} continuity issues")

        return fixed_prompts, reports

    def _check_story_continuity(
        self,
        prompts: List[dict],
        main_character: str
    ) -> tuple[List[dict], List[str]]:
        """Use LLM to check and fix story continuity between episodes."""
        if not self.client:
            return prompts, []

        issues_found = []

        try:
            episodes_text = "\n".join([
                f"Episode {p['number']}: {p.get('title', 'Untitled')}\nSynopsis: {p.get('synopsis', 'No synopsis')}\nVisual: {p.get('visual_prompt', '')[:200]}..."
                for p in prompts
            ])

            system_prompt = """You are a story editor checking episode continuity.
Analyze these episodes and identify any logical problems:
1. Does each episode flow naturally from the previous one?
2. Are there any sudden jumps in location, time, or character state that don't make sense?
3. Is the story arc coherent?

If you find issues, respond with JSON:
{
  "has_issues": true,
  "issues": [
    {"episode": 2, "problem": "description", "fix": "suggested transition or fix"}
  ]
}

If everything flows well, respond:
{"has_issues": false, "issues": []}"""

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Main character: {main_character}\n\nEpisodes:\n{episodes_text}"}
                ],
                temperature=0.3,
                max_tokens=500,
                timeout=30,
            )

            result_text = response.choices[0].message.content

            try:
                if "```json" in result_text:
                    result_text = result_text.replace("```json", "").replace("```", "")
                result_text = result_text.strip()

                if "{" in result_text:
                    result = json.loads(result_text[result_text.find("{"):result_text.rfind("}")+1])

                    if result.get("has_issues") and result.get("issues"):
                        for issue in result["issues"]:
                            ep_num = issue.get("episode", 0)
                            fix = issue.get("fix", "")
                            problem = issue.get("problem", "")

                            issues_found.append(f"Episode {ep_num}: {problem}")
                            print(f"[QUALITY CHECKER] Continuity issue in Episode {ep_num}: {problem}")

                            if fix and 0 < ep_num <= len(prompts):
                                idx = ep_num - 1
                                current_prompt = prompts[idx].get('visual_prompt', '')
                                prompts[idx] = prompts[idx].copy()
                                prompts[idx]['visual_prompt'] = f"{current_prompt} Transition: {fix}"
                                print(f"[QUALITY CHECKER] Applied fix to Episode {ep_num}")
            except json.JSONDecodeError:
                pass

        except Exception as e:
            print(f"[QUALITY CHECKER] Continuity check error: {e}")

        return prompts, issues_found

    def _check_single_prompt(
        self,
        prompt: dict,
        main_character: str,
        all_prompts: List[dict]
    ) -> QualityReport:
        """Check a single prompt for quality issues including Veo 3.1 compliance"""
        issues = []
        score = 100

        visual_prompt = prompt.get('visual_prompt', '')
        episode_num = prompt.get('number', 0)

        # Check 1: Prompt length (completeness)
        if len(visual_prompt) < 50:
            issues.append(QualityIssue(
                episode_number=episode_num, issue_type='incomplete', severity='high',
                description='Prompt too short (< 50 chars)', suggested_fix='Add more visual details'))
            score -= 30
        elif len(visual_prompt) < 80:
            issues.append(QualityIssue(
                episode_number=episode_num, issue_type='incomplete', severity='medium',
                description='Prompt could use more detail (< 80 chars)'))
            score -= 10

        # Check 2: Character consistency
        if main_character:
            char_parts = main_character.lower().split(',')[:3]
            matches = sum(1 for part in char_parts if part.strip() in visual_prompt.lower())
            if matches < 2:
                issues.append(QualityIssue(
                    episode_number=episode_num, issue_type='consistency', severity='high',
                    description='Character description missing or inconsistent',
                    suggested_fix=f'Add: {main_character}'))
                score -= 25

        # Check 3: (removed — moderation handled by PromptSoftener at generation time)

        # Check 4: Truncation detection
        if visual_prompt.endswith('...') or visual_prompt.endswith('-'):
            issues.append(QualityIssue(
                episode_number=episode_num, issue_type='quality', severity='high',
                description='Prompt appears truncated',
                suggested_fix='Regenerate or complete the prompt'))
            score -= 25

        # Check 5: Camera/lighting instructions
        has_camera = any(word in visual_prompt.lower() for word in ['camera', 'shot', 'close-up', 'medium', 'wide', 'pan', 'zoom', 'dolly', 'tracking'])
        has_lighting = any(word in visual_prompt.lower() for word in ['light', 'lighting', 'glow', 'shadow', 'neon', 'dark', 'bright', 'golden'])

        if not has_camera:
            issues.append(QualityIssue(
                episode_number=episode_num, issue_type='quality', severity='low',
                description='Missing camera instructions'))
            score -= 5

        if not has_lighting:
            issues.append(QualityIssue(
                episode_number=episode_num, issue_type='quality', severity='low',
                description='Missing lighting description'))
            score -= 5

        # Check 6: Structured audio (SFX/Ambient/Music)
        has_audio = any(word in visual_prompt.lower() for word in ['sfx:', 'ambient:', 'music:'])
        if not has_audio:
            issues.append(QualityIssue(
                episode_number=episode_num, issue_type='audio', severity='medium',
                description='Missing structured audio (SFX:/Ambient:/Music:). Veo guesses audio poorly without it.'))
            score -= 5

        # Check 7: Negative prompt present (noun format, not "no X")
        has_negative = 'negative prompt:' in visual_prompt.lower()
        if not has_negative:
            issues.append(QualityIssue(
                episode_number=episode_num, issue_type='quality', severity='low',
                description='Missing negative prompt section'))
            score -= 3

        # Check 8: Dialogue uses colon syntax (not quotes -> Veo renders subtitles)
        has_quoted_dialogue = bool(re.search(r'["\u201c\u201d].{5,}["\u201c\u201d]', visual_prompt))
        if has_quoted_dialogue:
            issues.append(QualityIssue(
                episode_number=episode_num, issue_type='dialogue', severity='medium',
                description='Dialogue uses quotes -> subtitles. Use colon syntax: Character says: line'))
            score -= 5

        # Check 9: Inline (no subtitles)
        has_no_subs = 'no subtitles' in visual_prompt.lower()
        if not has_no_subs:
            issues.append(QualityIssue(
                episode_number=episode_num, issue_type='quality', severity='low',
                description='Missing inline (no subtitles) - Veo may render subtitles'))
            score -= 2

        # Check 10: Multiple camera movements (causes flicker)
        found_movements = [m for m in self.CAMERA_MOVEMENTS if m in visual_prompt.lower()]
        if len(found_movements) > 1:
            issues.append(QualityIssue(
                episode_number=episode_num, issue_type='quality', severity='medium',
                description=f'Multiple camera movements ({", ".join(found_movements)}) - causes flicker. Use ONE.'))
            score -= 5

        # Check 11: Prompt language (must be English for Veo)
        if re.search(r'[\u0400-\u04FF]', visual_prompt):
            issues.append(QualityIssue(
                episode_number=episode_num, issue_type='language', severity='high',
                description='Prompt contains non-English (Cyrillic) text. Veo requires English-only prompts.'))
            score -= 15

        # Check 12: Technical constraints at end (aspect ratio, resolution, duration)
        has_tech = any(p in visual_prompt for p in ['9:16', '16:9', '720p', '1080p'])
        if not has_tech:
            issues.append(QualityIssue(
                episode_number=episode_num, issue_type='quality', severity='low',
                description='Missing technical constraints (aspect ratio, resolution, duration) at end'))
            score -= 2

        score = max(0, min(100, score))

        return QualityReport(
            episode_number=episode_num,
            score=score,
            issues=issues
        )

    def _auto_fix_prompt(
        self,
        prompt: dict,
        report: QualityReport,
        main_character: str
    ) -> dict:
        """Auto-fix a prompt based on quality report"""
        fixed = prompt.copy()
        visual_prompt = fixed.get('visual_prompt', '')

        # Fix 1: Add character description if missing
        has_character_issue = any(i.issue_type == 'consistency' for i in report.issues)
        if has_character_issue and main_character:
            if not visual_prompt.lower().startswith(main_character.lower()[:20]):
                visual_prompt = f"{main_character}. {visual_prompt}"

        # Fix 2: Add camera/lighting if missing
        has_camera = any(word in visual_prompt.lower() for word in ['camera', 'shot', 'close-up', 'medium', 'wide', 'dolly', 'tracking'])
        has_lighting = any(word in visual_prompt.lower() for word in ['light', 'lighting', 'glow', 'shadow', 'neon'])

        additions = []
        if not has_camera:
            additions.append("Medium shot, smooth dolly-in")
        if not has_lighting:
            additions.append("atmospheric cinematic lighting")

        if additions:
            visual_prompt = f"{visual_prompt}. {', '.join(additions)}."

        # Fix 3: Handle truncation
        is_truncated = any(i.issue_type == 'quality' and 'truncated' in i.description.lower() for i in report.issues)
        if is_truncated and self.use_llm:
            visual_prompt = self._complete_truncated_prompt(visual_prompt)

        # Fix 4: Add negative prompt if missing (noun format, NOT "no X")
        if 'negative prompt:' not in visual_prompt.lower():
            visual_prompt = visual_prompt.rstrip('.') + '. Negative prompt: text overlays, subtitles, watermark, blurry, low quality, extra limbs, deformed anatomy, mutated.'

        # Fix 5: Replace quoted dialogue with colon syntax
        visual_prompt = re.sub(r'(\w+)\s+says\s*["\u201c]([^"\u201d]+)["\u201d]', r'\1 says: \2', visual_prompt)
        visual_prompt = re.sub(r'["\u201c]([^"\u201d]+)["\u201d]\s*,?\s*(\w+)\s+says', r'\2 says: \1', visual_prompt)

        # Fix 6: Add inline (no subtitles) if missing
        if '(no subtitles)' not in visual_prompt.lower() and 'no subtitles' not in visual_prompt.lower():
            if 'negative prompt:' in visual_prompt.lower():
                visual_prompt = re.sub(
                    r'(?i)negative prompt:',
                    '(no subtitles). Negative prompt:',
                    visual_prompt,
                    count=1
                )
            else:
                visual_prompt = visual_prompt.rstrip('.') + '. (no subtitles).'

        # Fix 7: Add default audio if missing
        if not any(w in visual_prompt.lower() for w in ['sfx:', 'ambient:', 'music:']):
            audio_block = 'SFX: subtle environmental sounds. Ambient: quiet atmosphere. Music: soft background score.'
            neg_idx = visual_prompt.lower().find('(no subtitles)')
            if neg_idx == -1:
                neg_idx = visual_prompt.lower().find('negative prompt:')
            if neg_idx > 0:
                visual_prompt = visual_prompt[:neg_idx] + audio_block + ' ' + visual_prompt[neg_idx:]
            else:
                visual_prompt += f' {audio_block}'

        fixed['visual_prompt'] = visual_prompt
        return fixed

    def _complete_truncated_prompt(self, prompt: str) -> str:
        """Use LLM to complete a truncated prompt"""
        if not self.client:
            return prompt.rstrip('.-') + "."

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Complete this truncated visual prompt for AI video generation. Keep it concise, add 1-2 sentences to complete the scene. Output in English."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=200,
                timeout=30,
            )
            completed = response.choices[0].message.content
            return completed.strip()
        except Exception as e:
            print(f"[QUALITY CHECKER] LLM completion failed: {e}")
            return prompt.rstrip('.-') + "."


# Singleton instance
_quality_checker = None


def get_quality_checker() -> QualityChecker:
    """Get or create the quality checker instance"""
    global _quality_checker
    if _quality_checker is None:
        _quality_checker = QualityChecker()
    return _quality_checker
