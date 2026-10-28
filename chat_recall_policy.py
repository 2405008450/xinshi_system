from datetime import timedelta
from chat_time import BUSINESS_TIMEZONE, now


def can_recall_own(sender_id, user_id, created_at, recalled_at=None, current=None):
    if sender_id != user_id or created_at is None or recalled_at:
        return False
    created = created_at.replace(tzinfo=BUSINESS_TIMEZONE) if created_at.tzinfo is None else created_at
    current = current or now()
    if current.tzinfo is None:
        current = current.replace(tzinfo=BUSINESS_TIMEZONE)
    return timedelta(0) <= current - created <= timedelta(hours=1)
