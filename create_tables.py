from sqlalchemy import inspect, text

from database import Base, engine
import models  # noqa: F401


REQUIRED_COLUMNS = {
    "users": {"id", "username", "email", "password_hash", "created_at"},
    "uploaded_papers": {"id", "user_id", "filename", "filepath", "upload_time"},
    "chat_history": {"id", "user_id", "question", "answer", "created_at"},
    "search_history": {"id", "user_id", "query", "searched_at"},
    "favorites": {"id", "user_id", "paper_name", "saved_at"},
    "query_logs": {"id", "user_id", "query", "response_time", "timestamp"},
}

COLUMN_DEFINITIONS = {
    "users": {
        "id": "INTEGER",
        "username": "VARCHAR(100)",
        "email": "VARCHAR(200)",
        "password_hash": "VARCHAR(255)",
        "created_at": "TIMESTAMP WITH TIME ZONE DEFAULT now()",
    },
    "uploaded_papers": {
        "id": "INTEGER",
        "user_id": "INTEGER REFERENCES users(id) ON DELETE CASCADE",
        "filename": "VARCHAR(300)",
        "filepath": "VARCHAR(500)",
        "upload_time": "TIMESTAMP WITH TIME ZONE DEFAULT now()",
    },
    "chat_history": {
        "id": "INTEGER",
        "user_id": "INTEGER REFERENCES users(id) ON DELETE CASCADE",
        "question": "TEXT",
        "answer": "TEXT",
        "created_at": "TIMESTAMP WITH TIME ZONE DEFAULT now()",
    },
    "search_history": {
        "id": "INTEGER",
        "user_id": "INTEGER REFERENCES users(id) ON DELETE CASCADE",
        "query": "TEXT",
        "searched_at": "TIMESTAMP WITH TIME ZONE DEFAULT now()",
    },
    "favorites": {
        "id": "INTEGER",
        "user_id": "INTEGER REFERENCES users(id) ON DELETE CASCADE",
        "paper_name": "VARCHAR(300)",
        "saved_at": "TIMESTAMP WITH TIME ZONE DEFAULT now()",
    },
    "query_logs": {
        "id": "INTEGER",
        "user_id": "INTEGER REFERENCES users(id) ON DELETE CASCADE",
        "query": "TEXT",
        "response_time": "DOUBLE PRECISION",
        "timestamp": "TIMESTAMP WITH TIME ZONE DEFAULT now()",
    },
}


def create_tables():
    Base.metadata.create_all(bind=engine)


def add_missing_columns():
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    with engine.begin() as connection:
        for table_name, required_columns in REQUIRED_COLUMNS.items():
            if table_name not in existing_tables:
                continue

            existing_columns = {
                column["name"]
                for column in inspector.get_columns(table_name)
            }

            for column_name in sorted(required_columns - existing_columns):
                column_definition = COLUMN_DEFINITIONS[table_name][column_name]
                connection.execute(
                    text(
                        f'ALTER TABLE "{table_name}" '
                        f'ADD COLUMN IF NOT EXISTS "{column_name}" '
                        f"{column_definition}"
                    )
                )


def verify_tables():
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    missing_tables = set(REQUIRED_COLUMNS) - existing_tables

    if missing_tables:
        missing = ", ".join(sorted(missing_tables))
        raise RuntimeError(f"Missing required tables: {missing}")

    missing_columns = {}
    for table_name, required_columns in REQUIRED_COLUMNS.items():
        existing_columns = {
            column["name"]
            for column in inspector.get_columns(table_name)
        }
        missing = required_columns - existing_columns
        if missing:
            missing_columns[table_name] = sorted(missing)

    if missing_columns:
        details = "; ".join(
            f"{table}: {', '.join(columns)}"
            for table, columns in missing_columns.items()
        )
        raise RuntimeError(f"Missing required columns: {details}")

    print("Tables created and verified successfully:")
    for table_name in sorted(REQUIRED_COLUMNS):
        print(f"- {table_name}")


if __name__ == "__main__":
    create_tables()
    add_missing_columns()
    verify_tables()
