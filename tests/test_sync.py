"""
Tests for src/managers/sync.py — the per-batch save path. The source, the gap
lookup, the DB session and save_fn are all faked, so no DB or network.
"""
import threading
from datetime import datetime, timedelta, timezone
from unittest import mock

import pytest

from managers import sync

START = datetime(2026, 1, 1, tzinfo=timezone.utc)
END = datetime(2026, 4, 1, tzinfo=timezone.utc)
ONE_GAP = [{"start": START, "end": END}]


def _run(fetch_fn, fetch_kind="range", gaps=ONE_GAP, events=None):
    '''runs fetch_key_source on a fake source; returns (saved batches, progress messages)'''
    events = events if events is not None else []
    save_fn = mock.Mock(side_effect=lambda session, model, batch: events.append(("save", list(batch))))
    src = sync.Source(object, fetch_fn, save_fn, fetch_kind=fetch_kind, keys={"K": {}})
    messages = []
    with mock.patch.dict(sync.SOURCES, {"fake": src}), \
         mock.patch.object(sync, "_get_missing_ranges", return_value=gaps), \
         mock.patch.object(sync, "Session", mock.MagicMock()):
        sync.fetch_key_source("K", START, END, "fake", progress_callback=messages.append)
    return [batch for kind, batch in events if kind == "save"], messages


def test_failure_keeps_batches_saved_before_it():
    events = []

    def fetch(key, start, end, progress_callback=None):
        yield ["a1", "a2"]
        yield ["b1"]
        raise RuntimeError("503 after retries")

    with pytest.raises(RuntimeError, match="503 after retries"):
        _run(fetch, events=events)

    assert [batch for kind, batch in events if kind == "save"] == [["a1", "a2"], ["b1"]]


def test_failure_message_counts_saved_batches():
    messages = []
    save_fn = mock.Mock()

    def fetch(key, start, end, progress_callback=None):
        yield ["a"]
        yield ["b"]
        raise RuntimeError("boom")

    src = sync.Source(object, fetch, save_fn, keys={"K": {}})
    with mock.patch.dict(sync.SOURCES, {"fake": src}), \
         mock.patch.object(sync, "_get_missing_ranges", return_value=ONE_GAP), \
         mock.patch.object(sync, "Session", mock.MagicMock()), \
         pytest.raises(RuntimeError):
        sync.fetch_key_source("K", START, END, "fake", progress_callback=messages.append)

    assert messages[-1] == "failed after saving 2 chunks: boom"


def test_each_batch_is_saved_before_the_next_is_fetched():
    events = []

    def fetch(key, start, end, progress_callback=None):
        for i in (1, 2):
            events.append(("fetch", i))
            yield [i]

    _, messages = _run(fetch, events=events)

    assert events == [("fetch", 1), ("save", [1]), ("fetch", 2), ("save", [2])]
    assert messages[-1] == "done"


def test_cursor_list_is_saved_once():
    saved, messages = _run(lambda key, start, progress_callback=None: ["u1", "u2"], fetch_kind="cursor")

    assert saved == [["u1", "u2"]]
    assert messages[-1] == "done"


def test_nothing_missing_is_up_to_date_without_fetching():
    fetch = mock.Mock()

    saved, messages = _run(fetch, gaps=[])

    fetch.assert_not_called()
    assert saved == []
    assert messages[-1] == "up-to-date"


def test_empty_batches_are_skipped():
    saved, messages = _run(lambda key, start, end, progress_callback=None: iter([[], ["x"], []]))
    assert saved == [["x"]]
    assert messages[-1] == "done"

    saved, messages = _run(lambda key, start, end, progress_callback=None: iter([[], []]))
    assert saved == []
    assert messages[-1] == "up-to-date"


def test_range_fetch_returning_a_list_is_one_batch():
    saved, messages = _run(lambda key, start, end, progress_callback=None: ["x", "y"])

    assert saved == [["x", "y"]]
    assert messages[-1] == "done"


def test_sync_result_reports_partial_failure():
    def fetch(key, start, end, progress_callback=None):
        yield [1]
        yield [2]
        raise RuntimeError("503 after retries")

    src = sync.Source(object, fetch, mock.Mock(), keys={"K1": {}})
    with mock.patch.dict(sync.SOURCES, {"fake": src}), \
         mock.patch.object(sync, "_get_missing_ranges", return_value=ONE_GAP), \
         mock.patch.object(sync, "Session", mock.MagicMock()):
        results = sync.sync("fake", START, END)

    assert results == {"K1": "failed after saving 2 chunks: 503 after retries"}


def test_gaps_closer_than_merge_gaps_are_fetched_as_one_range():
    h = lambda hours: START + timedelta(hours=hours)
    gaps = [
        {"start": h(13), "end": h(13.25)},
        {"start": h(35), "end": h(35.25)},   # next day 11:00, ~22 h later: merged
        {"start": h(38), "end": h(38.25)},   # same day 14:00: merged into the same range
        {"start": h(90), "end": h(90.25)},   # ~52 h later: its own range
    ]
    requested = []

    def fetch(key, start, end, progress_callback=None):
        requested.append((start, end))
        yield [start]

    src = sync.Source(object, fetch, mock.Mock(), keys={"K": {}}, merge_gaps=timedelta(days=1))
    with mock.patch.dict(sync.SOURCES, {"fake": src}), \
         mock.patch.object(sync, "_get_missing_ranges", return_value=gaps), \
         mock.patch.object(sync, "Session", mock.MagicMock()):
        sync.fetch_key_source("K", START, END, "fake")

    assert requested == [(h(13), h(38.25)), (h(90), h(90.25))]


def test_cancel_stops_before_the_next_request():
    cancel = threading.Event()
    fetched = []

    def fetch(key, start, end, progress_callback=None):
        for i in (1, 2, 3):
            fetched.append(i)
            yield [i]

    save_fn = mock.Mock(side_effect=lambda session, model, batch: cancel.set())
    src = sync.Source(object, fetch, save_fn, keys={"K": {}})
    messages = []
    with mock.patch.dict(sync.SOURCES, {"fake": src}), \
         mock.patch.object(sync, "_get_missing_ranges", return_value=ONE_GAP), \
         mock.patch.object(sync, "Session", mock.MagicMock()):
        sync.fetch_key_source("K", START, END, "fake", progress_callback=messages.append, cancel_event=cancel)

    assert fetched == [1]
    assert save_fn.call_count == 1
    assert messages[-1] == "cancelled after saving 1 chunks"
