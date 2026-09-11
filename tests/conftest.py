import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from home_budget.app.database import get_connection, init_db


@pytest.fixture
def conn(tmp_path):
    db_path = tmp_path / "test.db"
    connection = get_connection(db_path)
    init_db(connection)
    yield connection
    connection.close()
