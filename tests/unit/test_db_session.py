"""数据库会话管理测试"""

import pytest

# 检查 pymysql 是否可用
try:
    import pymysql
    HAS_PYMYSQL = True
except ImportError:
    HAS_PYMYSQL = False


@pytest.mark.skipif(not HAS_PYMYSQL, reason="pymysql not installed")
def test_engine_url_is_mysql():
    from src.db.session import get_engine
    engine = get_engine()
    assert "mysql" in str(engine.url)


@pytest.mark.skipif(not HAS_PYMYSQL, reason="pymysql not installed")
def test_session_can_be_created():
    from src.db.session import get_session
    session = get_session()
    assert session is not None
    session.close()


def test_sqlite_session_works():
    """测试 SQLite 会话可以正常工作"""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine("sqlite:///:memory:")
    Session = sessionmaker(bind=engine)
    session = Session()
    assert session is not None
    session.close()
