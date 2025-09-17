import pytest

from jupythunder2.agent import PlanningAgent


def test_dummy_planning_agent_generates_plan():
    agent = PlanningAgent.from_env(use_dummy=True)
    plan = agent.draft_plan("테스트 목표")

    assert plan.title
    assert len(plan.steps) >= 1
    ids = [step.id for step in plan.steps]
    assert ids == sorted(ids)

    for step in plan.steps:
        assert step.name
        assert step.description


def test_empty_goal_raises_value_error():
    agent = PlanningAgent.from_env(use_dummy=True)
    with pytest.raises(ValueError):
        agent.draft_plan(" ")
