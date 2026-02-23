"""
System health monitoring with Telegram/Email alerts.
"""
import redis
from datetime import datetime
from typing import Dict, List, Optional
from app.core.config import settings


class HealthChecker:
    """System health checks."""

    def check_all(self) -> Dict:
        """Run all health checks and return status."""
        checks = {
            "redis": self.check_redis(),
            "worker": self.check_worker(),
            "api_keys": self.check_api_keys(),
            "youtube_quota": self.check_youtube_quota(),
            "timestamp": datetime.utcnow().isoformat(),
        }
        checks["overall"] = all(
            c.get("healthy", False)
            for c in checks.values()
            if isinstance(c, dict) and "healthy" in c
        )
        return checks

    def check_redis(self) -> Dict:
        """Check Redis connection."""
        try:
            r = redis.from_url(settings.REDIS_URL)
            r.ping()
            info = r.info("memory")
            return {
                "healthy": True,
                "used_memory_human": info.get("used_memory_human", "unknown"),
            }
        except Exception as e:
            return {"healthy": False, "error": str(e)}

    def check_worker(self) -> Dict:
        """Check if RQ worker is alive."""
        try:
            from rq import Worker
            r = redis.from_url(settings.REDIS_URL)
            workers = Worker.all(connection=r)
            active = [w for w in workers if w.state == "busy" or w.state == "idle"]
            return {
                "healthy": len(active) > 0,
                "worker_count": len(active),
                "workers": [{"name": w.name, "state": w.state} for w in active],
            }
        except Exception as e:
            return {"healthy": False, "error": str(e)}

    def check_api_keys(self) -> Dict:
        """Check if essential API keys are configured."""
        keys = {
            "OPENAI_API_KEY": bool(settings.OPENAI_API_KEY),
            "REPLICATE_API_TOKEN": bool(settings.REPLICATE_API_TOKEN),
            "YOUTUBE_API_KEY": bool(settings.YOUTUBE_API_KEY),
            "YOUTUBE_CLIENT_ID": bool(settings.YOUTUBE_CLIENT_ID),
        }
        configured_count = sum(1 for v in keys.values() if v)
        return {
            "healthy": configured_count >= 1,  # At least one key configured
            "configured": keys,
            "configured_count": configured_count,
        }

    def check_youtube_quota(self) -> Dict:
        """Check YouTube API quota remaining."""
        try:
            from app.services.youtube.quota_tracker import QuotaTracker
            tracker = QuotaTracker()
            status = tracker.get_status()
            return {
                "healthy": status["remaining"] > 0,
                **status,
            }
        except Exception as e:
            return {"healthy": True, "error": str(e), "note": "quota check skipped"}


class AlertService:
    """Send alerts via Telegram and/or Email."""

    def send_alert(self, title: str, message: str, level: str = "warning"):
        """Send alert to all configured channels."""
        full_message = f"[{level.upper()}] {title}\n{message}"
        print(f"[ALERT] {full_message}")

        if settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_ID:
            self._send_telegram(full_message)

        if settings.ALERT_EMAIL and settings.SMTP_HOST:
            self._send_email(title, full_message)

    def _send_telegram(self, message: str):
        """Send alert via Telegram Bot API."""
        try:
            import requests
            url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
            requests.post(url, json={
                "chat_id": settings.TELEGRAM_CHAT_ID,
                "text": message,
                "parse_mode": "HTML",
            }, timeout=10)
        except Exception as e:
            print(f"[ALERT] Telegram send failed: {e}")

    def _send_email(self, subject: str, body: str):
        """Send alert via email."""
        try:
            import smtplib
            from email.mime.text import MIMEText

            msg = MIMEText(body)
            msg["Subject"] = f"AI Video Factory Alert: {subject}"
            msg["From"] = settings.SMTP_USER or "noreply@aivideo.local"
            msg["To"] = settings.ALERT_EMAIL

            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
                server.ehlo()
                if settings.SMTP_PORT == 587:
                    server.starttls()
                if settings.SMTP_USER and settings.SMTP_PASSWORD:
                    server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.sendmail(msg["From"], [settings.ALERT_EMAIL], msg.as_string())
        except Exception as e:
            print(f"[ALERT] Email send failed: {e}")


def run_health_check_and_alert():
    """Run health checks and send alerts for unhealthy components."""
    checker = HealthChecker()
    alerter = AlertService()
    results = checker.check_all()

    unhealthy = []
    for name, status in results.items():
        if isinstance(status, dict) and not status.get("healthy", True):
            unhealthy.append(f"- {name}: {status.get('error', 'unhealthy')}")

    if unhealthy:
        alerter.send_alert(
            "System Health Issue",
            "The following checks failed:\n" + "\n".join(unhealthy),
            level="critical",
        )

    return results


def notify_new_ideas(ideas: list):
    """Send Telegram notification when new story ideas are generated."""
    if not ideas:
        return

    genre_emoji = {
        "drama": "\U0001f3ad", "comedy": "\U0001f602", "horror": "\U0001f47b",
        "thriller": "\U0001f52a", "romance": "\u2764\ufe0f", "sci-fi": "\U0001f680",
        "mystery": "\U0001f50d",
    }

    lines = [f"\U0001f514 {len(ideas)} new video ideas\n"]
    for i, idea in enumerate(ideas, 1):
        emoji = genre_emoji.get(getattr(idea, "genre", ""), "\U0001f3ac")
        score = getattr(idea, "virality_score", 0)
        genre = getattr(idea, "genre", "unknown")
        text = getattr(idea, "idea_text", "")[:80]
        lines.append(f"{i}. {emoji} {genre.title()}: \"{text}...\" ({int(score * 100)}%)")

    lines.append("\n\u2192 Open /trends to approve")

    alerter = AlertService()
    alerter.send_alert("New Ideas", "\n".join(lines), level="info")


def notify_video_ready(review_item, idea=None):
    """Send Telegram notification when a video is ready for review."""
    title = getattr(review_item, "title", "Untitled")
    item_id = getattr(review_item, "id", "?")

    lines = [
        "\u2705 Video ready for review",
        f"\U0001f4dd \"{title}\"",
        f"\U0001f3ac ID: #{item_id}",
    ]

    if idea:
        genre = getattr(idea, "genre", "")
        score = getattr(idea, "virality_score", 0)
        if genre:
            lines.append(f"\U0001f3ad Genre: {genre.title()}")
        if score:
            lines.append(f"\u26a1 Virality: {int(score * 100)}%")

    lines.append("\n\u2192 Open /review to check")

    alerter = AlertService()
    alerter.send_alert("Video Ready", "\n".join(lines), level="info")
