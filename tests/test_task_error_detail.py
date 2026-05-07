from app.services.simple_analysis_service import _build_task_error_detail


def test_task_error_detail_keeps_technical_error_and_redacts_keys():
    error = RuntimeError("Error code: 400 - api_key=sk-proj-abcdefghijklmnopqrstuvwxyz123456")

    detail = _build_task_error_detail(error, "分析失败\n\n模型请求失败")

    assert detail["category"] == "llm_bad_request"
    assert "Error code: 400" in detail["technical_detail"]
    assert "sk-proj-abcdefghijklmnopqrstuvwxyz123456" not in detail["technical_detail"]
    assert detail["suggestions"]
