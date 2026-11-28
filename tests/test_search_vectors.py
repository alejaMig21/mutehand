"""The search rule has two implementations, one here and one in the editor (web/src/search.js). Both must give the
answers of tests/search_vectors.json, so the two cannot drift."""

import json
from pathlib import Path

import pytest

from workflow_factory.steps import search_matches

VECTORS = json.loads(Path(__file__).with_name("search_vectors.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("vector", VECTORS, ids=[v["why"] for v in VECTORS])
def test_the_search_rule_gives_the_shared_answer(vector):
    assert search_matches(vector["query"], vector["name"], vector["tags"]) is vector["match"]
