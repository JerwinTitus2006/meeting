"""
OpenAI GPT-based AI Analysis Service
Provides intelligent extraction of pain points, action items, and solutions
from meeting transcripts using GPT-4 or GPT-3.5-turbo.
"""
import os
import logging
import json
from typing import List, Dict, Optional
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("ai-meet.openai")


class OpenAIService:
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.model = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
        self.enabled = bool(self.api_key and self.api_key != "your-openai-api-key-here")
        
        if not self.enabled:
            logger.warning(
                "⚠️  OPENAI_API_KEY not set – using fallback keyword-based AI. "
                "For better results, set OPENAI_API_KEY in .env"
            )
        else:
            logger.info(f"✅ OpenAI Service initialized with model: {self.model}")

    async def analyze_transcript(self, transcript_text: str) -> Dict:
        """
        Analyze transcript and extract pain points, action items, and sentiment.
        
        Args:
            transcript_text: Full meeting transcript
            
        Returns:
            dict with keys: pain_points, action_items, sentiment, summary
        """
        if not self.enabled:
            return self._fallback_analysis(transcript_text)
        
        try:
            import openai
            openai.api_key = self.api_key
            
            prompt = self._create_analysis_prompt(transcript_text)
            
            response = await openai.ChatCompletion.acreate(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an AI assistant specialized in analyzing business meeting transcripts. Extract pain points, action items, and provide sentiment analysis."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=2000,
            )
            
            result_text = response.choices[0].message.content
            analysis = self._parse_gpt_response(result_text)
            
            logger.info("✅ OpenAI analysis complete: %d pain points, %d actions", 
                       len(analysis["pain_points"]), len(analysis["action_items"]))
            return analysis
            
        except ImportError:
            logger.error("❌ OpenAI package not installed. Run: pip install openai")
            return self._fallback_analysis(transcript_text)
        except Exception as exc:
            logger.error(f"❌ OpenAI API error: {exc}")
            return self._fallback_analysis(transcript_text)

    def _create_analysis_prompt(self, transcript: str) -> str:
        return f"""Analyze this meeting transcript and provide a structured analysis in JSON format:

TRANSCRIPT:
{transcript[:4000]}  # Limit to avoid token limits

Please provide your analysis in the following JSON format:
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
Be thorough and specific."""

    def _parse_gpt_response(self, response_text: str) -> Dict:
        """Parse GPT JSON response"""
        try:
            # Try to extract JSON from response
            import re
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                return {
                    "pain_points": data.get("pain_points", []),
                    "action_items": data.get("action_items", []),
                    "sentiment": data.get("sentiment", {"overall": "neutral", "score": 50, "key_emotions": []}),
                    "summary": data.get("summary", "")
                }
        except Exception as exc:
            logger.error(f"Error parsing GPT response: {exc}")
        
        return self._fallback_analysis("")

    def _fallback_analysis(self, text: str) -> Dict:
        """Simple keyword-based fallback when OpenAI is not available"""
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
        """Generate solution steps for a pain point using GPT"""
        if not self.enabled:
            return self._fallback_solutions(category, severity)
        
        try:
            import openai
            openai.api_key = self.api_key
            
            prompt = f"""Generate 3-5 specific, actionable solution steps for this business problem:

Problem: {pain_point}
Category: {category}
Severity: {severity}

Provide solutions as a numbered list, focusing on immediate, practical actions."""

            response = await openai.ChatCompletion.acreate(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a business solutions expert."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.5,
                max_tokens=500,
            )
            
            solution_text = response.choices[0].message.content
            # Parse numbered list into array
            solutions = [
                line.strip() 
                for line in solution_text.split('\n') 
                if line.strip() and any(line.strip().startswith(f"{i}.") for i in range(1, 10))
            ]
            
            return solutions[:5] if solutions else self._fallback_solutions(category, severity)
            
        except Exception as exc:
            logger.error(f"Error generating solutions: {exc}")
            return self._fallback_solutions(category, severity)

    def _fallback_solutions(self, category: str, severity: str) -> List[str]:
        """Basic fallback solutions"""
        solutions = {
            "delivery": ["Contact logistics partner", "Track shipment status", "Provide customer update"],
            "pricing": ["Review pricing structure", "Analyze competitor pricing", "Discuss with finance team"],
            "quality": ["Conduct quality inspection", "Review quality standards", "Implement corrective actions"],
            "availability": ["Check inventory levels", "Contact suppliers", "Arrange alternative stock"],
            "service": ["Escalate to support manager", "Review service protocols", "Provide status update"],
            "other": ["Investigate the issue", "Document findings", "Create action plan"]
        }
        return solutions.get(category, solutions["other"])


# Singleton
openai_service = OpenAIService()
