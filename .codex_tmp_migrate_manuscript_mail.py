from sqlalchemy import inspect, text

from database import engine
from mail_inline_image_models import MailInlineImage, MailInlineImageBinding


MailInlineImage.__table__.create(bind=engine, checkfirst=True)
MailInlineImageBinding.__table__.create(bind=engine, checkfirst=True)
with engine.begin() as connection:
    connection.execute(
        text(
            "ALTER TABLE manuscript_arrangement "
            "ADD COLUMN IF NOT EXISTS email_body_html TEXT"
        )
    )

db_inspector = inspect(engine)
tables = set(db_inspector.get_table_names())
columns = {
    item["name"]
    for item in db_inspector.get_columns("manuscript_arrangement")
}
assert "mail_inline_image" in tables
assert "mail_inline_image_binding" in tables
assert "email_body_html" in columns
print("MANUSCRIPT_MAIL_MIGRATION_OK")
