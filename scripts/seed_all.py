from app.db import SessionLocal, init_db
from app.services.bootstrap_service import ensure_system_accounts


def main() -> None:
    init_db()
    with SessionLocal() as db:
        ensure_system_accounts(db)
    print("System accounts, topics and sources ensured.")


if __name__ == "__main__":
    main()
