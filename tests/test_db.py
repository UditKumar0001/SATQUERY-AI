# tests/test_db.py
import json
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from orchestrator.db import Base, Query, UploadedImage, ExecutionTrace


@pytest.fixture
def db_session():
    """Create an isolated in-memory SQLite database session for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()


def test_create_and_query_record(db_session):
    """Test saving a query record and associated trace/images."""
    # 1. Create primary query
    q = Query(
        query_text="Detect buildings in the tile",
        selected_task="vqa_caption_ground",
        model_used="geochat",
        mode="vqa",
        router_confidence=0.92,
        output_confidence=0.88,
        validation_msg="ok"
    )
    db_session.add(q)
    db_session.commit()
    db_session.refresh(q)

    assert q.id is not None
    assert q.selected_task == "vqa_caption_ground"

    # 2. Add an uploaded image linked to the query
    img = UploadedImage(
        query_id=q.id,
        filepath="data/raw/uploads/sample.png",
        modality="optical",
        format="PNG",
        timestamp_tag=None
    )
    db_session.add(img)

    # 3. Add an execution trace linked to the query
    trace_obj = {"selected_task": "vqa_caption_ground", "confidence": 0.88}
    trace = ExecutionTrace(
        query_id=q.id,
        trace_json=json.dumps(trace_obj)
    )
    db_session.add(trace)
    db_session.commit()

    # 4. Verify relations and querying
    fetched = db_session.query(Query).filter(Query.id == q.id).first()
    assert len(fetched.images) == 1
    assert fetched.images[0].filepath == "data/raw/uploads/sample.png"
    assert fetched.trace is not None
    assert json.loads(fetched.trace.trace_json)["confidence"] == 0.88
