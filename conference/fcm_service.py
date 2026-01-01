import os
import logging
from typing import List, Dict, Optional
import firebase_admin
from firebase_admin import credentials, messaging
from django.conf import settings

logger = logging.getLogger(__name__)


class FCMService:
    """Service for sending Firebase Cloud Messaging notifications"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(FCMService, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._initialized = True
        self._app = None
        self._init_firebase()

    def _init_firebase(self) -> bool:
        """Initialize Firebase Admin SDK"""
        try:
            # Check if Firebase is already initialized
            if firebase_admin._apps:
                self._app = firebase_admin.get_app()
            else:
                # Get credentials path from environment or settings
                creds_path = getattr(
                    settings,
                    'FIREBASE_CREDENTIALS_PATH',
                    os.environ.get('FIREBASE_CREDENTIALS_PATH')
                )

                if not creds_path:
                    logger.warning(
                        "FIREBASE_CREDENTIALS_PATH not configured. FCM notifications disabled."
                    )
                    return False

                if not os.path.exists(creds_path):
                    logger.error(
                        f"Firebase credentials file not found: {creds_path}")
                    return False

                creds = credentials.Certificate(creds_path)
                self._app = firebase_admin.initialize_app(creds)
                logger.info("Firebase Admin SDK initialized successfully")

            return True
        except Exception as e:
            logger.error(f"Failed to initialize Firebase: {str(e)}")
            return False

    def send_notification(
        self,
        token: str,
        title: str,
        body: str,
        data: Optional[Dict] = None,
        badge: int = 1,
    ) -> bool:
        """
        Send a notification to a single device

        Args:
            token: FCM device token
            title: Notification title
            body: Notification body
            data: Additional data to send with the notification
            badge: Badge count for the app icon

        Returns:
            True if sent successfully, False otherwise
        """
        if not self._app:
            logger.warning(
                "Firebase not initialized. Cannot send notification.")
            return False

        try:
            message = messaging.Message(
                notification=messaging.Notification(
                    title=title,
                    body=body,
                ),
                data=data or {},
                webpush=messaging.WebpushConfig(
                    notification=messaging.WebpushNotification(
                        title=title,
                        body=body,
                        badge=str(badge),
                    ),
                    data=data or {},
                ),
                apns=messaging.APNSConfig(
                    payload=messaging.APNSPayload(
                        aps=messaging.Aps(
                            alert=messaging.ApsAlert(
                                title=title,
                                body=body,
                            ),
                            badge=badge,
                            sound='default',
                        ),
                    ),
                    custom_data=data or {},
                ),
                android=messaging.AndroidConfig(
                    notification=messaging.AndroidNotification(
                        title=title,
                        body=body,
                        click_action='FLUTTER_NOTIFICATION_CLICK',
                        sound='default',
                    ),
                    data=data or {},
                ),
                token=token,
            )

            response = messaging.send(message)
            logger.info(
                f"FCM notification sent successfully. Message ID: {response}")
            return True

        except messaging.InvalidArgumentError as e:
            logger.error(f"Invalid FCM token: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Error sending FCM notification: {str(e)}")
            return False

    def send_multicast(
        self,
        tokens: List[str],
        title: str,
        body: str,
        data: Optional[Dict] = None,
    ) -> Dict:
        """
        Send a notification to multiple devices

        Args:
            tokens: List of FCM device tokens
            title: Notification title
            body: Notification body
            data: Additional data to send with the notification

        Returns:
            Dictionary with 'success' and 'failed' counts and lists
        """
        if not self._app:
            logger.warning(
                "Firebase not initialized. Cannot send multicast notification.")
            return {"success": 0, "failed": len(tokens), "failed_tokens": tokens}

        if not tokens:
            return {"success": 0, "failed": 0, "failed_tokens": []}

        try:
            message = messaging.MulticastMessage(
                notification=messaging.Notification(
                    title=title,
                    body=body,
                ),
                data=data or {},
                webpush=messaging.WebpushConfig(
                    notification=messaging.WebpushNotification(
                        title=title,
                        body=body,
                    ),
                    data=data or {},
                ),
                apns=messaging.APNSConfig(
                    payload=messaging.APNSPayload(
                        aps=messaging.Aps(
                            alert=messaging.ApsAlert(
                                title=title,
                                body=body,
                            ),
                            sound='default',
                        ),
                    ),
                    custom_data=data or {},
                ),
                android=messaging.AndroidConfig(
                    notification=messaging.AndroidNotification(
                        title=title,
                        body=body,
                        click_action='FLUTTER_NOTIFICATION_CLICK',
                        sound='default',
                    ),
                    data=data or {},
                ),
                tokens=tokens,
            )

            response = messaging.send_multicast(message)

            failed_tokens = []
            for idx, send_response in enumerate(response.responses):
                if not send_response.success:
                    failed_tokens.append(tokens[idx])
                    logger.warning(
                        f"Failed to send message to token {tokens[idx]}: "
                        f"{send_response.exception}"
                    )

            logger.info(
                f"Multicast notification sent. Success: {response.success_count}, "
                f"Failed: {response.failure_count}"
            )

            return {
                "success": response.success_count,
                "failed": response.failure_count,
                "failed_tokens": failed_tokens,
            }

        except Exception as e:
            logger.error(f"Error sending multicast notification: {str(e)}")
            return {
                "success": 0,
                "failed": len(tokens),
                "failed_tokens": tokens,
                "error": str(e),
            }

    def send_invitation_notification(
        self,
        user_tokens: List[str],
        inviter_name: str,
        conference_name: str,
        invitation_id: int,
    ) -> Dict:
        """
        Send invitation notification to user devices

        Args:
            user_tokens: List of user's FCM device tokens
            inviter_name: Name of the user sending the invitation
            conference_name: Name of the conference
            invitation_id: ID of the invitation

        Returns:
            Result dictionary from send_multicast
        """
        title = "نتایج جدید 📨"  # "New Invitation" in Persian
        # "{name} invited you to {conference}"
        body = f"{inviter_name} شما را برای '{conference_name}' دعوت کرد"
        data = {
            "type": "invitation",
            "invitation_id": str(invitation_id),
            "conference_name": conference_name,
        }

        return self.send_multicast(user_tokens, title, body, data)

    def send_permission_update_notification(
        self,
        user_tokens: List[str],
        conference_name: str,
        permissions: List[str],
    ) -> Dict:
        """
        Notify user of permission updates

        Args:
            user_tokens: List of user's FCM device tokens
            conference_name: Name of the conference
            permissions: List of permission names granted

        Returns:
            Result dictionary from send_multicast
        """
        title = "تغییر دسترسی‌ها 🔐"  # "Permissions Updated" in Persian
        # "Your permissions for {conference} have been updated"
        body = f"دسترسی‌های شما برای '{conference_name}' تغییر کرد"
        data = {
            "type": "permissions_updated",
            "conference_name": conference_name,
            "permissions_count": str(len(permissions)),
        }

        return self.send_multicast(user_tokens, title, body, data)

    def cleanup_invalid_token(self, token: str) -> None:
        """
        Remove an invalid FCM token from the database

        Args:
            token: The invalid FCM device token
        """
        try:
            from conference.models import UserFCMDevice
            UserFCMDevice.objects.filter(device_token=token).delete()
            logger.info(f"Removed invalid FCM token from database")
        except Exception as e:
            logger.error(f"Error removing invalid token: {str(e)}")


# Singleton instance
fcm_service = FCMService()
