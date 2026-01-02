"""
WebSocket consumers for real-time notifications.
Handles user notifications and admin alerts via channel groups.
"""

import json
import logging

from channels.generic.websocket import AsyncJsonWebsocketConsumer
from asgiref.sync import sync_to_async

logger = logging.getLogger(__name__)


class NotificationConsumer(AsyncJsonWebsocketConsumer):
    """
    WebSocket consumer for real-time notifications.
    
    Groups:
    - user_{user_id}: Personal notifications for authenticated users
    - admin_alerts: System-wide alerts for staff/admin users
    
    Expected message format from channel layer:
    {
        "type": "user_notification" or "admin_alert",
        "event": "CREDIT" | "DEBIT" | etc.,
        "amount": "123.45",
        "timestamp": "2026-01-02T12:00:00Z",
        ...
    }
    """

    async def connect(self):
        """
        Handle WebSocket connection.
        Authenticated users join their personal group.
        Staff users additionally join admin_alerts group.
        """
        self.user = self.scope.get("user")
        self.groups_joined = []

        if self.user and self.user.is_authenticated:
            # Add to personal notification group
            user_group = f"user_{self.user.id}"
            await self.channel_layer.group_add(user_group, self.channel_name)
            self.groups_joined.append(user_group)
            logger.info(f"User {self.user.id} joined group: {user_group}")

            # Staff/Admin users also join admin_alerts
            is_staff = await sync_to_async(lambda: self.user.is_staff)()
            if is_staff:
                await self.channel_layer.group_add("admin_alerts", self.channel_name)
                self.groups_joined.append("admin_alerts")
                logger.info(f"Admin user {self.user.id} joined group: admin_alerts")

            await self.accept()
            # Send connection confirmation
            await self.send_json({
                "type": "connection_established",
                "message": "Connected to notification service",
                "groups": self.groups_joined,
            })
        else:
            # Reject unauthenticated connections
            logger.warning("Unauthenticated WebSocket connection rejected")
            await self.close(code=4001)

    async def disconnect(self, close_code):
        """Leave all groups on disconnect."""
        for group_name in self.groups_joined:
            await self.channel_layer.group_discard(group_name, self.channel_name)
            logger.info(f"Left group: {group_name}")

    async def receive_json(self, content):
        """
        Handle incoming messages from client.
        Currently, this is a push-only system; client messages are logged but not processed.
        """
        logger.debug(f"Received from client: {content}")
        # Could implement ping/pong, subscription management, etc.
        if content.get("type") == "ping":
            await self.send_json({"type": "pong"})

    # -------------------------------------------------------------------------
    # Handler methods for messages sent via channel layer
    # -------------------------------------------------------------------------

    async def user_notification(self, event):
        """
        Handle user notification events (credit/debit alerts).
        Message format: { "type": "user_notification", "event": "...", ... }
        """
        await self.send_json({
            "type": "user_notification",
            "event": event.get("event"),
            "amount": event.get("amount"),
            "currency": event.get("currency"),
            "account": event.get("account"),
            "timestamp": event.get("timestamp"),
            "message": event.get("message"),
        })

    async def admin_alert(self, event):
        """
        Handle admin alert events (security incidents).
        Message format: { "type": "admin_alert", "severity": "...", ... }
        """
        await self.send_json({
            "type": "admin_alert",
            "severity": event.get("severity"),
            "message": event.get("message"),
            "incident_id": event.get("incident_id"),
            "timestamp": event.get("timestamp"),
        })
