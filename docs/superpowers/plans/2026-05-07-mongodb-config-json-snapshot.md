# MongoDB Config JSON Snapshot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Make MongoDB the single editable source for LLM configuration while keeping generated JSON snapshots for legacy dependencies.

**Architecture:** Runtime configuration writes go to MongoDB first. After successful MongoDB writes, a small exporter renders `config/models.json` and model-related keys in `config/settings.json` from the active MongoDB document. Legacy readers may consume those files, but user edits and UI writes no longer treat JSON as authoritative.

**Tech Stack:** FastAPI service layer, Motor/PyMongo MongoDB access, existing `SystemConfig`/`LLMConfig` models, JSON compatibility files.

---

### Task 1: Add Snapshot Exporter

**Files:**
- Modify: `app/core/unified_config.py`
- Test: focused Python import/snapshot check

- [x] **Step 1: Add methods that render legacy JSON from a `SystemConfig`**

Add a method that receives the active MongoDB config and writes only generated compatibility fields:

```python
def export_mongodb_snapshot(self, system_config: SystemConfig) -> bool:
    """Export MongoDB configuration to legacy JSON snapshots.

    MongoDB remains authoritative. The generated files are read-only compatibility
    snapshots for legacy TradingAgents dependencies.
    """
```

The method writes:

- `config/models.json`: derived from `system_config.llm_configs`, with empty `api_key`.
- `config/settings.json`: current non-model settings merged with MongoDB `system_settings`, with model fields generated from MongoDB defaults.

- [x] **Step 2: Keep `sync_to_legacy_format()` as a wrapper**

Change `sync_to_legacy_format()` to call `export_mongodb_snapshot()` so existing callers keep working while direction becomes explicit.

- [x] **Step 3: Run import check**

Run:

```bash
.venv/bin/python - <<'PY'
from app.core.unified_config import unified_config
print(type(unified_config).__name__)
PY
```

Expected: prints `UnifiedConfigManager`.

### Task 2: Stop Direct LLM JSON Writes

**Files:**
- Modify: `app/services/config_service.py`

- [x] **Step 1: Remove direct `save_llm_config()` as a gate**

In `update_llm_config()`, do not save JSON before MongoDB. Save MongoDB first through `save_system_config(config)`.

- [x] **Step 2: Generate snapshot after successful MongoDB save**

After `save_system_config(config)` succeeds, call `unified_config.export_mongodb_snapshot(config)`. Snapshot errors should log a warning and not fail the MongoDB write.

- [x] **Step 3: Keep settings sync one-way**

In `update_system_settings()`, keep the post-save sync but route through the new exporter wrapper.

### Task 3: Remove Authored Model JSON Configuration

**Files:**
- Modify: `config/models.json`
- Modify: `config/settings.json`
- Modify: `config/README.md`

- [x] **Step 1: Make `models.json` an empty generated snapshot**

Set it to:

```json
[]
```

- [x] **Step 2: Remove model keys from checked-in `settings.json`**

Remove:

```text
llm_provider
deep_think_llm
quick_think_llm
backend_url
quick_api_key
deep_api_key
quick_provider
deep_provider
quick_backend_url
deep_backend_url
```

Keep non-model runtime settings.

- [x] **Step 3: Update README wording**

Document MongoDB as the authoritative source and JSON files as generated compatibility snapshots.

### Task 4: Verify Behavior

**Files:**
- No production edits expected

- [x] **Step 1: Run focused syntax/import checks**

Run:

```bash
.venv/bin/python -m py_compile app/core/unified_config.py app/services/config_service.py
```

Expected: no output and exit 0.

- [x] **Step 2: Run configuration tests if available**

Run:

```bash
.venv/bin/pytest tests app/scripts -k "config" -q
```

Expected: pass or report unrelated legacy script collection issues clearly.

- [x] **Step 3: Audit remaining JSON dependencies**

Run:

```bash
rg -n "save_llm_config|get_llm_configs|get_quick_analysis_model|get_deep_analysis_model|models\\.json|settings\\.json" app config tradingagents scripts
```

Expected: remaining reads are compatibility reads or migration/debug scripts; no direct UI write treats JSON as authoritative.
