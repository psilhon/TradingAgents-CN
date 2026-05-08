"""get_database() 与 get_mongo_db() 同源路由测试.

Root cause: `app/core/database.py:443` 的 `get_database()` 硬编码
    `return db_manager.mongo_client.tradingagents`
而 `get_mongo_db()` 用 settings.MONGO_DB（解析为 `tradingagentscn`）.

实测后果：6 个 caller (baostock_sync_service / historical_data_service /
news_data_service / social_media_service / internal_message_service /
baostock_init_service) 通过 `get_database()` 连到了**不存在数据**的
`tradingagents` db，而其他用 `get_mongo_db()` 的 service 连对了
`tradingagentscn`，数据被分裂到两个 db。

修复：让 `get_database()` 走 `get_mongo_db()` 同源路径，统一 db 入口。
本测试断言两个函数返回同一个 db 对象，且 db.name 是 settings.MONGO_DB。
"""

from __future__ import annotations

import pytest


@pytest.mark.unit
def test_get_database_returns_same_db_as_get_mongo_db(monkeypatch) -> None:
    """get_database() MUST 返回与 get_mongo_db() 同一个 db 对象（同源路由）."""
    import app.core.database as db_mod

    sentinel = object()
    monkeypatch.setattr(db_mod, "mongo_db", sentinel, raising=False)

    a = db_mod.get_mongo_db()
    b = db_mod.get_database()
    assert a is b is sentinel, f"get_database() / get_mongo_db() 必须返回同一个对象 (get_mongo_db={a!r}, get_database={b!r})"


@pytest.mark.unit
def test_get_database_body_has_no_hardcoded_db_attribute_access() -> None:
    """get_database() 函数体 MUST NOT 含 `mongo_client.<hardcoded_name>` getattr.

    历史 bug：`return db_manager.mongo_client.tradingagents` 用 getattr-style
    访问硬编码 db 名，绕过了 settings.MONGO_DB 配置。用 AST 检查（避免被
    docstring 自伤）.
    """
    import ast
    import inspect

    import app.core.database as db_mod

    src = inspect.getsource(db_mod.get_database)
    tree = ast.parse(src)
    # 从 body 中过滤掉 docstring（首条 Expr-Constant string）
    func_def = tree.body[0]
    assert isinstance(func_def, ast.FunctionDef)
    body = func_def.body
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
        body = body[1:]

    # 在剩余 body 上扫 Attribute 访问，确认没有 mongo_client.<name> 形式（应改用 [settings.MONGO_DB] 下标）
    for node in ast.walk(ast.Module(body=body, type_ignores=[])):
        if isinstance(node, ast.Attribute):
            v = node.value
            if isinstance(v, ast.Attribute) and v.attr == "mongo_client":
                pytest.fail(f"get_database body 含硬编码 attribute 访问 `...mongo_client.{node.attr}` —— 必须改用 settings.MONGO_DB 路径")


@pytest.mark.unit
def test_get_database_raises_when_uninitialized(monkeypatch) -> None:
    """get_database() 在 mongo_db 未初始化时 MUST 抛 RuntimeError."""
    import app.core.database as db_mod

    monkeypatch.setattr(db_mod, "mongo_db", None, raising=False)

    with pytest.raises(RuntimeError):
        db_mod.get_database()
