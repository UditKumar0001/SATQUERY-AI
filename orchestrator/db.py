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
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    images = relationship("UploadedImage", back_populates="query", cascade="all, delete-orphan")
    trace = relationship("ExecutionTrace", back_populates="query", uselist=False, cascade="all, delete-orphan")


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


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
