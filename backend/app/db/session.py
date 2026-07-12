from pathlib import Path

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    pass


def _connect_args() -> dict[str, object]:
    if settings.database_url.startswith("sqlite"):
        return {"check_same_thread": False}
    return {}


def _ensure_sqlite_parent() -> None:
    if not settings.database_url.startswith("sqlite:///"):
        return
    db_path = settings.database_url.removeprefix("sqlite:///")
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)


_ensure_sqlite_parent()
engine = create_engine(settings.database_url, connect_args=_connect_args())
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from app.models import agent  # noqa: F401
    from app.models import agent_audit  # noqa: F401
    from app.models import agent_skill  # noqa: F401
    from app.models import analysis_task  # noqa: F401
    from app.models import data_source  # noqa: F401
    from app.models import knowledge  # noqa: F401
    from app.models import model_config  # noqa: F401
    from app.models import stock_catalog  # noqa: F401
    from app.services.seed import seed_defaults

    Base.metadata.create_all(bind=engine)
    _drop_removed_agent_columns()
    with SessionLocal() as db:
        seed_defaults(db)


def _drop_removed_agent_columns() -> None:
    if engine.dialect.name != "sqlite":
        return
    with engine.begin() as connection:
        for table_name in ("agents", "agent_prompt_versions"):
            columns = {column["name"] for column in inspect(connection).get_columns(table_name)}
            if "output_schema" in columns:
                connection.exec_driver_sql(f"ALTER TABLE {table_name} DROP COLUMN output_schema")
