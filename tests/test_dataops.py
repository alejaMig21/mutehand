"""The data system nodes as pure functions: fields in, Data out. A bad value raises DataError with a message that
never contains the value itself, because the value may be private."""

import pytest

from workflow_factory.dataops import OPS, DataError, apply, check_op


def run(op, **fields):
    return apply(op, fields)["value"]


# --- fixed value, convert ---------------------------------------------------------------------------------

def test_a_fixed_value_gives_itself_out():
    assert run("fixed", value={"a": [1, 2]}) == {"a": [1, 2]}


@pytest.mark.parametrize("value, to, expected", [
    ("12", "number", 12), (" 3.5 ", "number", 3.5), (7, "number", 7), ("12", "integer", 12), (4.0, "integer", 4),
    ("true", "boolean", True), (" FALSE ", "boolean", False), (1, "boolean", True), (0, "boolean", False),
    (5, "text", "5"), (2.5, "text", "2.5"), (3.0, "text", "3"), (True, "text", "true"), ("x", "text", "x"),
    ([1, "a"], "text", '[1, "a"]'), ({"k": 1}, "text", '{"k": 1}'),
])
def test_convert_between_text_number_integer_and_boolean(value, to, expected):
    result = run("convert", value=value, to=to)

    assert result == expected and type(result) is type(expected)


@pytest.mark.parametrize("value, to", [
    ("abc", "number"), ("1,5", "number"), ("nan", "number"), ("inf", "number"), (True, "number"), (None, "number"),
    ("1.5", "integer"), (1.5, "integer"), ("x", "integer"), ("maybe", "boolean"), (2, "boolean"), (None, "text"),
])
def test_convert_refuses_what_it_cannot_convert_without_echoing_the_value(value, to):
    with pytest.raises(DataError) as error:
        run("convert", value=value, to=to)

    assert str(value) not in str(error.value) or str(value) in ("", "1", "x")  # short tokens could appear by chance


def test_convert_to_an_unknown_type_is_refused():
    with pytest.raises(DataError, match="to"):
        run("convert", value=1, to="date")


# --- text -------------------------------------------------------------------------------------------------

def test_split_cuts_a_text_at_a_separator_and_can_trim_the_pieces():
    assert run("split", text="a, b ,c", separator=",") == ["a", " b ", "c"]
    assert run("split", text="a, b ,c", separator=",", trim=True) == ["a", "b", "c"]


@pytest.mark.parametrize("fields", [dict(text="a", separator=""), dict(text=3, separator=","), dict(text="a", separator=1)])
def test_split_needs_text_and_a_non_empty_separator(fields):
    with pytest.raises(DataError):
        run("split", **fields)


def test_join_puts_a_list_of_simple_values_into_one_text():
    assert run("join", items=["a", 2, True, 1.5], separator="-") == "a-2-true-1.5"


@pytest.mark.parametrize("items", ["abc", [[1]], [{"a": 1}], [None]])
def test_join_needs_a_list_of_simple_values(items):
    with pytest.raises(DataError):
        run("join", items=items, separator=",")


def test_format_fills_named_places_and_keeps_doubled_braces():
    assert run("format", template="Hi {name}, you have {n} {{new}}", values={"name": "Ada", "n": 3}) == "Hi Ada, you have 3 {new}"


@pytest.mark.parametrize("template, values", [("{missing}", {}), ("{a}", "not an object"), (3, {})])
def test_format_refuses_a_missing_name_or_wrong_kinds(template, values):
    with pytest.raises(DataError):
        run("format", template=template, values=values)


def test_format_never_reads_attributes_or_calls_anything():
    # the Python format mini-language would resolve {a.__class__}; a name here is letters, digits and underscore only
    assert run("format", template="{a.__class__} {a.b} {a!r}", values={"a": 1}) == "{a.__class__} {a.b} {a!r}"


def test_regex_reports_a_match_its_groups_and_the_first_group_as_the_value():
    out = apply("regex", {"text": "order 4521 shipped", "pattern": r"order (\d+) (\w+)"})

    assert out == {"match": True, "groups": ["4521", "shipped"], "value": "4521"}


def test_regex_without_groups_gives_the_whole_match_and_no_match_gives_nothing():
    assert apply("regex", {"text": "abc123", "pattern": r"\d+"})["value"] == "123"
    assert apply("regex", {"text": "abc", "pattern": r"\d+"}) == {"match": False, "groups": [], "value": None}


@pytest.mark.parametrize("fields", [dict(text="a", pattern="("), dict(text="a", pattern=""), dict(text=1, pattern="a"),
                                    dict(text="a", pattern="a" * 600), dict(text="a" * 200_000, pattern="a")])
def test_regex_refuses_a_bad_or_too_big_pattern_or_text(fields):
    with pytest.raises(DataError):
        apply("regex", fields)


# --- object fields ----------------------------------------------------------------------------------------

def test_get_reads_a_field_by_a_dotted_path_through_objects_and_lists():
    assert run("get", object={"a": {"b": [10, 20]}}, path="a.b.1") == 20


@pytest.mark.parametrize("path", ["a.x", "a.b.5", "z", "a.b.x", ""])
def test_get_refuses_a_path_that_leads_nowhere(path):
    with pytest.raises(DataError):
        run("get", object={"a": {"b": [10]}}, path=path)


def test_set_returns_a_new_object_with_the_field_written_and_leaves_the_original_alone():
    original = {"a": {"b": 1}}

    result = run("set", object=original, path="a.c.d", value=5)

    assert result == {"a": {"b": 1, "c": {"d": 5}}} and original == {"a": {"b": 1}}


@pytest.mark.parametrize("fields", [dict(object=[1], path="a", value=1), dict(object={"a": 1}, path="a.b", value=1),
                                    dict(object={}, path="", value=1)])
def test_set_refuses_what_it_cannot_write(fields):
    with pytest.raises(DataError):
        run("set", **fields)


# --- math -------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("operation, a, b, expected", [
    ("add", 2, 3, 5), ("subtract", 2, 3, -1), ("multiply", 4, 2.5, 10), ("divide", 7, 2, 3.5), ("divide", 8, 2, 4),
    ("modulo", 7, 3, 1), ("power", 2, 10, 1024), ("add", 0.1, 0.2, pytest.approx(0.3)),
])
def test_math_does_the_six_operations(operation, a, b, expected):
    assert run("math", a=a, b=b, operation=operation) == expected


@pytest.mark.parametrize("operation, a, b", [
    ("divide", 1, 0), ("modulo", 1, 0), ("power", 10, 10000), ("power", -8, 0.5), ("add", "1", 2), ("add", True, 1),
    ("add", None, 1), ("average", 1, 2),
])
def test_math_refuses_division_by_zero_overflow_non_numbers_and_unknown_operations(operation, a, b):
    with pytest.raises(DataError):
        run("math", a=a, b=b, operation=operation)


# --- logic ------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("operator, a, b, expected", [
    ("equals", 1, 1, True), ("equals", 1, True, False), ("equals", "a", "a", True), ("equals", [1], [1], True),
    ("equals", 1, "1", False), ("not_equals", 1, 2, True), ("greater", 3, 2, True), ("greater_or_equal", 2, 2, True),
    ("less", "a", "b", True), ("less_or_equal", 2, 1, False), ("contains", "hello", "ell", True),
    ("contains", [1, 2], 2, True), ("contains", [1, 2], 3, False), ("starts_with", "hello", "he", True),
    ("ends_with", "hello", "lo", True), ("ends_with", "hello", "he", False),
])
def test_compare_gives_a_boolean_and_never_confuses_booleans_with_numbers(operator, a, b, expected):
    result = run("compare", a=a, b=b, operator=operator)

    assert result is expected


@pytest.mark.parametrize("operator, a, b", [
    ("greater", 1, "1"), ("less", None, 1), ("greater", True, 1), ("contains", 5, 1), ("starts_with", 1, "a"),
    ("sort_of", 1, 1),
])
def test_compare_refuses_mismatched_kinds_and_unknown_operators(operator, a, b):
    with pytest.raises(DataError):
        run("compare", a=a, b=b, operator=operator)


@pytest.mark.parametrize("op, fields, expected", [
    ("and", dict(a=True, b=True), True), ("and", dict(a=True, b=False), False), ("or", dict(a=False, b=False), False),
    ("or", dict(a=False, b=True), True), ("not", dict(a=True), False), ("not", dict(a=False), True),
])
def test_and_or_not_work_on_booleans(op, fields, expected):
    assert run(op, **fields) is expected


@pytest.mark.parametrize("op, fields", [("and", dict(a=1, b=True)), ("or", dict(a="yes", b=False)), ("not", dict(a=0)),
                                        ("not", dict(a=None))])
def test_logic_does_not_guess_the_truth_of_a_non_boolean(op, fields):
    with pytest.raises(DataError):
        run(op, **fields)


# --- the catalogue ----------------------------------------------------------------------------------------

def test_every_operation_is_listed_with_the_fields_it_takes():
    assert set(OPS) == {"fixed", "convert", "split", "join", "format", "regex", "get", "set", "math", "compare", "and", "or", "not"}


def test_check_op_requires_the_fields_and_refuses_unknown_ones_and_unknown_operations():
    check_op("math", {"a": {}, "b": {}, "operation": {}})
    with pytest.raises(ValueError, match="needs"):
        check_op("math", {"a": {}})
    with pytest.raises(ValueError, match="unknown field"):
        check_op("not", {"a": {}, "z": {}})
    with pytest.raises(ValueError, match="operation"):
        check_op("sing", {})
    with pytest.raises(ValueError, match="operation"):
        check_op(None, {})
