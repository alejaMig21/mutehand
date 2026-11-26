import pytest

from workflow_factory.schedule import delete_schedule


def test_a_default_test_cannot_change_a_real_scheduled_task():
    with pytest.raises(AssertionError, match="FakeScheduler"):
        delete_schedule("guard-probe-that-does-not-exist")
