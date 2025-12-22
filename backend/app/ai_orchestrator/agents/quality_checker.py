"""
Quality Check Agent - validates and auto-fixes episode prompts before video generation.

This agent uses LLM to analyze prompts for:
1. Logical consistency between episodes
2. Character description consistency
3. Completeness (enough detail for video generation)
4. Moderation safety (no banned words)
5. Quality of writing (no glitches, truncation)
"""
import os
import json
from typing import List, Optional
from dataclasses import dataclass


@dataclass
class QualityIssue:
    """Represents a quality issue found in a prompt"""
    episode_number: int
    issue_type: str  # 'consistency', 'incomplete', 'moderation', 'logic', 'quality'
    severity: str  # 'low', 'medium', 'high'
    description: str
    suggested_fix: Optional[str] = None


@dataclass
class QualityReport:
    """Quality report for an episode prompt"""
    episode_number: int
    score: int  # 0-100
    issues: List[QualityIssue]
    fixed_prompt: Optional[str] = None  # Auto-fixed version if needed


class QualityChecker:
    """
    Agent that checks quality of generated prompts and auto-fixes issues.
    """
    
    # Words that trigger Google moderation
    BANNED_WORDS = [
        'weapon', 'gun', 'knife', 'sword', 'blood', 'violence', 'fight', 
        'combat', 'tactical', 'military', 'kill', 'death', 'attack', 'battle',
        'murder', 'assault', 'bomb', 'explosion', 'shooting', 'stab'
    ]
    
    # Safe replacements
    SAFE_REPLACEMENTS = {
        'weapon': 'object',
        'gun': 'device',
        'knife': 'tool',
        'sword': 'staff',
        'blood': 'red color',
        'violence': 'intensity',
        'fight': 'confrontation',
        'combat': 'athletic',
        'tactical': 'athletic',
        'military': 'uniform',
        'kill': 'defeat',
        'death': 'end',
        'attack': 'approach',
        'battle': 'challenge',
        'murder': 'mystery',
        'assault': 'approach',
        'bomb': 'device',
        'explosion': 'flash',
        'shooting': 'chase',
        'stab': 'gesture'
    }
    
    def __init__(self):
        """Initialize the Quality Checker with LLM client"""
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
                print("[QUALITY CHECKER] Warning: openai package not installed, using rule-based checks only")
                self.use_llm = False
    
    def check_and_fix_prompts(
        self, 
        prompts: List[dict],
        main_character: str = ""
    ) -> tuple[List[dict], List[QualityReport]]:
        """
        Check all prompts for quality issues and auto-fix them.
        
        Args:
            prompts: List of episode dicts with 'number', 'title', 'synopsis', 'visual_prompt'
            main_character: The main character description for consistency check
            
        Returns:
            Tuple of (fixed_prompts, quality_reports)
        """
        print(f"[QUALITY CHECKER] Checking {len(prompts)} prompts...")
        
        reports = []
        fixed_prompts = []
        
        for prompt in prompts:
            # Check individual prompt
            report = self._check_single_prompt(prompt, main_character, prompts)
            
            # Auto-fix if score < 70
            if report.score < 70:
                fixed_prompt = self._auto_fix_prompt(prompt, report, main_character)
                report.fixed_prompt = fixed_prompt.get('visual_prompt')
                fixed_prompts.append(fixed_prompt)
                print(f"[QUALITY CHECKER] Episode {prompt.get('number')}: {report.score}/100 - AUTO-FIXED")
            else:
                fixed_prompts.append(prompt)
                print(f"[QUALITY CHECKER] Episode {prompt.get('number')}: {report.score}/100 - OK")
            
            reports.append(report)
        
        # Check story continuity between episodes if we have multiple episodes
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
        """
        Use LLM to check and fix story continuity between episodes.
        Returns fixed prompts and list of issues found.
        """
        if not self.client:
            return prompts, []
        
        issues_found = []
        
        try:
            # Prepare synopsis list for LLM
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
                max_tokens=500
            )
            
            result_text = response.choices[0].message.content
            
            # Try to parse JSON response
            try:
                # Clean markdown if present
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
                            
                            # Apply fix by adding transition text
                            if fix and 0 < ep_num <= len(prompts):
                                idx = ep_num - 1
                                current_prompt = prompts[idx].get('visual_prompt', '')
                                # Add transition hint at the beginning
                                prompts[idx] = prompts[idx].copy()
                                prompts[idx]['visual_prompt'] = f"{current_prompt} Transition: {fix}"
                                print(f"[QUALITY CHECKER] Applied fix to Episode {ep_num}")
            except json.JSONDecodeError:
                pass  # LLM didn't return valid JSON, skip
                
        except Exception as e:
            print(f"[QUALITY CHECKER] Continuity check error: {e}")
        
        return prompts, issues_found
    
    def _check_single_prompt(
        self, 
        prompt: dict, 
        main_character: str,
        all_prompts: List[dict]
    ) -> QualityReport:
        """Check a single prompt for quality issues"""
        issues = []
        score = 100
        
        visual_prompt = prompt.get('visual_prompt', '')
        episode_num = prompt.get('number', 0)
        
        # Check 1: Prompt length (completeness)
        if len(visual_prompt) < 50:
            issues.append(QualityIssue(
                episode_number=episode_num,
                issue_type='incomplete',
                severity='high',
                description='Prompt too short (< 50 chars)',
                suggested_fix='Add more visual details'
            ))
            score -= 30
        elif len(visual_prompt) < 80:
            issues.append(QualityIssue(
                episode_number=episode_num,
                issue_type='incomplete',
                severity='medium',
                description='Prompt could use more detail (< 80 chars)'
            ))
            score -= 10
        
        # Check 2: Character consistency - should contain main character description
        if main_character:
            # Extract key identifiers from main character
            char_parts = main_character.lower().split(',')[:3]  # First 3 parts (name, age, ethnicity)
            matches = sum(1 for part in char_parts if part.strip() in visual_prompt.lower())
            if matches < 2:
                issues.append(QualityIssue(
                    episode_number=episode_num,
                    issue_type='consistency',
                    severity='high',
                    description='Character description missing or inconsistent',
                    suggested_fix=f'Add: {main_character}'
                ))
                score -= 25
        
        # Check 3: Banned words (moderation)
        found_banned = []
        for word in self.BANNED_WORDS:
            if word.lower() in visual_prompt.lower():
                found_banned.append(word)
        
        if found_banned:
            issues.append(QualityIssue(
                episode_number=episode_num,
                issue_type='moderation',
                severity='high',
                description=f'Contains banned words: {", ".join(found_banned)}',
                suggested_fix='Replace with safe alternatives'
            ))
            score -= 20 * len(found_banned)
        
        # Check 4: Truncation detection
        if visual_prompt.endswith('...') or visual_prompt.endswith('-'):
            issues.append(QualityIssue(
                episode_number=episode_num,
                issue_type='quality',
                severity='high',
                description='Prompt appears truncated',
                suggested_fix='Regenerate or complete the prompt'
            ))
            score -= 25
        
        # Check 5: Basic quality - has camera/lighting instructions
        has_camera = any(word in visual_prompt.lower() for word in ['camera', 'shot', 'close-up', 'medium', 'wide', 'pan', 'zoom'])
        has_lighting = any(word in visual_prompt.lower() for word in ['light', 'lighting', 'glow', 'shadow', 'neon', 'dark', 'bright'])
        
        if not has_camera:
            issues.append(QualityIssue(
                episode_number=episode_num,
                issue_type='quality',
                severity='low',
                description='Missing camera instructions'
            ))
            score -= 5
        
        if not has_lighting:
            issues.append(QualityIssue(
                episode_number=episode_num,
                issue_type='quality',
                severity='low',
                description='Missing lighting description'
            ))
            score -= 5
        
        # Ensure score is 0-100
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
        
        # Fix 1: Replace banned words
        for word, replacement in self.SAFE_REPLACEMENTS.items():
            import re
            visual_prompt = re.sub(
                rf'\b{word}\b', 
                replacement, 
                visual_prompt, 
                flags=re.IGNORECASE
            )
        
        # Fix 2: Add character description if missing
        has_character_issue = any(i.issue_type == 'consistency' for i in report.issues)
        if has_character_issue and main_character:
            # Prepend character description
            if not visual_prompt.lower().startswith(main_character.lower()[:20]):
                visual_prompt = f"{main_character}. {visual_prompt}"
        
        # Fix 3: Add camera/lighting if missing
        has_camera = any(word in visual_prompt.lower() for word in ['camera', 'shot', 'close-up', 'medium', 'wide'])
        has_lighting = any(word in visual_prompt.lower() for word in ['light', 'lighting', 'glow', 'shadow', 'neon'])
        
        additions = []
        if not has_camera:
            additions.append("Medium shot, smooth camera movement")
        if not has_lighting:
            additions.append("atmospheric lighting")
        
        if additions:
            visual_prompt = f"{visual_prompt}. {', '.join(additions)}."
        
        # Fix 4: Handle truncation - use LLM if available
        is_truncated = any(i.issue_type == 'quality' and 'truncated' in i.description.lower() for i in report.issues)
        if is_truncated and self.use_llm:
            visual_prompt = self._complete_truncated_prompt(visual_prompt)
        
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
                    {"role": "system", "content": "Complete this truncated visual prompt for AI video generation. Keep it concise, add 1-2 sentences to complete the scene."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=200
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
