# known-issues.md

> AI prime context — fork 撞过的坑 + 上游遗留。每次 session 不需要全读，遇到对应症状时查阅。
> 沉淀自 OpenSpec change `claude-md-trim`（从 CLAUDE.md 主文件外置，让 CLAUDE.md 回到 ≤150 行）。

## 🔴 高频严重

### `uv pip install -e .` 会误删 tracked 文件

**症状**：跑 `uv pip install -e .` 后 `git status` 显示 `VERSION` / `requirements.txt` / `requirements-lock.txt` 被删。

**原因**：不明。无 `setup.py` / `MANIFEST.in`，文件也不在 `.gitignore`。疑似 setuptools editable build 或 uv 0.11 editable 实现的副作用。

**workaround**：装完**立即** `git status` 检查；若有删除，立即恢复：

```bash
git checkout HEAD -- VERSION requirements.txt requirements-lock.txt
```

## 🟡 fork 长期警觉

### `app/services/config_service.py` hardcode 端口 fallback

**症状**：backend 启动失败 `Connection refused localhost:27017`。

**原因**：`app/services/config_service.py:491/500` hardcode `port=27017/6379` 作为 fallback 默认值（专有授权代码，不改）。

**fix**：`.env` 必须显式配：
```
MONGODB_PORT=54302
REDIS_PORT=54303
```
否则 backend fallback 连 27017/6379 失败（docker 端口已被 override 改成 54302/54303，无监听）。

### 上游 `scripts/*.py` 多处 hardcode 端口

**症状**：跑 `scripts/<name>.py` 时 `Connection refused localhost:27017`。

**原因**：上游 scripts 多处直接 hardcode `MONGO_URI = "mongodb://...:27017/..."` 不读 `.env`。典型：`scripts/create_default_admin.py`。

**临时 workaround**：跑脚本前 sed patch + 跑完还原：
```bash
sed -i.orig 's/localhost:27017/localhost:54302/g' scripts/<name>.py
.venv/bin/python scripts/<name>.py
mv scripts/<name>.py.orig scripts/<name>.py
```

**长期**：可独立立 OpenSpec change `upstream-scripts-port-config`，把所有 scripts 改成读 `.env`。

## 工具链调用

### `uv sync` 不带 `--frozen` 失败

**症状**：`uv sync` 报 `qianfan>=0.4.20 not available for python_full_version >= '3.13'`。

**原因**：`pyproject.toml` 写 `requires-python = ">=3.10"`，`uv sync` 默认做 universal resolution（包括 3.13），但 `qianfan>=0.4.20` 在 3.13 无 wheel。

**fix**：必须 `uv sync --frozen` 跳过 universal resolution，按 `uv.lock` 装现成的。

### `uv pip install` 不带 `--python` 装到错位置

**症状**：`uv pip install xxx` 报 PEP 668 错误"externally-managed-environment"。

**原因**：uv 默认装到系统 Python（homebrew），但 homebrew Python 受 PEP 668 保护。

**fix**：所有 `uv pip install` 命令必须带 `--python .venv/bin/python` 显式指向 venv：
```bash
uv pip install -e . --python .venv/bin/python
```

## 系统约束

### Docker Desktop 必须手动启动

Claude 无法代替你启动 Docker Desktop GUI 应用。每次重启 mac 后需手动打开 Docker Desktop，等 daemon ready 后才能 `docker compose up`。

验证 ready：`docker info | head -3` 看到 Server Version 即可。
