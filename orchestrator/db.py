# orchestrator/db.py
import os
from datetime import datetime, timezone
from dotenv import load_dotenv
from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text, create_engine
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./satquery.db")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Query(Base):
    __tablename__ = "queries"

    id = Column(Integer, primary_key=True, index=True)
    query_text = Column(Text, nullable=False)
    selected_task = Column(String, nullable=False)
    model_used = Column(String, nullable=False)
    mode = Column(String, nullable=True)
    router_confidence = Column(Float, nullable=True)
    output_confidence = Column(Float, nullable=True)
    validation_msg = Column(String, nullable=True)
    visual_output_path = Column(String, nullable=True)
    visual_output_url = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    images = relationship("UploadedImage", back_populates="query", cascade="all, delete-orphan")
    trace = relationship("ExecutionTrace", back_populates="query", uselist=False, cascade="all, delete-orphan")


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, unique=True, index=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    messages = relationship("ChatMessage", back_populates="conversation", cascade="all, delete-orphan")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False)
    role = Column(String, nullable=False)  # 'user', 'assistant', 'system'
    content = Column(Text, nullable=False)
    query_id = Column(Integer, ForeignKey("queries.id"), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    conversation = relationship("Conversation", back_populates="messages")
    query = relationship("Query")


class UploadedImage(Base):
    __tablename__ = "uploaded_images"

    id = Column(Integer, primary_key=True, index=True)
    query_id = Column(Integer, ForeignKey("queries.id"), nullable=False)
    filepath = Column(String, nullable=False)
    modality = Column(String, nullable=False)
    format = Column(String, nullable=False)
    timestamp_tag = Column(String, nullable=True)

    query = relationship("Query", back_populates="images")


class ExecutionTrace(Base):
    __tablename__ = "execution_traces"

    id = Column(Integer, primary_key=True, index=True)
    query_id = Column(Integer, ForeignKey("queries.id"), nullable=False, unique=True)
    trace_json = Column(Text, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    query = relationship("Query", back_populates="trace")


def init_db():
    Base.metadata.create_all(bind=engine)
    # Ensure backward-compatible schema migration for SQLite
    try:
        with engine.connect() as conn:
            from sqlalchemy import text
            res = conn.execute(text("PRAGMA table_info(queries)"))
            cols = [row[1] for row in res.fetchall()]
            if cols and "visual_output_path" not in cols:
                conn.execute(text("ALTER TABLE queries ADD COLUMN visual_output_path VARCHAR"))
            if cols and "visual_output_url" not in cols:
                conn.execute(text("ALTER TABLE queries ADD COLUMN visual_output_url VARCHAR"))
            conn.commit()
    except Exception as e:
        print(f"[DB] Migration notice: {e}")


# Auto-initialize SQLite database tables on module load
try:
    init_db()
except Exception:
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
