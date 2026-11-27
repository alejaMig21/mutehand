"""A recipe is an ordered pattern of holes. Taught on one app, it is applied to another by teaching only the controls that
differ; every hole is measured on the new app and a failing hole leaves a doubt that names it."""

import pytest

from workflow_factory import find_step, list_doubts, save_step
from workflow_factory.recipes import apply_recipe, list_recipes, mark_step_known, recipe_bindings, save_recipe
from workflow_factory.steps import Locator

from fake_desktop import FakeDesktop, button, step

HOLES = [
    {"hole": "open-chat", "role": "button", "control_name": "Open chat"},
    {"hole": "compose", "role": "button", "control_name": "Message field"},
    {"hole": "send", "role": "button", "control_name": "Send message", "sensitive": "outward_action"},
]


def telegram():
    return FakeDesktop(controls=[button("Open chat"), button("Message field"), button("Send message")], app="telegram.exe")


def whatsapp(**names):
    """WhatsApp calls the compose node and the send button differently; the first control is called the same."""
    return FakeDesktop(controls=[button("Open chat"), button(names.get("compose", "Type a message")),
                                 button(names.get("send", "Send"))], app="whatsapp.exe")


@pytest.fixture
def db(tmp_path):
    user_db = tmp_path / "user.db"
    save_recipe(user_db, "send-message", HOLES)
    return user_db


def teach_telegram(db):
    from workflow_factory import grant_consent
    grant_consent(db, "telegram.exe", "Send message", "click")
    return apply_recipe(db, telegram(), "send-message")


def test_a_recipe_taught_on_a_first_app_saves_one_step_per_hole_in_order(db):
    result = teach_telegram(db)

    assert result["status"] == "applied" and [h["hole"] for h in result["holes"]] == ["open-chat", "compose", "send"]
    assert [recipe_bindings(db, "send-message", "telegram.exe")[h] for h in ("open-chat", "compose", "send")] == [
        "send-message-open-chat", "send-message-compose", "send-message-send"]
    assert find_step(db, None, "telegram.exe", "send-message-send").locator == Locator("button", "Send message", None)


def test_the_recipe_is_applied_to_a_second_app_by_teaching_only_the_controls_that_differ(db):
    from workflow_factory import grant_consent
    teach_telegram(db)
    grant_consent(db, "whatsapp.exe", "Send", "click")
    desktop = whatsapp()

    result = apply_recipe(db, desktop, "send-message", {
        "compose": {"role": "button", "control_name": "Type a message"},
        "send": {"role": "button", "control_name": "Send"},
    })

    assert result["status"] == "applied" and list_doubts(db) == []
    assert [c.name for c in desktop.clicks] == ["Open chat", "Type a message", "Send"]  # open-chat reused Telegram's control
    assert find_step(db, None, "whatsapp.exe", "send-message-open-chat").locator.name == "Open chat"
    assert find_step(db, None, "whatsapp.exe", "send-message-send").locator.name == "Send"


def test_a_hole_that_fails_on_the_new_app_leaves_a_doubt_that_names_it_and_stops_there(db):
    teach_telegram(db)
    desktop = whatsapp()  # nobody told the recipe where the compose node is: the default control does not exist here

    result = apply_recipe(db, desktop, "send-message")

    assert result["status"] == "stopped" and result["holes"][1] == {"hole": "compose", "status": "control_not_found",
                                                                     "step": "send-message-compose"}
    assert [h["status"] for h in result["holes"]] == ["saved", "control_not_found", "not_tried"]
    (doubt,) = list_doubts(db)
    assert doubt.node_id == "compose" and doubt.step == "send-message-compose" and doubt.flow_id == "recipe:send-message"
    assert doubt.detail == "control_not_found"
    assert [c.name for c in desktop.clicks] == ["Open chat"]  # nothing after the failed hole was touched


def test_the_doubt_of_a_hole_is_answered_by_teaching_that_step_and_the_recipe_resumes_without_repeating_clicks(db):
    from workflow_factory import grant_consent
    from workflow_factory.tutor import answer_doubt_by_teaching
    teach_telegram(db)
    desktop = whatsapp()
    apply_recipe(db, desktop, "send-message")
    (doubt,) = list_doubts(db)
    answer_doubt_by_teaching(db, desktop, doubt.id, "send-message-compose", Locator("button", "Type a message", None))
    grant_consent(db, "whatsapp.exe", "Send", "click")
    desktop.clicks.clear()

    result = apply_recipe(db, desktop, "send-message", {"send": {"role": "button", "control_name": "Send"}})

    assert result["status"] == "applied"
    assert [h["status"] for h in result["holes"]] == ["already_known", "already_known", "saved"]
    assert [c.name for c in desktop.clicks] == ["Send"]


def test_a_sensitive_hole_without_consent_asks_for_it_instead_of_acting(db):
    desktop = telegram()

    result = apply_recipe(db, desktop, "send-message")

    assert result["status"] == "consent_required" and result["hole"] == "send"
    assert result["scope"] == {"app": "telegram.exe", "control": "Send message", "action": "click"}
    assert list_doubts(db) == []


def test_a_hole_can_be_bound_to_a_step_the_app_already_has(db):
    save_step(db, step("existing-compose", "Type a message", app="whatsapp.exe"))

    mark_step_known(db, "whatsapp.exe", "send-message", "compose", "existing-compose")

    assert recipe_bindings(db, "send-message", "whatsapp.exe") == {"compose": "existing-compose"}
    result = apply_recipe(db, whatsapp(), "send-message", {"compose": {"known_step": "existing-compose"}})
    assert result["holes"][1] == {"hole": "compose", "status": "already_known", "step": "existing-compose"}


def test_binding_a_hole_to_a_step_that_does_not_exist_is_refused(db):
    with pytest.raises(ValueError, match="no step"):
        mark_step_known(db, "whatsapp.exe", "send-message", "compose", "ghost")
    with pytest.raises(ValueError, match="hole"):
        mark_step_known(db, "whatsapp.exe", "send-message", "nowhere", "ghost")


@pytest.mark.parametrize("holes, message", [
    ([], "at least one"),
    ([{"hole": "a", "role": "button", "control_name": "A"}, {"hole": "a", "role": "button", "control_name": "B"}], "twice"),
    ([{"hole": "a", "role": "button", "control_name": "A", "action": "explode"}], "action"),
    ([{"hole": "", "role": "button", "control_name": "A"}], "hole"),
    ([{"hole": "a", "role": "button"}], "control_name"),
])
def test_a_recipe_needs_named_holes_with_a_control_and_a_known_action(tmp_path, holes, message):
    with pytest.raises(ValueError, match=message):
        save_recipe(tmp_path / "user.db", "bad", holes)


def test_recipes_are_listed_with_their_holes_and_saving_again_replaces_the_pattern(db):
    save_recipe(db, "send-message", HOLES[:2])

    assert list_recipes(db) == [{"name": "send-message", "holes": [
        {"hole": "open-chat", "role": "button", "control_name": "Open chat", "automation_id": None, "action": "click", "sensitive": None},
        {"hole": "compose", "role": "button", "control_name": "Message field", "automation_id": None, "action": "click", "sensitive": None},
    ]}]


def test_applying_an_unknown_recipe_or_filling_an_unknown_hole_is_refused(db):
    with pytest.raises(ValueError, match="no recipe"):
        apply_recipe(db, telegram(), "ghost")
    with pytest.raises(ValueError, match="no hole"):
        apply_recipe(db, telegram(), "send-message", {"nowhere": {"role": "button", "control_name": "X"}})


def test_the_first_app_a_recipe_is_taught_on_is_where_it_came_from(db):
    from workflow_factory.recipes import adaptations, recipes_overview
    teach_telegram(db)
    apply_recipe(db, whatsapp(), "send-message", {"compose": {"role": "button", "control_name": "Type a message"}})

    (overview,) = recipes_overview(db)

    assert overview["name"] == "send-message" and overview["origin"] == "telegram.exe"
    assert overview["apps"]["telegram.exe"]["compose"] == "send-message-compose"
    assert set(overview["apps"]) == {"telegram.exe", "whatsapp.exe"}
    assert adaptations(db).get(("whatsapp.exe", "send-message-compose")) == "telegram.exe"
    assert ("telegram.exe", "send-message-compose") not in adaptations(db)  # the original is not adapted from anything
    assert ("whatsapp.exe", "unrelated-step") not in adaptations(db)


def test_a_recipe_never_applied_has_no_origin_and_no_apps_yet(db):
    from workflow_factory.recipes import recipes_overview

    assert recipes_overview(db) == [{**list_recipes(db)[0], "origin": None, "apps": {}}]
