from google import genai
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

def analyze_incident(incident):
    """
    Analyzes a high-severity incident using Google Gemini.
    Returns a strict course of action.
    """
    if not settings.GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY not set. Skipping AI analysis.")
        return None

    try:
        # Use the newer Google GenAI Client
        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        
        prompt = f"""
        You are a Senior SOC Analyst. Analyze this security incident:
        
        - Event: {incident.event}
        - Severity: {incident.severity}
        - IP: {incident.ip} ({incident.country})
        - User: {incident.attempted_email or incident.user}
        - Context: {incident.details}
        
        Task:
        Provide a VERY SHORT, readable summary (under 60 words).
        1. Threat Assessment (1 sentence).
        2. Immediate Actions (2-3 concise bullet points).
        Do NOT provide generic advice. Be specific and brief.
        """
        
        # Use gemini-1.5-flash as it is the current standard/stable model
        response = client.models.generate_content(
            model="gemini-2.5-flash", 
            contents=prompt
        )
        return response.text
    except Exception as e:
        logger.error(f"Failed to generate AI analysis for incident {incident.id}: {e}")
        return f"AI Analysis Failed: {e}"
