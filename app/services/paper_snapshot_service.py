"""
PaperSnapshotService — 每个交易日盘后写 paper 账户净值快照到 mongo
`paper_account_snapshots`，为 PaperPerformanceService 提供时间序列基础。

OpenSpec change: paper-account-snapshots
Spec: openspec/specs/paper-account-snapshots/spec.md (after archive)
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.config import settings
from app.core.database import get_mongo_db

logger = logging.getLogger(__name__)


def _compute_snapshot_aggregates(
    positions: list[dict[str, Any]],
    last_prices: dict[str, float | None],
) -> dict[str, Any]:
    """Pure helper: compute snapshot aggregates from positions + per-code last_price.

    capability paper-account-snapshots Requirement "Snapshot 写入闸门 + partial 标志".
    change 2026-05-20-paper-null-quote-handling.

    返回 {
        positions_value: float | None,   # None when partial (任一 position 缺/异常 quote)
        unrealized_pnl: float | None,     # 同上
        partial: bool,
        missing_quote_codes: list[str],   # 缺/异常 quote 的 position code 列表
    }

    缺 quote (last_price=None) 或异常 quote (last <= 0) 都归入 missing_codes，
    切断 v1.3.0 静默剔除 partial coverage → 累加值假装 fully-covered 的污染路径。
    """
    positions_value_acc = 0.0
    unrealized_acc = 0.0
    missing_codes: list[str] = []
    for p in positions:
        code = str(p.get("code", "")).strip()
        qty = int(p.get("quantity", 0) or 0)
        avg_cost = float(p.get("avg_cost", 0.0) or 0.0)
        last = last_prices.get(code)
        if last is None or last <= 0:
            missing_codes.append(code)
            continue
        positions_value_acc += round(last * qty, 2)
        unrealized_acc += round((last - avg_cost) * qty, 2)

    partial = len(missing_codes) > 0
    return {
        # partial=true 时聚合整体 None（不允许部分累加污染 mongo snapshot）
        "positions_value": None if partial else round(positions_value_acc, 2),
        "unrealized_pnl": None if partial else round(unrealized_acc, 2),
        "partial": partial,
        "missing_quote_codes": missing_codes,
    }


class PaperSnapshotService:
    COLLECTION_NAME = "paper_account_snapshots"

    def __init__(self, db: AsyncIOMotorDatabase | None = None) -> None:
        self._db = db
        self._tz = ZoneInfo(settings.TIMEZONE)

    @property
    def db(self) -> AsyncIOMotorDatabase:
        if self._db is None:
            self._db = get_mongo_db()
        return self._db

    async def ensure_index(self) -> None:
        """unique compound (user_id, date) + 普通 user_id index."""
        try:
            await self.db[self.COLLECTION_NAME].create_index([("user_id", 1), ("date", 1)], unique=True)
            await self.db[self.COLLECTION_NAME].create_index("user_id")
        except Exception as e:
            logger.debug(f"ensure_index on paper_account_snapshots: {e}")

    async def take_snapshot(self, user_id: str, snapshot_date: date | None = None) -> dict[str, Any]:
        """计算指定 user 当前账户 equity，upsert 一条 snapshot."""
        if snapshot_date is None:
            snapshot_date = datetime.now(self._tz).date()
        date_str = snapshot_date.isoformat()

        # 拉账户主文档
        acc = await self.db["paper_accounts"].find_one({"user_id": user_id})
        if not acc:
            logger.warning(f"take_snapshot: paper_accounts 未找到 user_id={user_id}")
            return {"ok": False, "reason": "account_not_found"}

        cash_dict = acc.get("cash", {})
        if not isinstance(cash_dict, dict):
            cash_dict = {"CNY": float(cash_dict), "HKD": 0.0, "USD": 0.0}
        cash_cny = float(cash_dict.get("CNY", 0.0))

        realized_pnl_dict = acc.get("realized_pnl", {})
        if not isinstance(realized_pnl_dict, dict):
            realized_pnl_dict = {"CNY": float(realized_pnl_dict), "HKD": 0.0, "USD": 0.0}
        realized_pnl_cny = float(realized_pnl_dict.get("CNY", 0.0))

        # 算 CN 持仓市值 + 浮动盈亏
        positions = await self.db["paper_positions"].find({"user_id": user_id, "market": "CN"}).to_list(None)

        # 延迟 import 避免循环依赖
        from app.routers.paper import _get_last_price

        # 收集 per-code last_price，partial coverage 由 _compute_snapshot_aggregates 处理
        # capability paper-account-snapshots Requirement "Snapshot 写入闸门 + partial 标志"
        last_prices: dict[str, float | None] = {}
        for p in positions:
            code = str(p.get("code", "")).strip()
            last, _, _ = await _get_last_price(code, "CN")
            last_prices[code] = last

        agg = _compute_snapshot_aggregates(positions, last_prices)
        positions_value = agg["positions_value"]
        unrealized_pnl = agg["unrealized_pnl"]
        partial = agg["partial"]
        missing_codes = agg["missing_quote_codes"]

        # equity 在 positions_value=None (partial) 时也 None（公式分量缺失不可信）
        equity = None if positions_value is None else round(cash_cny + positions_value, 2)

        doc: dict[str, Any] = {
            "user_id": user_id,
            "date": date_str,
            "equity": equity,
            "cash": round(cash_cny, 2),
            "positions_value": positions_value,
            "realized_pnl": round(realized_pnl_cny, 2),
            "unrealized_pnl": unrealized_pnl,
            "partial": partial,
            "missing_quote_codes": missing_codes,
            "updated_at": datetime.now(self._tz).replace(tzinfo=None),
        }

        try:
            await self.db[self.COLLECTION_NAME].update_one(
                {"user_id": user_id, "date": date_str},
                {"$set": doc},
                upsert=True,
            )
            log_partial = f" partial(missing={len(missing_codes)})" if partial else ""
            equity_str = "None" if equity is None else f"{equity:.2f}"
            pv_str = "None" if positions_value is None else f"{positions_value:.2f}"
            logger.info(
                f"✅ paper snapshot: user={user_id} date={date_str} equity={equity_str} cash={cash_cny:.2f} positions={pv_str}{log_partial}"
            )
            return {"ok": True, **doc}
        except Exception as e:
            logger.warning(f"take_snapshot upsert 失败: {e}")
            return {"ok": False, "reason": str(e)}

    async def take_snapshots_for_all_users(self) -> dict[str, int]:
        """遍历 paper_accounts 所有 user_id，逐个 take_snapshot."""
        users = await self.db["paper_accounts"].distinct("user_id")
        ok = err = 0
        for user_id in users:
            result = await self.take_snapshot(user_id)
            if result.get("ok"):
                ok += 1
            else:
                err += 1
        logger.info(f"paper snapshots batch: total={len(users)} ok={ok} err={err}")
        return {"total": len(users), "ok": ok, "errors": err}

    async def get_snapshots(self, user_id: str, days: int = 90) -> list[dict[str, Any]]:
        """返回最近 N 个交易日 snapshot（按 date 升序）."""
        cursor = self.db[self.COLLECTION_NAME].find({"user_id": user_id}, {"_id": 0}).sort("date", -1).limit(days)
        docs = await cursor.to_list(None)
        # 升序返回（前端 sparkline / 月度柱图按时间递增）
        docs.sort(key=lambda d: d.get("date", ""))
        return docs


_paper_snapshot_service: PaperSnapshotService | None = None


def get_paper_snapshot_service() -> PaperSnapshotService:
    global _paper_snapshot_service
    if _paper_snapshot_service is None:
        _paper_snapshot_service = PaperSnapshotService()
    return _paper_snapshot_service


__all__: list[Any] = ["PaperSnapshotService", "get_paper_snapshot_service"]
