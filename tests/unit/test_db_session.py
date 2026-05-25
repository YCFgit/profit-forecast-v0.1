"""数据库会话管理测试"""

import pytest
from src.db.session import get_engine, get_session


def test_engine_url_is_mysql():
    engine = get_engine()
    assert "mysql" in str(engine.url)


def test_session_can_be_created():
    session = get_session()
    assert session is not None
    session.close()
