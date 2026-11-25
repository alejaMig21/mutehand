from workflow_factory import Flow, Node, load_flow, save_flow

FLOW = Flow(id="morning", nodes=[Node("a", "open-menu", inputs=(("text", "str"),)),
                                 Node("choose", kind="if", on="a", equals="revealed", then="b"),
                                 Node("b", "save-file"),
                                 Node("l", "scroll", kind="loop", max_iterations=5, max_seconds=60)],
            edges=[("a", "choose"), ("b", "l")])


def test_a_flow_saved_to_the_user_database_loads_back_unchanged(tmp_path):
    user_db = tmp_path / "user.db"

    save_flow(user_db, FLOW)

    assert load_flow(user_db, None, "morning") == FLOW


def test_the_user_flow_shadows_a_factory_template_of_the_same_id_and_the_factory_file_is_not_written(tmp_path):
    factory_db, user_db = tmp_path / "factory.db", tmp_path / "user.db"
    template = Flow(id="morning", nodes=[Node("t", "template-step")])
    save_flow(factory_db, template)
    before = factory_db.read_bytes()

    from_factory = load_flow(user_db, factory_db, "morning")
    save_flow(user_db, FLOW)
    from_user = load_flow(user_db, factory_db, "morning")

    assert from_factory == template and from_user == FLOW
    assert factory_db.read_bytes() == before


def test_loading_an_unknown_flow_gives_none_even_without_a_factory_file(tmp_path):
    assert load_flow(tmp_path / "user.db", tmp_path / "absent.db", "nope") is None


def test_a_factory_file_that_has_steps_but_no_flows_is_simply_empty_of_flows(tmp_path):
    from workflow_factory import list_flows, save_step

    from fake_desktop import step

    factory_db, user_db = tmp_path / "factory.db", tmp_path / "user.db"
    save_step(factory_db, step("x", "X", origin="factory"))  # a factory file with only steps
    save_flow(user_db, FLOW)

    assert list_flows(user_db, factory_db) == [{"id": "morning", "origin": "local"}]
    assert load_flow(user_db, factory_db, "nope") is None


def test_a_factory_file_that_has_flows_but_no_steps_still_lists_steps(tmp_path):
    from workflow_factory import list_steps

    factory_db = tmp_path / "factory.db"
    save_flow(factory_db, FLOW)

    assert list_steps(tmp_path / "user.db", factory_db) == []
