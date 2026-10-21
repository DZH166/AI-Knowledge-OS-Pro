from app.db.session import SessionLocal
from app.modules.feedback.service import SqlFeedback


def get_feedback() -> SqlFeedback:
    return SqlFeedback(SessionLocal)
