import os
import time
from django.core.management.base import BaseCommand
from django.conf import settings
from risk.models import Incident
from risk.ai import analyze_incident

class Command(BaseCommand):
    help = 'Diagnose Gemini AI integration for Risk module'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('--- Step 1: Checking API Key ---'))
        api_key = os.environ.get('GEMINI_API_KEY')
        if api_key:
            masked = f"{api_key[:4]}...{api_key[-4:]}" if len(api_key) > 8 else "***"
            self.stdout.write(self.style.SUCCESS(f"GEMINI_API_KEY found: {masked}"))
        else:
            self.stdout.write(self.style.ERROR("GEMINI_API_KEY is missing from environment!"))

        self.stdout.write(self.style.WARNING('\n--- Step 2: Direct Service Test ---'))
        dummy_incident = Incident(
            event="Direct Test Event",
            severity="high",
            ip="127.0.0.1",
            country="TestLand",
            details={'test_reason': 'manual_debug'}
        )
        # Note: We are passing an unsaved instance here, which is fine for analyze_incident 
        # as it just reads fields.
        
        try:
            self.stdout.write("Calling risk.ai.analyze_incident()...")
            response = analyze_incident(dummy_incident)
            if response:
                self.stdout.write(self.style.SUCCESS(f"AI Response received:\n{response[:100]}..."))
            else:
                self.stdout.write(self.style.ERROR("AI Response was None (Check logs/key)."))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Exception during AI call: {e}"))

        self.stdout.write(self.style.WARNING('\n--- Step 3: Signal Logic Test ---'))
        self.stdout.write("Creating High Severity Incident in DB...")
        
        try:
            # Create a real incident
            incident = Incident.objects.create(
                event="Signal Logic Diagnostic",
                severity="high",
                ip="10.0.0.1",
                country="SignalLand",
                details={'type': 'signal_test'}
            )
            self.stdout.write(f"Incident created with ID: {incident.id}")
            
            # Wait a moment if it involved async (it's sync now, but good practice)
            time.sleep(1)
            
            # Refresh from DB
            refreshed = Incident.objects.get(pk=incident.id)
            self.stdout.write(f"Refreshed gemini_analysis field: {refreshed.gemini_analysis}")
            
            if refreshed.gemini_analysis:
                self.stdout.write(self.style.SUCCESS("SUCCESS: Signal populated the field!"))
            else:
                self.stdout.write(self.style.ERROR("FAILURE: Field is still None. Signal logic or saving failed."))
                
        except Exception as e:
             self.stdout.write(self.style.ERROR(f"Exception during signal test: {e}"))
