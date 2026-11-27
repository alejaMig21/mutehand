"""The persona harness stays up while its data folder exists, whichever dataset it serves (the first day creates no database)."""

import shutil

import pytest
from acceptance_server import DATASETS, data_folder_present, desktop_for
from fake_scheduler import FakeScheduler

from workflow_factory.api import ApiServer


@pytest.mark.parametrize("dataset", sorted(DATASETS))
def test_the_harness_is_up_while_its_folder_exists_and_stops_when_it_is_deleted(tmp_path, dataset):
    state = tmp_path / "state"
    state.mkdir()
    server = ApiServer(state / "user.db", state / "factory.db", desktop_for, token="t", schedule_runner=FakeScheduler())
    DATASETS[dataset](state / "user.db", server)

    assert data_folder_present(state)
    shutil.rmtree(state)
    assert not data_folder_present(state)
