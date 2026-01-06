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
    - "freeze" - For suspicious patterns that need immediate halt pending review
    - "block" - For repeated violations that warrant temporary restriction
    - "monitor" - For suspicious but not dangerous events that need observation
    - "no_action" - For benign events, routine operations, or false positives
    """
    event = (getattr(incident, 'event', '') or '').lower()
    severity = (getattr(incident, 'severity', '') or '').lower()
    details = getattr(incident, 'details', {}) or {}
    
    # Extract relevant metrics from details if available
    failed_attempts = details.get('failed_attempts', 0) if isinstance(details, dict) else 0
    velocity_violations = details.get('velocity_violations', 0) if isinstance(details, dict) else 0
    amount = details.get('amount', 0) if isinstance(details, dict) else 0
    
    # =========================================================================
    # NO_ACTION: Benign events that don't require any intervention
    # =========================================================================
    no_action_keywords = [
        'password reset', 'reset password', 'forgot password', 'password recovery',
        'email verification', 'account activation', 'successful login', 
        'session refresh', 'token refresh', 'logout', 'profile update',
        'settings change', 'notification', 'info', 'informational'
    ]
    if any(kw in event for kw in no_action_keywords):
        return 'no_action'
    
    # Also no action for very low severity or info-level events
    if severity in ['info', 'informational', 'low'] and failed_attempts == 0:
        return 'no_action'
    
    # =========================================================================
    # TERMINATE: Critical severity or confirmed fraud/breach
    # =========================================================================
    terminate_keywords = ['fraud confirmed', 'malicious', 'compromised', 'stolen', 'data breach', 'hack confirmed']
    if severity == 'critical':
        return 'terminate'
    if any(kw in event for kw in terminate_keywords):
        return 'terminate'
    if failed_attempts and int(failed_attempts) > 15:
        return 'terminate'
    
    # =========================================================================
    # FREEZE: High severity or suspicious patterns needing immediate halt
    # =========================================================================
    freeze_keywords = ['credential stuffing', 'brute force', 'impossible travel', 'overseas transaction']
    if severity == 'high':
        return 'freeze'
    if any(kw in event for kw in freeze_keywords):
        return 'freeze'
    if velocity_violations and int(velocity_violations) > 5:
        return 'freeze'
    if amount and float(amount) > 25000:
        return 'freeze'
    
    # =========================================================================
    # BLOCK: Medium severity or repeated issues needing temporary restriction
    # =========================================================================
    block_keywords = ['multiple failed', 'repeated failure', 'rate limit exceeded', 'locked out']
    if severity == 'medium' and failed_attempts and int(failed_attempts) > 5:
        return 'block'
    if any(kw in event for kw in block_keywords):
        return 'block'
    if failed_attempts and int(failed_attempts) > 8:
        return 'block'
    
    # =========================================================================
    # MONITOR: Suspicious but not dangerous, needs observation
    # =========================================================================
    monitor_keywords = ['unusual', 'anomaly', 'new device', 'new location', 'suspicious', 'first time']
    if severity == 'medium':
        return 'monitor'
    if any(kw in event for kw in monitor_keywords):
        return 'monitor'
    if failed_attempts and int(failed_attempts) > 2:
        return 'monitor'
    
    # Default: No action for anything that doesn't match threat patterns
    return 'no_action'


def analyze_incident(incident):
    """
    Analyzes a security incident using Google Gemini AI.
    Returns a comprehensive analysis with a deterministic action recommendation.
    """
    # Determine action first (deterministic, not AI-dependent)
    recommended_action = determine_action(incident)
    
    action_descriptions = {
        'terminate': 'TERMINATE - Immediately disable account/session and escalate to security team for investigation.',
        'freeze': 'FREEZE - Suspend account activity pending manual security review. User should be notified.',
        'block': 'BLOCK - Temporarily restrict access until the issue is resolved or verified.',
        'monitor': 'MONITOR - Continue observation and logging. No immediate action required.',
        'no_action': 'NO ACTION REQUIRED - This is a routine event or false positive. No intervention needed.'
    }
    action_text = action_descriptions.get(recommended_action, 'NO ACTION REQUIRED')
    
    if not settings.GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY not set. Returning action recommendation only.")
        return f"""
## Security Incident Analysis

**Event:** {getattr(incident, 'event', 'Unknown')}
**Severity:** {getattr(incident, 'severity', 'Unknown')}

### Assessment
AI analysis unavailable (API key not configured). Based on automated risk assessment rules.

### Recommendation
**{action_text}**

---
*Automated analysis based on event type and severity.*
"""

    try:
        # Use the newer Google GenAI Client
        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        
        prompt = f"""You are a Senior Security Operations Center (SOC) Analyst at NexusBank, a digital banking platform. 
Analyze the following security incident and provide a professional, detailed assessment.

## Incident Details
- **Event Type:** {incident.event}
- **Severity Level:** {incident.severity}
- **Source IP:** {incident.ip} ({incident.country})
- **User/Target:** {incident.attempted_email or incident.user or 'Unknown'}
- **Additional Context:** {incident.details}

## Pre-determined Action
The automated system has determined the recommended action: **{recommended_action.upper()}**
Action meaning: {action_text}

## Your Task
Provide a comprehensive security analysis (150-200 words) that includes:

1. **Threat Assessment** (2-3 sentences)
   - What type of security event is this?
   - What is the potential risk level and impact?

2. **Root Cause Analysis** (1-2 sentences)
   - What likely caused this incident?
   - Is this a user error, system issue, or potential attack?

3. **Recommended Actions** (3-4 bullet points)
   - What specific steps should the security team take?
   - Include both immediate and follow-up actions.

4. **Risk Context** (1-2 sentences)
   - How does this fit into broader security patterns?
   - Any patterns or trends to watch for?

## Important Guidelines
- Be specific to THIS incident, not generic security advice
- If this appears to be a benign event (password reset, normal login failure), say so clearly
- For routine events, recommend minimal or no intervention
- Format your response with clear headers using **bold**

End your analysis with:
**RECOMMENDED ACTION: {action_text}**
"""
        
        # Use gemini-2.5-flash as it is the current standard/stable model
        response = client.models.generate_content(
            model="gemini-2.5-flash", 
            contents=prompt
        )
        
        analysis_text = response.text or ""
        
        # Ensure the action recommendation is always included
        if "RECOMMENDED ACTION" not in analysis_text.upper():
            analysis_text += f"\n\n**RECOMMENDED ACTION: {action_text}**"
        
        return analysis_text
        
    except Exception as e:
        logger.error(f"Failed to generate AI analysis for incident {incident.id}: {e}")
        # Still return the deterministic action even if AI fails
        return f"""
## Security Incident Analysis

**Event:** {getattr(incident, 'event', 'Unknown')}
**Severity:** {getattr(incident, 'severity', 'Unknown')}

### AI Analysis Error
Unable to generate detailed analysis: {e}

### Automated Assessment
Based on the event type and severity level, the system has made the following determination:

- **Event Classification:** {getattr(incident, 'event', 'Unknown')}
- **Severity:** {getattr(incident, 'severity', 'Unknown')}
- **Action Determined:** {recommended_action.upper()}

### Recommendation
**{action_text}**

---
*Please review this incident manually if AI analysis is consistently unavailable.*
"""
