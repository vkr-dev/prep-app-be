from sqlmodel import Session, SQLModel, create_engine

from app.config import settings

# Neon free Postgres: the one piece of state that must survive redeploys and
# scale-to-zero. Chroma vectors are rebuilt on startup instead - see the RAG
# step in Day 2, no engine needed for that.
engine = create_engine(settings.database_url, echo=False)


def init_db() -> None:
    """Create tables that don't exist yet. Fine for this project's scale;
    reach for Alembic migrations if the schema needs to evolve non-additively."""
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session
