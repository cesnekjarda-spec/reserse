from app.config import settings
from app.db import SessionLocal, init_db
from app.services.auth_service import ensure_admin_exists


def main():
    init_db()
    with SessionLocal() as db:
        ensure_admin_exists(db, settings.admin_email, settings.admin_password)
    print("Admin initialization finished.")


if __name__ == "__main__":
    main()
