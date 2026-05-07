import asyncio

from app.routers import paper


class _FakeInsertResult:
    inserted_id = "inserted"


class _FakeUpdateResult:
    modified_count = 1
    upserted_id = None


class _FakeDeleteResult:
    def __init__(self, deleted_count: int):
        self.deleted_count = deleted_count


class _FakeCollection:
    def __init__(self, docs=None):
        self.docs = list(docs or [])
        self.deleted_filters = []
        self.updated = []

    async def find_one(self, query, *args, **kwargs):
        for doc in self.docs:
            if all(doc.get(k) == v for k, v in query.items()):
                return dict(doc)
        return None

    async def insert_one(self, doc):
        stored = dict(doc)
        stored.setdefault("_id", f"id-{len(self.docs) + 1}")
        self.docs.append(stored)
        return _FakeInsertResult()

    async def update_one(self, query, update, upsert=False):
        self.updated.append((query, update, upsert))
        target = None
        for doc in self.docs:
            if all(doc.get(k) == v for k, v in query.items()):
                target = doc
                break

        if target is None and upsert:
            target = dict(query)
            self.docs.append(target)

        if target is not None:
            for key, value in update.get("$set", {}).items():
                parts = key.split(".")
                cursor = target
                for part in parts[:-1]:
                    cursor = cursor.setdefault(part, {})
                cursor[parts[-1]] = value

        return _FakeUpdateResult()

    async def delete_many(self, query):
        before = len(self.docs)
        self.docs = [doc for doc in self.docs if not all(doc.get(k) == v for k, v in query.items())]
        deleted = before - len(self.docs)
        self.deleted_filters.append(query)
        return _FakeDeleteResult(deleted)


class _FakeDB(dict):
    def __getitem__(self, name):
        if name not in self:
            self[name] = _FakeCollection()
        return super().__getitem__(name)


def test_import_account_replaces_positions_and_sets_cash(monkeypatch):
    db = _FakeDB(
        {
            "paper_accounts": _FakeCollection(
                [
                    {
                        "user_id": "u1",
                        "cash": {"CNY": 1000.0, "HKD": 0.0, "USD": 0.0},
                        "realized_pnl": {"CNY": 0.0, "HKD": 0.0, "USD": 0.0},
                    }
                ]
            ),
            "paper_positions": _FakeCollection(
                [
                    {
                        "user_id": "u1",
                        "code": "000001",
                        "market": "CN",
                        "quantity": 100,
                    }
                ]
            ),
            "paper_orders": _FakeCollection([{"user_id": "u1", "code": "000001"}]),
            "paper_trades": _FakeCollection([{"user_id": "u1", "code": "000001"}]),
        }
    )
    monkeypatch.setattr(paper, "get_mongo_db", lambda: db)

    payload = paper.ImportAccountRequest(
        mode="replace",
        cash={"CNY": 50000.0, "HKD": 3000.0},
        positions=[
            paper.ImportPositionItem(
                code="002428",
                market="CN",
                name="云南锗业",
                quantity=200,
                avg_cost=12.34,
            )
        ],
    )

    result = asyncio.run(paper.import_account(payload, {"id": "u1"}))

    assert result["success"] is True
    assert result["data"]["imported_positions"] == 1
    assert result["data"]["mode"] == "replace"
    assert db["paper_accounts"].docs[0]["cash"]["CNY"] == 50000.0
    assert db["paper_accounts"].docs[0]["cash"]["HKD"] == 3000.0
    assert db["paper_positions"].docs == [
        {
            "user_id": "u1",
            "code": "002428",
            "market": "CN",
            "currency": "CNY",
            "name": "云南锗业",
            "quantity": 200,
            "available_qty": 200,
            "frozen_qty": 0,
            "avg_cost": 12.34,
            "source": "manual_import",
            "imported_at": db["paper_positions"].docs[0]["imported_at"],
            "updated_at": db["paper_positions"].docs[0]["updated_at"],
        }
    ]
    assert db["paper_orders"].docs == []
    assert db["paper_trades"].docs == []
