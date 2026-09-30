from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from .config import Settings
from .models import Base


def make_session_factory(settings: Settings) -> sessionmaker[Session]:
    url = settings.database_url
    if url.startswith("postgres://"):
        url = "postgresql+psycopg://" + url[len("postgres://"):]
    elif url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    engine = create_engine(url, pool_pre_ping=True)
    if engine.dialect.name == "postgresql":
        with engine.begin() as connection:
            connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(engine)
    if engine.dialect.name == "postgresql":
        # Additive migration for databases created by the first demo version.
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE knowledge_docs ADD COLUMN IF NOT EXISTS embedding_vector vector(768)"))
            connection.execute(text("ALTER TABLE knowledge_docs ADD COLUMN IF NOT EXISTS embedding_fingerprint varchar(64)"))
            connection.execute(text("ALTER TABLE semantic_entries ADD COLUMN IF NOT EXISTS embedding_vector vector(768)"))
            connection.execute(text("ALTER TABLE request_traces ADD COLUMN IF NOT EXISTS operator_id varchar(40) REFERENCES operators(id)"))
            connection.execute(text("ALTER TABLE request_traces ADD COLUMN IF NOT EXISTS conversation_id varchar(40) REFERENCES conversations(id)"))
            connection.execute(text("CREATE INDEX IF NOT EXISTS ix_knowledge_docs_vector ON knowledge_docs USING hnsw (embedding_vector vector_cosine_ops)"))
            connection.execute(text("CREATE INDEX IF NOT EXISTS ix_semantic_entries_vector ON semantic_entries USING hnsw (embedding_vector vector_cosine_ops)"))
            connection.execute(text("CREATE INDEX IF NOT EXISTS ix_request_traces_operator_id ON request_traces (operator_id)"))
            connection.execute(text("CREATE INDEX IF NOT EXISTS ix_request_traces_conversation_id ON request_traces (conversation_id)"))
    return sessionmaker(bind=engine, expire_on_commit=False)
