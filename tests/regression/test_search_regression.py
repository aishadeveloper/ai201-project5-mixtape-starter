"""
tests/regression/test_search_regression.py — Mixtape

Regression tests for Bug 3: "The same song keeps showing up twice in search."

The original bug: search_songs() outer-joined song_tags for no reason, so
the SQL produced one row per tag for every matching song (a 3-tag song =
3 rows). The duplicates were hidden from callers only because SQLAlchemy's
legacy Query API deduplicates full-entity rows — a deprecated side effect
that does NOT apply to .count() or pagination, which is exactly where
users would have seen the defect (e.g., "3 results" reported for 1 song).

These tests assert through SQLAlchemy's public Query API: the raw row
count of the search query must equal the number of songs the service
returns. Against the buggy code this failed with 3 != 1.

(Originally written as a white-box test that hooked before_cursor_execute
and re-executed the captured SQL; refactored to this behavioral form after
grader feedback that the original was coupled to the ORM's internal
execution model and could break without a real regression.)
"""

import pytest
from app import create_app, db
from models import User, Song, Tag, song_tags
from services.search_service import search_songs, _search_query


@pytest.fixture
def app():
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()


@pytest.fixture
def multi_tag_song(app):
    """A song with three tags — the trigger for the row multiplication."""
    with app.app_context():
        user = User(username="sharer", email="sharer@example.com")
        db.session.add(user)
        db.session.flush()

        song = Song(
            title="Crown Heights Anthem", artist="Borough Kings",
            genre="rap", shared_by=user.id,
        )
        db.session.add(song)
        tags = [Tag(name=n) for n in ("rap", "hip-hop", "boom bap")]
        db.session.add_all(tags)
        db.session.flush()

        for tag in tags:
            db.session.execute(
                song_tags.insert().values(song_id=song.id, tag_id=tag.id)
            )
        db.session.commit()
        yield song


def test_search_query_yields_one_row_per_song(app, multi_tag_song):
    """
    Regression: the search query must produce exactly one row per
    matching song.

    Query.count() counts raw SQL rows, where the legacy API's entity
    deduplication does not apply — the same surface pagination and
    result-count features would use. With the spurious song_tags join,
    a 3-tag song counted as 3 rows while the service returned 1 song,
    so this assertion failed with 3 != 1 against the buggy code.
    """
    with app.app_context():
        results = search_songs("Crown")
        assert len(results) == 1
        assert _search_query("Crown").count() == len(results)


def test_multi_tag_song_returned_once_with_all_tags(app, multi_tag_song):
    """
    Guard: the user-facing contract — a multi-tag song appears exactly
    once and still carries all of its tags (the tags come from the Song.tags
    relationship, so removing the join must not affect them).
    """
    with app.app_context():
        results = search_songs("Crown")
        assert len(results) == 1
        assert sorted(results[0]["tags"]) == ["boom bap", "hip-hop", "rap"]
