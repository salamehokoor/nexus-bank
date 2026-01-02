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
        You are a Senior Security Operations Center (SOC) Analyst at a Digital Bank.
        A high-severity security incident has been detected.
        
        Incident Details:
        - Event: {incident.event}
        - Severity: {incident.severity}
        - IP Address: {incident.ip}
        - Country: {incident.country}
        - User Email: {incident.attempted_email or incident.user}
        - Context: {incident.details}
        
        Task:
        Provide a strict, step-by-step Course of Action for the administrator.
        Focus on containment, investigation, and remediation.
        Do NOT provide generic advice. Be specific to the details provided.
        Format constraints: Plain text, bullet points, concise.
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
