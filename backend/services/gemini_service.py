"""
Google Gemini AI Analysis Service
Provides intelligent extraction of pain points, action items, and solutions
from meeting transcripts using Gemini Pro.
"""
import os
import logging
import json
import re
from typing import List, Dict, Optional
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("ai-meet.gemini")


class GeminiService:
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.model_name = os.getenv("GEMINI_MODEL", "gemini-pro")
        self.enabled = bool(self.api_key and self.api_key != "your-gemini-api-key-here")
        self.client = None
        
        if not self.enabled:
            logger.warning(
                "⚠️  GEMINI_API_KEY not set – using fallback keyword-based AI. "
                "For better results, set GEMINI_API_KEY in .env"
            )
        else:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.api_key)
                self.client = genai.GenerativeModel(self.model_name)
                logger.info(f"✅ Gemini Service initialized with model: {self.model_name}")
            except ImportError:
                logger.error("❌ google-generativeai package not installed. Run: pip install google-generativeai")
                self.enabled = False
            except Exception as exc:
                logger.error(f"❌ Gemini initialization error: {exc}")
                self.enabled = False

    async def analyze_transcript(self, transcript_text: str) -> Dict:
        """
        Analyze transcript and extract pain points, action items, and sentiment.
        
        Args:
            transcript_text: Full meeting transcript
            
        Returns:
            dict with keys: pain_points, action_items, sentiment, summary
        """
        if not self.enabled or not self.client:
            return self._fallback_analysis(transcript_text)
        
        try:
            prompt = self._create_analysis_prompt(transcript_text)
            
            # Gemini API call
            response = self.client.generate_content(prompt)
            
            if not response or not response.text:
                logger.error("❌ Empty response from Gemini")
                return self._fallback_analysis(transcript_text)
            
            result_text = response.text
            analysis = self._parse_gemini_response(result_text)
            
            logger.info("✅ Gemini analysis complete: %d pain points, %d actions", 
                       len(analysis["pain_points"]), len(analysis["action_items"]))
            return analysis
            
        except Exception as exc:
            logger.error(f"❌ Gemini API error: {exc}")
            return self._fallback_analysis(transcript_text)

    def _create_analysis_prompt(self, transcript: str) -> str:
        return f"""Analyze this meeting transcript and provide a structured analysis in JSON format.

TRANSCRIPT:
{transcript[:4000]}

Please provide your analysis in the following JSON format (respond ONLY with valid JSON, no markdown formatting):
{{
    "pain_points": [
        {{
            "issue": "Brief description of the pain point",
            "category": "delivery|pricing|quality|availability|service|other",
            "severity": "critical|high|medium|low",
            "context": "Relevant quote from transcript"
        }}
    ],
    "action_items": [
        {{
            "task": "Description of the action item",
            "assignee": "Person responsible (or 'Unassigned')",
            "priority": "urgent|high|medium|low",
            "deadline": "If mentioned, otherwise null"
        }}
    ],
    "sentiment": {{
        "overall": "positive|neutral|negative",
        "score": 0-100,
        "key_emotions": ["emotion1", "emotion2"]
    }},
    "summary": "Brief 2-3 sentence summary of the meeting"
}}

Extract ALL pain points, issues, concerns, problems mentioned.
Extract ALL action items, commitments, tasks, and next steps.
Be thorough and specific. Return valid JSON only."""

    def _parse_gemini_response(self, response_text: str) -> Dict:
        """Parse Gemini JSON response"""
        try:
            # Remove markdown code blocks if present
            text = response_text.strip()
            if text.startswith("```"):
                # Remove ```json or ``` at start and ``` at end
                text = re.sub(r'^```(?:json)?\s*\n', '', text)
                text = re.sub(r'\n```\s*$', '', text)
            
            # Try to extract JSON from response
            json_match = re.search(r'\{.*\}', text, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                return {
                    "pain_points": data.get("pain_points", []),
                    "action_items": data.get("action_items", []),
                    "sentiment": data.get("sentiment", {"overall": "neutral", "score": 50, "key_emotions": []}),
                    "summary": data.get("summary", "")
                }
        except Exception as exc:
            logger.error(f"Error parsing Gemini response: {exc}")
            logger.debug(f"Response text: {response_text[:500]}")
        
        return self._fallback_analysis("")

    def _fallback_analysis(self, text: str) -> Dict:
        """Simple keyword-based fallback when Gemini is not available"""
        return {
            "pain_points": [],
            "action_items": [],
            "sentiment": {
                "overall": "neutral",
                "score": 50,
                "key_emotions": []
            },
            "summary": ""
        }

    async def generate_solutions(self, pain_point: str, category: str, severity: str) -> List[str]:
        """Generate solution steps for a pain point using Gemini"""
        if not self.enabled or not self.client:
            return self._fallback_solutions(category, severity)
        
        try:
            prompt = f"""Generate 3-5 specific, actionable solution steps for this business problem:

Problem: {pain_point}
Category: {category}
Severity: {severity}

Provide solutions as a numbered list (1. 2. 3. etc.), focusing on immediate, practical actions.
Return ONLY the numbered list, no additional text."""

            response = self.client.generate_content(prompt)
            
            if not response or not response.text:
                return self._fallback_solutions(category, severity)
            
            solution_text = response.text
            # Parse numbered list into array
            solutions = []
            for line in solution_text.split('\n'):
                line = line.strip()
                if line and any(line.startswith(f"{i}.") for i in range(1, 10)):
                    # Remove the number prefix
                    clean_line = re.sub(r'^\d+\.\s*', '', line)
                    solutions.append(clean_line)
            
            logger.info(f"💡 Gemini generated {len(solutions)} solutions")
            return solutions[:5] if solutions else self._fallback_solutions(category, severity)
            
        except Exception as exc:
            logger.error(f"Error generating Gemini solutions: {exc}")
            return self._fallback_solutions(category, severity)

    def _fallback_solutions(self, category: str, severity: str) -> List[str]:
        """Basic fallback solutions"""
        solutions = {
            "delivery": ["Contact logistics partner immediately", "Track shipment status and update stakeholders", "Provide customer with timeline update"],
            "pricing": ["Review pricing structure with finance team", "Analyze competitor pricing", "Discuss volume discounts or alternatives"],
            "quality": ["Conduct immediate quality inspection", "Review quality control standards", "Implement corrective actions and document findings"],
            "availability": ["Check current inventory levels", "Contact suppliers for expedited delivery", "Identify and arrange alternative stock"],
            "service": ["Escalate to support manager", "Review and improve service protocols", "Provide detailed status update to stakeholders"],
            "other": ["Investigate the issue thoroughly", "Document findings and impact", "Create detailed action plan with timeline"]
        }
        return solutions.get(category, solutions["other"])


# Singleton
gemini_service = GeminiService()
