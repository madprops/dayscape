"""Basic tests for Dayscape logic."""

from datetime import date

from dayscape.models import Entry, relative_label
from dayscape.search import parse
from dayscape.stats import summarize


def test_entry_is_empty():
    assert Entry(date(2026, 1, 1), None, "").is_empty
    assert Entry(date(2026, 1, 1), None, "   \n").is_empty
    assert not Entry(date(2026, 1, 1), 5, "").is_empty
    assert not Entry(date(2026, 1, 1), None, "hello").is_empty


def test_entry_lines():
    e = Entry(date(2026, 1, 1), 5, "- hello\n* world\n  - sub\nplain")
    assert e.lines == ["hello", "world", "sub", "plain"]


def test_relative_label():
    today = date(2026, 10, 8)
    assert relative_label(today, today) == "Today"
    assert relative_label(today - timedelta(days=1), today) == "Yesterday"


def test_summarize():
    s = summarize([1, 2, None, 4])
    assert s.count == 3
    assert s.mean is not None and abs(s.mean - 2.333) < 0.01


def test_search_parse():
    q = parse("hello -world #tag score:5")
    assert "hello" in q.terms
    assert "world" in q.excludes
    assert "tag" in q.tags
    assert len(q.score_tests) == 1
    assert q.score_tests[0](5)
    assert not q.score_tests[0](4)


from datetime import timedelta
