import os
import sys
import uuid
from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.orm import Session

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from main import app
from app.config import settings
from app.db.session import engine, get_db
from app.models.document import Document, DocumentStatus
from app.models.processing_job import ProcessingJob, JobStatus
from app.models.processing_result import ProcessingResult
from app.models.validation_result import ValidationResult, ValidationStatus

client = TestClient(app)



@pytest.fixture
def isolated_db_session():
    """Provides a database session isolated in a rolled-back transaction with clean tables."""
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")

    # Clear existing documents inside the isolated transaction
    session.query(Document).delete()
    session.commit()

    # Override get_db dependency to point to this session
    def override_get_db():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    yield session

    # Cleanup and rollback all transaction changes
    app.dependency_overrides.pop(get_db, None)
    session.close()
    transaction.rollback()
    connection.close()


def test_empty_document_list(isolated_db_session):
    """Assert GET /documents returns empty list and total 0 when no documents exist."""
    response = client.get("/documents")
    assert response.status_code == 200
    data = response.json()

    assert data["items"] == []
    assert data["total"] == 0
    assert data["limit"] == 20
    assert data["offset"] == 0


def test_multiple_documents_ordered_newest_first(isolated_db_session):
    """Assert documents are returned in created_at DESC order (newest first)."""
    now = datetime.now(timezone.utc)
    t_old = now - timedelta(hours=2)
    t_mid = now - timedelta(hours=1)
    t_new = now

    doc_old = Document(
        id=uuid.uuid4(),
        original_filename="oldest.pdf",
        content_type="application/pdf",
        file_size=100,
        storage_path="path/oldest.pdf",
        status=DocumentStatus.UPLOADED,
        created_at=t_old,
    )
    doc_mid = Document(
        id=uuid.uuid4(),
        original_filename="middle.pdf",
        content_type="application/pdf",
        file_size=200,
        storage_path="path/middle.pdf",
        status=DocumentStatus.UPLOADED,
        created_at=t_mid,
    )
    doc_new = Document(
        id=uuid.uuid4(),
        original_filename="newest.pdf",
        content_type="application/pdf",
        file_size=300,
        storage_path="path/newest.pdf",
        status=DocumentStatus.UPLOADED,
        created_at=t_new,
    )

    isolated_db_session.add_all([doc_mid, doc_old, doc_new])
    isolated_db_session.commit()

    response = client.get("/documents")
    assert response.status_code == 200
    data = response.json()

    assert data["total"] == 3
    assert len(data["items"]) == 3
    returned_ids = [item["id"] for item in data["items"]]
    assert returned_ids == [str(doc_new.id), str(doc_mid.id), str(doc_old.id)]
    assert data["items"][0]["original_filename"] == "newest.pdf"
    assert data["items"][1]["original_filename"] == "middle.pdf"
    assert data["items"][2]["original_filename"] == "oldest.pdf"


def test_pagination_and_total_count(isolated_db_session):
    """Assert limit and offset paginate documents correctly and total reflects overall count."""
    now = datetime.now(timezone.utc)
    docs = []
    for i in range(5):
        doc = Document(
            id=uuid.uuid4(),
            original_filename=f"doc_{i}.pdf",
            content_type="application/pdf",
            file_size=1000 + i,
            storage_path=f"path/doc_{i}.pdf",
            status=DocumentStatus.UPLOADED,
            created_at=now + timedelta(minutes=i),
        )
        docs.append(doc)

    isolated_db_session.add_all(docs)
    isolated_db_session.commit()

    # Total is 5. Documents ordered newest first: doc_4, doc_3, doc_2, doc_1, doc_0

    # Page 1: limit 2, offset 0 -> doc_4, doc_3
    res1 = client.get("/documents?limit=2&offset=0")
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["total"] == 5
    assert data1["limit"] == 2
    assert data1["offset"] == 0
    assert len(data1["items"]) == 2
    assert [d["id"] for d in data1["items"]] == [str(docs[4].id), str(docs[3].id)]

    # Page 2: limit 2, offset 2 -> doc_2, doc_1
    res2 = client.get("/documents?limit=2&offset=2")
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["total"] == 5
    assert data2["limit"] == 2
    assert data2["offset"] == 2
    assert len(data2["items"]) == 2
    assert [d["id"] for d in data2["items"]] == [str(docs[2].id), str(docs[1].id)]

    # Page 3: limit 2, offset 4 -> doc_0
    res3 = client.get("/documents?limit=2&offset=4")
    assert res3.status_code == 200
    data3 = res3.json()
    assert data3["total"] == 5
    assert data3["limit"] == 2
    assert data3["offset"] == 4
    assert len(data3["items"]) == 1
    assert [d["id"] for d in data3["items"]] == [str(docs[0].id)]

    # Beyond total: limit 2, offset 6 -> empty items, total is still 5
    res4 = client.get("/documents?limit=2&offset=6")
    assert res4.status_code == 200
    data4 = res4.json()
    assert data4["total"] == 5
    assert data4["limit"] == 2
    assert data4["offset"] == 6
    assert data4["items"] == []


def test_correct_nested_response_structure(isolated_db_session):
    """Assert response includes full nested processing job, result, and validation result."""
    doc_id = uuid.uuid4()
    job_id = uuid.uuid4()
    res_id = uuid.uuid4()
    val_id = uuid.uuid4()

    doc = Document(
        id=doc_id,
        original_filename="transcript_nested.pdf",
        content_type="application/pdf",
        file_size=54321,
        storage_path="path/nested.pdf",
        status=DocumentStatus.COMPLETED,
    )
    job = ProcessingJob(
        id=job_id,
        document_id=doc_id,
        status=JobStatus.COMPLETED,
        attempts=1,
    )
    proc_res = ProcessingResult(
        id=res_id,
        document_id=doc_id,
        document_type="MARKSHEET",
        detection_score=88,
        matched_signals=["cgpa", "transcript", "grades"],
        extracted_text="CGPA: 8.5",
        extracted_data={"gpa": "8.5", "institution": "State University"},
    )
    val_res = ValidationResult(
        id=val_id,
        processing_result_id=res_id,
        overall_status=ValidationStatus.PASS,
        policy_id="sample-scholarship",
        policy_version="1.0",
        checks=[
            {
                "rule_id": "MIN_CGPA",
                "status": "PASS",
                "expected": ">= 7.0",
                "actual": "8.5",
                "reason": "CGPA 8.5 meets requirement.",
            }
        ],
    )

    isolated_db_session.add(doc)
    isolated_db_session.add(job)
    isolated_db_session.add(proc_res)
    isolated_db_session.add(val_res)
    isolated_db_session.commit()

    response = client.get("/documents")
    assert response.status_code == 200
    data = response.json()

    assert data["total"] == 1
    assert len(data["items"]) == 1
    item = data["items"][0]

    # Document fields
    assert item["id"] == str(doc_id)
    assert item["original_filename"] == "transcript_nested.pdf"
    assert item["content_type"] == "application/pdf"
    assert item["file_size"] == 54321
    assert item["status"] == "COMPLETED"
    assert "created_at" in item

    # ProcessingJob fields
    assert item["processing_job"] is not None
    assert item["processing_job"]["id"] == str(job_id)
    assert item["processing_job"]["status"] == "COMPLETED"
    assert item["processing_job"]["attempts"] == 1

    # ProcessingResult fields
    assert item["processing_result"] is not None
    assert item["processing_result"]["id"] == str(res_id)
    assert item["processing_result"]["document_type"] == "MARKSHEET"
    assert item["processing_result"]["detection_score"] == 88
    assert item["processing_result"]["matched_signals"] == ["cgpa", "transcript", "grades"]
    assert item["processing_result"]["extracted_text"] == "CGPA: 8.5"
    assert item["processing_result"]["extracted_data"] == {"gpa": "8.5", "institution": "State University"}

    # ValidationResult fields
    val = item["processing_result"]["validation_result"]
    assert val is not None
    assert val["id"] == str(val_id)
    assert val["overall_status"] == "PASS"
    assert val["policy_id"] == "sample-scholarship"
    assert val["policy_version"] == "1.0"
    assert len(val["checks"]) == 1
    assert val["checks"][0]["rule_id"] == "MIN_CGPA"
    assert val["checks"][0]["status"] == "PASS"
    assert val["checks"][0]["actual"] == "8.5"


def test_invalid_pagination_parameters():
    """Assert invalid limit and offset values return 422 Unprocessable Entity."""
    # limit < 1
    res = client.get("/documents?limit=0")
    assert res.status_code == 422

    res = client.get("/documents?limit=-5")
    assert res.status_code == 422

    # limit > 100
    res = client.get("/documents?limit=101")
    assert res.status_code == 422

    # non-integer limit
    res = client.get("/documents?limit=abc")
    assert res.status_code == 422

    # offset < 0
    res = client.get("/documents?offset=-1")
    assert res.status_code == 422

    # non-integer offset
    res = client.get("/documents?offset=xyz")
    assert res.status_code == 422


def test_valid_boundary_pagination_parameters(isolated_db_session):
    """Assert valid boundary limit values (1 and 100) and offset 0 work as expected."""
    res_min = client.get("/documents?limit=1&offset=0")
    assert res_min.status_code == 200
    assert res_min.json()["limit"] == 1
    assert res_min.json()["offset"] == 0

    res_max = client.get("/documents?limit=100&offset=0")
    assert res_max.status_code == 200
    assert res_max.json()["limit"] == 100
    assert res_max.json()["offset"] == 0


def test_e2e_listing_with_real_upload(isolated_db_session, monkeypatch, tmp_path):
    """Assert real uploaded document appears at the top of the GET /documents list,
    while keeping database and filesystem completely isolated and clean.
    """
    # Isolate uploads directory to a temporary folder
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))

    pdf_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "samples", "marksheet", "sample_transcript.pdf")
    )
    assert os.path.exists(pdf_path)

    with open(pdf_path, "rb") as f:
        response = client.post(
            "/documents",
            files={"file": ("listing_e2e_test.pdf", f, "application/pdf")},
        )
    assert response.status_code == 201
    created_id = response.json()["id"]

    # Verify file was written to temporary directory and NOT to normal upload dir
    temp_doc_dir = tmp_path / created_id
    assert temp_doc_dir.exists()
    assert (temp_doc_dir / "original.pdf").exists()

    list_res = client.get("/documents?limit=10&offset=0")
    assert list_res.status_code == 200
    list_data = list_res.json()
    assert list_data["total"] == 1
    # The newly uploaded doc should be the newest, i.e., items[0]
    assert list_data["items"][0]["id"] == created_id
    assert list_data["items"][0]["original_filename"] == "listing_e2e_test.pdf"


def test_query_count_stays_bounded(isolated_db_session):
    """Regression test: verify query count stays bounded as document count increases (no N+1 queries)."""
    now = datetime.now(timezone.utc)
    # Seed 10 documents with full nested processing_job, processing_result, and validation_result
    for i in range(10):
        doc_id = uuid.uuid4()
        res_id = uuid.uuid4()
        doc = Document(
            id=doc_id,
            original_filename=f"query_test_{i}.pdf",
            content_type="application/pdf",
            file_size=1000 + i,
            storage_path=f"path/query_test_{i}.pdf",
            status=DocumentStatus.COMPLETED,
            created_at=now + timedelta(minutes=i),
        )
        job = ProcessingJob(
            id=uuid.uuid4(),
            document_id=doc_id,
            status=JobStatus.COMPLETED,
            attempts=1,
        )
        proc_res = ProcessingResult(
            id=res_id,
            document_id=doc_id,
            document_type="MARKSHEET",
            detection_score=90,
            matched_signals=["cgpa"],
            extracted_text="CGPA: 8.0",
            extracted_data={"gpa": "8.0"},
        )
        val_res = ValidationResult(
            id=uuid.uuid4(),
            processing_result_id=res_id,
            overall_status=ValidationStatus.PASS,
            policy_id="sample-scholarship",
            policy_version="1.0",
            checks=[
                {
                    "rule_id": "MIN_CGPA",
                    "status": "PASS",
                    "expected": ">= 7.0",
                    "actual": "8.0",
                    "reason": "Meets criteria",
                }
            ],
        )
        isolated_db_session.add_all([doc, job, proc_res, val_res])
    isolated_db_session.commit()

    # Track SELECT queries executed on the database engine
    queries = []

    def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        if statement.strip().upper().startswith("SELECT"):
            queries.append(statement)

    event.listen(engine, "before_cursor_execute", before_cursor_execute)
    try:
        # Fetch 1 document
        res_1 = client.get("/documents?limit=1&offset=0")
        assert res_1.status_code == 200
        assert len(res_1.json()["items"]) == 1
        count_for_1 = len(queries)

        # Reset query tracker
        queries.clear()

        # Fetch 10 documents
        res_10 = client.get("/documents?limit=10&offset=0")
        assert res_10.status_code == 200
        assert len(res_10.json()["items"]) == 10
        count_for_10 = len(queries)

        # Both fetches execute the exact same bounded number of queries (2 SELECT queries: 1 count + 1 joined fetch)
        # Without eager loading, 10 docs would execute 32 queries (1 count + 1 fetch + 10 * 3 lazy loads).
        assert count_for_1 <= 3
        assert count_for_10 <= 3
        assert count_for_10 == count_for_1
    finally:
        event.remove(engine, "before_cursor_execute", before_cursor_execute)


