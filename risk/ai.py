from google import genai
from django.conf import settings
import logging
import re

logger = logging.getLogger(__name__)


def determine_action(incident):
    """
    Deterministically determine the recommended action based on incident data.
    
    Returns one of:
    - "terminate" - For repeated fraud, critical severity, or confirmed malicious activity
    - "freeze" - For suspicious but reversible activity 
    - "block" - For temporary anomalies or minor violations
    - "monitor" - For low-risk events that need observation
    """
    event = (getattr(incident, 'event', '') or '').lower()
    severity = (getattr(incident, 'severity', '') or '').lower()
    details = getattr(incident, 'details', {}) or {}
    
    # Extract relevant metrics from details if available
    failed_attempts = details.get('failed_attempts', 0) if isinstance(details, dict) else 0
    velocity_violations = details.get('velocity_violations', 0) if isinstance(details, dict) else 0
    amount = details.get('amount', 0) if isinstance(details, dict) else 0
    
    # TERMINATE: Critical severity or confirmed fraud
    terminate_keywords = ['fraud', 'malicious', 'compromised', 'stolen', 'breach', 'hack']
    if severity == 'critical':
        return 'terminate'
    if any(kw in event for kw in terminate_keywords):
        return 'terminate'
    if failed_attempts and int(failed_attempts) > 10:
        return 'terminate'
    
    # FREEZE: High severity or suspicious reversible activity
    freeze_keywords = ['suspicious', 'unusual', 'anomaly', 'velocity', 'limit', 'overseas']
    if severity == 'high':
        return 'freeze'
    if any(kw in event for kw in freeze_keywords):
        return 'freeze'
    if velocity_violations and int(velocity_violations) > 3:
        return 'freeze'
    if amount and float(amount) > 10000:
        return 'freeze'
    
    # BLOCK: Medium severity or temporary issues
    block_keywords = ['failed', 'attempt', 'invalid', 'expired', 'timeout', 'locked']
    if severity == 'medium':
        return 'block'
    if any(kw in event for kw in block_keywords):
        return 'block'
    if failed_attempts and int(failed_attempts) > 3:
        return 'block'
    
    # MONITOR: Low severity or informational events
    return 'monitor'


def analyze_incident(incident):
    """
    Analyzes a high-severity incident using Google Gemini.
    Returns a strict course of action with a deterministic recommendation.
    """
    # Determine action first (deterministic, not AI-dependent)
    recommended_action = determine_action(incident)
    action_descriptions = {
        'terminate': 'TERMINATE - Immediately disable account/session and escalate to security team.',
        'freeze': 'FREEZE - Suspend account activity pending manual review.',
        'block': 'BLOCK - Temporarily restrict access until anomaly is resolved.',
        'monitor': 'MONITOR - Continue observation, no immediate action required.'
    }
    action_text = action_descriptions.get(recommended_action, 'MONITOR')
    
    if not settings.GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY not set. Returning action recommendation only.")
        return f"""
**TAKE ACTION: {action_text}**

AI analysis unavailable (API key not configured).

Based on event severity and type:
- Event: {getattr(incident, 'event', 'Unknown')}
- Severity: {getattr(incident, 'severity', 'Unknown')}
- Recommended Action: {recommended_action.upper()}
"""

    try:
        # Use the newer Google GenAI Client
        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        
        prompt = f"""
        You are a Senior SOC Analyst at NexusBank. Analyze this security incident:
        
        - Event: {incident.event}
        - Severity: {incident.severity}
        - IP: {incident.ip} ({incident.country})
        - User: {incident.attempted_email or incident.user}
        - Context: {incident.details}
        
        The system has already determined the recommended action: {recommended_action.upper()}
        
        Task:
        Provide a VERY SHORT, readable summary (under 60 words).
        1. Threat Assessment (1 sentence).
        2. Immediate Actions (2-3 concise bullet points).
        3. Justification for the {recommended_action.upper()} recommendation.
        
        Do NOT provide generic advice. Be specific and brief.
        End with: "TAKE ACTION: {action_text}"
        """
        
        # Use gemini-2.5-flash as it is the current standard/stable model
        response = client.models.generate_content(
            model="gemini-2.5-flash", 
            contents=prompt
        )
        
        analysis_text = response.text or ""
        
        # Ensure the action recommendation is always included
        if "TAKE ACTION" not in analysis_text:
            analysis_text += f"\n\n**TAKE ACTION: {action_text}**"
        
        return analysis_text
        
    except Exception as e:
        logger.error(f"Failed to generate AI analysis for incident {incident.id}: {e}")
        # Still return the deterministic action even if AI fails
        return f"""
AI Analysis Failed: {e}

**TAKE ACTION: {action_text}**

Based on automated risk assessment:
- Event: {getattr(incident, 'event', 'Unknown')}
- Severity: {getattr(incident, 'severity', 'Unknown')}  
- Recommended Action: {recommended_action.upper()}
"""
