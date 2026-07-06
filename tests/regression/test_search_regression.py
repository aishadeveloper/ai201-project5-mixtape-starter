"""
tests/regression/test_search_regression.py — Mixtape

Regression tests for Bug 3: "The same song keeps showing up twice in search."

search_songs() outer-joins song_tags for no reason — nothing filters on it
and no tag columns are selected — so the SQL produces one row per tag for
every matching song (a 3-tag song = 3 rows). The duplicates are currently
hidden from callers only because SQLAlchemy's legacy Query API deduplicates
full-entity rows as a side effect. That masking is deprecated behavior and
does not apply to .count(), .limit()/pagination, or 2.0-style execution.

test_search_sql_produces_one_row_per_song captures the defect by inspecting
the SQL the service actually executes, and is EXPECTED TO FAIL until the
spurious join in services/search_service.py is removed.
"""

import pytest
from sqlalchemy import event
from app import create_app, db
from models import User, Song, Tag, song_tags
from services.search_service import search_songs


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


def _search_capturing_sql(query_text):
    """Run search_songs() while capturing the SQL statements it executes."""
    captured = []

    def capture(conn, cursor, statement, parameters, context, executemany):
        if "LIKE" in statement.upper():
            captured.append((statement, parameters))

    event.listen(db.engine, "before_cursor_execute", capture)
    try:
        results = search_songs(query_text)
    finally:
        event.remove(db.engine, "before_cursor_execute", capture)
    return results, captured


def test_search_sql_produces_one_row_per_song(app, multi_tag_song):
    """
    Regression: the search query itself must yield ONE row per matching
    song. With the spurious song_tags join, a 3-tag song produces 3 rows,
    and only deprecated legacy-Query deduplication hides them — .count(),
    pagination, or a SQLAlchemy 2.0-style migration would all expose the
    duplicates users reported.
    """
    with app.app_context():
        results, captured = _search_capturing_sql("Crown")
        assert len(results) == 1

        # Re-execute the exact SQL the service ran and count raw rows.
        statement, parameters = captured[0]
        rows = db.session.connection().exec_driver_sql(statement, parameters).fetchall()
        assert len(rows) == len(results)  # Bug: 3 SQL rows for 1 song


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
