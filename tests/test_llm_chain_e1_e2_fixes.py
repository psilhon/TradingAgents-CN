"""E1 + E2 LLM 链路 bug fix 测试.

E1: deepseek embedding 404 — DeepSeek 官方 API 不提供 embedding 端点，
    memory.py 错误地 fallback 到 `OpenAI(base_url='https://api.deepseek.com')`
    + `client.embeddings.create(...)` 必触发 404. 修复：删此 fallback，
    无 DashScope/OpenAI 时直接 DISABLED.

E2: openai reasoning_content must be passed back — DeepSeek thinking 模型
    （deepseek-reasoner）多轮对话需要 client 在每轮回传 reasoning_content；
    langchain ChatOpenAI 当前不支持. 修复：openai_client._DEEPSEEK_EXTRA_BODY
    强制 override `thinking={"type":"disabled"}`，覆盖用户 extra_body 主动
    启用 thinking 的配置（防御性 default）.
"""

from __future__ import annotations

import pytest

# ============== E1 ==============


@pytest.mark.unit
def test_e1_deepseek_memory_disables_when_no_dashscope_no_openai(monkeypatch) -> None:
    """E1: deepseek provider + 无 DASHSCOPE_API_KEY + 无 OPENAI_API_KEY → client = DISABLED.

    历史 bug：还会尝试 `OpenAI(base_url='https://api.deepseek.com')` 然后每次
    embedding 调用都 404. 修复：直接 DISABLED 不试 deepseek 自己的端点.
    """
    import tradingagents.agents.utils.memory as mem_mod
    from tradingagents.agents.utils.memory import FinancialSituationMemory

    # 清掉相关 env keys
    for k in ("DASHSCOPE_API_KEY", "OPENAI_API_KEY", "DEEPSEEK_API_KEY", "FORCE_OPENAI_EMBEDDING"):
        monkeypatch.delenv(k, raising=False)

    # mock chromadb 避免真起 client（init 内部调 ChromaDB）
    class _FakeColl:
        def count(self):
            return 0

    class _FakeChromaClient:
        def get_or_create_collection(self, name):
            return _FakeColl()

    class _FakeChromaSingleton:
        _client = _FakeChromaClient()

    monkeypatch.setattr(mem_mod, "ChromaDBSingleton", _FakeChromaSingleton, raising=False)

    mem = FinancialSituationMemory("test-mem", {"llm_provider": "deepseek"})
    assert mem.client == "DISABLED", f"deepseek 无 embedding key 时应 DISABLED, 实际 {mem.client!r}"


@pytest.mark.unit
def test_e1_deepseek_memory_does_not_create_deepseek_embedding_client(monkeypatch) -> None:
    """E1: 即便有 DEEPSEEK_API_KEY，也不应创建 OpenAI(base_url='https://api.deepseek.com') client.

    确保不再走"DeepSeek使用自己的嵌入服务"那条 dead code 路径.
    """
    import tradingagents.agents.utils.memory as mem_mod
    from tradingagents.agents.utils.memory import FinancialSituationMemory

    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "FAKE_DS_KEY")
    monkeypatch.delenv("FORCE_OPENAI_EMBEDDING", raising=False)

    class _FakeColl:
        def count(self):
            return 0

    class _FakeChromaSingleton:
        class _client:
            @staticmethod
            def get_or_create_collection(name):
                return _FakeColl()

    monkeypatch.setattr(mem_mod, "ChromaDBSingleton", _FakeChromaSingleton, raising=False)

    # 拦截 OpenAI 类，记录是否被错误调用 base_url='https://api.deepseek.com'
    deepseek_base_url_calls: list[str] = []
    real_openai = mem_mod.OpenAI

    def _spy_openai(*args, **kwargs):
        bu = kwargs.get("base_url", "")
        if "deepseek.com" in str(bu):
            deepseek_base_url_calls.append(bu)
        return real_openai(*args, **kwargs)

    monkeypatch.setattr(mem_mod, "OpenAI", _spy_openai, raising=True)

    FinancialSituationMemory("test-mem", {"llm_provider": "deepseek"})

    assert deepseek_base_url_calls == [], (
        f"不应创建 OpenAI(base_url=deepseek.com) embedding client（API 不存在 → 必 404），实际 {deepseek_base_url_calls}"
    )


# ============== E2 ==============


@pytest.mark.unit
def test_e2_deepseek_extra_body_force_overrides_user_thinking() -> None:
    """E2: _DEEPSEEK_EXTRA_BODY_OVERRIDES MUST 强制覆盖用户主动启用 thinking.

    langchain ChatOpenAI 不支持 reasoning_content round-trip → 多轮对话报
    400 'reasoning_content must be passed back'. 防御性 default：强制
    thinking=disabled.
    """
    from tradingagents.llm_clients.openai_client import (
        _DEEPSEEK_EXTRA_BODY_OVERRIDES,
        _merge_deepseek_extra_body,
    )

    # 用户主动启用 thinking
    user_extra = {"thinking": {"type": "enabled"}}
    merged = _merge_deepseek_extra_body(user_extra)

    assert merged.get("thinking") == {"type": "disabled"}, (
        f"deepseek thinking MUST 被强制 disabled (override 用户 enabled), 实际 {merged!r}"
    )
    # 静态 sanity：default 字典本身值正确
    assert _DEEPSEEK_EXTRA_BODY_OVERRIDES["thinking"] == {"type": "disabled"}


@pytest.mark.unit
def test_e2_deepseek_extra_body_preserves_unrelated_user_keys() -> None:
    """E2: 强制 override 只覆盖 thinking，其他 extra_body keys 保留."""
    from tradingagents.llm_clients.openai_client import _merge_deepseek_extra_body

    user_extra = {
        "thinking": {"type": "enabled"},
        "custom_field": "preserved",
        "another": 42,
    }
    merged = _merge_deepseek_extra_body(user_extra)

    assert merged["thinking"] == {"type": "disabled"}, "thinking should be overridden"
    assert merged["custom_field"] == "preserved", "无关字段应保留"
    assert merged["another"] == 42, "无关字段应保留"


@pytest.mark.unit
def test_e2_deepseek_extra_body_handles_none_or_non_mapping() -> None:
    """E2: extra_body 为 None / 非 Mapping 时也正常返回 thinking=disabled."""
    from tradingagents.llm_clients.openai_client import _merge_deepseek_extra_body

    for bad_input in (None, "string", 42, []):
        merged = _merge_deepseek_extra_body(bad_input)
        assert merged.get("thinking") == {"type": "disabled"}, f"input {bad_input!r} 应返回 thinking=disabled, 实际 {merged!r}"
