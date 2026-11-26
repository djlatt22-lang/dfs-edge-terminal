import pytest
from pydantic import ValidationError
from app.projection_v2 import ProjectionRequest, project


def test_unverified_manual_simulation_is_never_graded_a():
    q = ProjectionRequest(
        sport="CBB", player="Sample Player", market="points",
        line=10.5, base=25.0, sims=1000,
    )
    result = project(q)
    assert result["probability"] > 80
    assert result["grade"] == "RESEARCH"
    assert result["confidence"] is None
    assert result["calibration_status"] == "NOT_VALIDATED"
    assert result["sample_size"] == 0
    assert result["heuristic_grade"] in {"A+", "A", "B+", "B", "C"}
    assert result["heuristic_confidence"] is not None


def test_simulation_reproducible_at_same_inputs():
    q = ProjectionRequest(sport="NFL", player="Sample Player",
                          market="passing_yards", line=240.5,
                          history=[210, 280, 265, 230], sims=1000)
    assert project(q) == project(q)


@pytest.mark.parametrize("extra", [
    {"line": float("nan")},
    {"line": float("inf")},
    {"base": float("-inf")},
    {"player": ""},
    {"market": ""},
])
def test_invalid_inputs_rejected(extra):
    row = dict(sport="NBA", player="Sample", market="points",
               line=10.5, base=12)
    row.update(extra)
    with pytest.raises(ValidationError):
        ProjectionRequest(**row)


def test_no_base_or_history_is_rejected():
    with pytest.raises(ValueError):
        project(ProjectionRequest(sport="CBB", player="Sample",
                                  market="points", line=10.5))
