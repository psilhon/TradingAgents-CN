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
            await self.db[self.COLLECTION_NAME].create_index(
                [("user_id", 1), ("date", 1)], unique=True
            )
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
        positions = await self.db["paper_positions"].find(
            {"user_id": user_id, "market": "CN"}
        ).to_list(None)

        # 延迟 import 避免循环依赖
        from app.routers.paper import _get_last_price

        positions_value = 0.0
        unrealized_pnl = 0.0
        for p in positions:
            code = p.get("code")
            qty = int(p.get("quantity", 0))
            avg_cost = float(p.get("avg_cost", 0.0))
            last = await _get_last_price(code, "CN")
            if last is None or last <= 0:
                continue
            mkt_value = round(last * qty, 2)
            positions_value += mkt_value
            unrealized_pnl += round((last - avg_cost) * qty, 2)

        equity = round(cash_cny + positions_value, 2)

        doc = {
            "user_id": user_id,
            "date": date_str,
            "equity": equity,
            "cash": round(cash_cny, 2),
            "positions_value": round(positions_value, 2),
            "realized_pnl": round(realized_pnl_cny, 2),
            "unrealized_pnl": round(unrealized_pnl, 2),
            "updated_at": datetime.now(self._tz).replace(tzinfo=None),
        }

        try:
            await self.db[self.COLLECTION_NAME].update_one(
                {"user_id": user_id, "date": date_str},
                {"$set": doc},
                upsert=True,
            )
            logger.info(
                f"✅ paper snapshot: user={user_id} date={date_str} "
                f"equity={equity} cash={cash_cny:.2f} positions={positions_value:.2f}"
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

    async def get_snapshots(
        self, user_id: str, days: int = 90
    ) -> list[dict[str, Any]]:
        """返回最近 N 个交易日 snapshot（按 date 升序）."""
        cursor = (
            self.db[self.COLLECTION_NAME]
            .find({"user_id": user_id}, {"_id": 0})
            .sort("date", -1)
            .limit(days)
        )
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
