from types import SimpleNamespace

from annotation_trial_errors import trial_integrity_detail


def test_trial_constraints_have_actionable_safe_messages():
    exc = SimpleNamespace(orig=SimpleNamespace(diag=SimpleNamespace(
        constraint_name="uq_annotation_trial_business_identity",
    )))
    detail = trial_integrity_detail(exc)
    assert detail["fieldLabel"] == "轮次"
    assert "已有候选记录" in detail["message"]
    assert "uq_" not in detail["message"]


def test_unknown_constraint_keeps_generic_fallback():
    assert trial_integrity_detail(SimpleNamespace(orig=Exception("private SQL"))) is None
