"""reports 资源 owner 隔离（IDOR 修复）源码守护测试。

`app/routers/reports.py` 此前对 `analysis_reports` 无 owner 校验——任一登录用户
可凭 report_id 读 / 下载 / 删除他人报告，`/list` 更直接返回全库。修复：
- 非 admin 的读 / 删全部经 `_scoped_report_query` / `_owner_scope` 叠加 owner 过滤
- admin 看全部
- writer (`simple_analysis_service`) 写报告时反查 task owner 写入 `user_id`
- 回填迁移 `scripts/migrations/2.4_backfill_report_owner.js`（dry-run 默认）

`reports.py` router 导入链会实例化 mongo 连接，无法在 unit test 直接 import，
故用 source-level grep 守护（与项目既有 schema/reliability 守护一致），防回归。
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_REPO = Path(__file__).resolve().parents[1]
_REPORTS_SRC = _REPO / "app" / "routers" / "reports.py"
_WRITER_SRC = _REPO / "app" / "services" / "simple_analysis_service.py"
_MIGRATION = _REPO / "scripts" / "migrations" / "2.4_backfill_report_owner.js"


def _reports_text() -> str:
    return _REPORTS_SRC.read_text()


def test_owner_scope_and_scoped_query_helpers_exist() -> None:
    src = _reports_text()
    assert "def _owner_scope(" in src, "_owner_scope owner 过滤助手缺失"
    assert "def _scoped_report_query(" in src, "_scoped_report_query 助手缺失"


def test_owner_scope_has_admin_bypass() -> None:
    """admin 看全部（owner=None）；非 admin 过滤本人。"""
    src = _reports_text()
    assert 'user.get("is_admin")' in src, "_owner_scope 缺 admin 旁路"
    assert '{"user_id": user["id"]}' in src, "非 admin owner 过滤条件缺失"


def test_no_unscoped_report_query_in_endpoints() -> None:
    """关键守护：裸 _build_report_query(report_id) 只能出现在 _scoped_report_query 内
    （恰好 1 次）。端点直接用裸 query = IDOR 回归。"""
    src = _reports_text()
    n = src.count("_build_report_query(report_id)")
    assert n == 1, f"_build_report_query(report_id) 出现 {n} 次（应仅 _scoped_report_query 内 1 次）—— 疑似端点绕过 owner 过滤"


def test_list_endpoint_applies_owner_filter() -> None:
    src = _reports_text()
    assert 'query["user_id"] = user["id"]' in src, "/list 端点缺 owner 过滤"


def test_detail_fallback_scopes_analysis_tasks() -> None:
    """detail 端点从 analysis_tasks 兜底还原时也须 owner 隔离（task owner 双命名）。"""
    src = _reports_text()
    assert '{"$or": [{"user_id": user["id"]}, {"user": user["id"]}]}' in src, "analysis_tasks 兜底路径缺 owner 隔离"


def test_writer_persists_owner_on_report() -> None:
    """writer 保存报告时反查 task owner 写入 user_id。"""
    src = _WRITER_SRC.read_text()
    assert '"user_id": owner_user_id' in src, "报告文档未写入 owner (user_id)"
    assert "analysis_tasks.find_one(" in src, "writer 未从 task 反查 owner"


def test_backfill_migration_exists_and_dry_run_default() -> None:
    assert _MIGRATION.exists(), "回填迁移脚本缺失"
    js = _MIGRATION.read_text()
    assert 'const DRY_RUN = (typeof DRY_RUN !== "undefined") ? DRY_RUN : true;' in js, "迁移脚本须 dry-run 默认"
    assert "analysis_reports" in js and "analysis_tasks" in js
