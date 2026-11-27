"""The persona harness stays up while its data folder exists, whichever dataset it serves (the first day creates no database)."""

import shutil

import pytest
from acceptance_server import DATASETS, data_folder_present, desktop_for
from fake_scheduler import FakeScheduler

from workflow_factory import list_flows, load_flow
from workflow_factory.api import ApiServer
from workflow_factory.steps import all_tags, list_steps


@pytest.mark.parametrize("dataset", sorted(DATASETS))
def test_the_harness_is_up_while_its_folder_exists_and_stops_when_it_is_deleted(tmp_path, dataset):
    state = tmp_path / "state"
    state.mkdir()
    server = ApiServer(state / "user.db", state / "factory.db", desktop_for, token="t", schedule_runner=FakeScheduler())
    DATASETS[dataset](state / "user.db", server)

    assert data_folder_present(state)
    shutil.rmtree(state)
    assert not data_folder_present(state)


def served_data(tmp_path, dataset):
    state = tmp_path / "state"
    state.mkdir()
    server = ApiServer(state / "user.db", state / "factory.db", desktop_for, token="t", schedule_runner=FakeScheduler())
    DATASETS[dataset](state / "user.db", server)
    return state / "user.db"


@pytest.mark.parametrize("dataset", ["everyday", "many-apps"])
def test_the_persona_data_is_built_with_generic_steps_tags_and_nodes_that_name_their_technology(tmp_path, dataset):
    db = served_data(tmp_path, dataset)
    steps = list_steps(db, None)
    technologies = {s.app for s in steps}

    by_name = {}
    for s in steps:
        by_name.setdefault(s.name, set()).add(s.app)
    assert any(len(apps) >= 2 for apps in by_name.values())  # one "Save" learned on two programs
    assert all_tags(db)  # pattern tags
    for name in by_name:  # named by what it does: no program in the name
        assert not [t for t in technologies if t.split(".")[0] in name.casefold()]

    flows = [load_flow(db, None, f["id"]) for f in list_flows(db, None)]
    assert flows
    for flow in flows:
        for node in (n for n in flow.nodes if n.kind == "step"):  # a daily time adds a trigger node
            assert node.technology in technologies and node.step in by_name and node.technology in by_name[node.step]
    assert any(len({n.technology for n in flow.nodes if n.kind == "step"}) >= 2 for flow in flows)  # a flow that mixes two programs
