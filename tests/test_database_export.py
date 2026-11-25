# AI-assisted (Claude)
"""제출용 DB 산출물(docs/database)이 지금 모델·가상 데이터와 맞는지 확인한다 (14주차)."""

import sqlite3

from scripts import export_database
from scripts.export_database import OUT_DIR, build_sample_db, sample_data_sql, schema_sql


def test_schema_sql_matches_models():
    """모델을 고치고 schema.sql을 다시 만들지 않으면 실패한다."""
    assert (OUT_DIR / "schema.sql").read_text(encoding="utf-8") == schema_sql()


def test_sample_db_has_all_seed_data(tmp_path):
    db = tmp_path / "sample.db"
    build_sample_db(db)
    with sqlite3.connect(db) as conn:
        counts = {
            t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            for t in ("stores", "menu_items", "faqs", "inquiries", "reservations")
        }
        no_history = conn.execute(
            "SELECT COUNT(*) FROM reservations r WHERE NOT EXISTS "
            "(SELECT 1 FROM reservation_histories h WHERE h.reservation_id = r.id)"
        ).fetchone()[0]
    assert counts == {
        "stores": 1,
        "menu_items": 12,
        "faqs": 20,
        "inquiries": 30,
        "reservations": 75,
    }
    assert no_history == 0  # 가상 예약도 모두 상태 이력이 있다
    assert "INSERT INTO" in sample_data_sql(db)


def test_export_writes_three_files(tmp_path, monkeypatch):
    monkeypatch.setattr(export_database, "OUT_DIR", tmp_path)
    export_database.main()
    assert {p.name for p in tmp_path.iterdir()} == {"schema.sql", "sample_data.sql", "sample.db"}
