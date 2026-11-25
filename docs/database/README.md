# 데이터베이스 (스키마·샘플 데이터)

14주차 최종 산출물. 모두 `python -m scripts.export_database`로 자동 생성한다. 직접 고치지 말고, 모델(`app/models/models.py`)이나 가상 데이터(`app/db/seed_data/`)를 고친 뒤 다시 생성한다.

| 파일 | 내용 | 여는 방법 |
|---|---|---|
| `schema.sql` | 테이블 8개의 `CREATE TABLE` 문 (컬럼·자료형·NOT NULL·기본키·외래키) | 메모장, VS Code |
| `sample_data.sql` | 가상 데이터 `INSERT` 문 382건 | 메모장, VS Code |
| `sample.db` | 스키마 + 가상 데이터가 들어 있는 SQLite 파일 | [DB Browser for SQLite](https://sqlitebrowser.org/) 등 |

- 테이블 설명, ERD, 관계, 샘플 데이터 구성: [`docs/design/erd.md`](../design/erd.md)
- `schema.sql`이 모델과 다르면 `tests/test_database_export.py`가 실패한다.
- 실제 개인정보는 없다. 모두 가상 데이터다.
