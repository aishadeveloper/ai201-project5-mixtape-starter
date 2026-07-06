"""
tests/regression/test_notification_regression.py — Mixtape

Regression tests for Bug 4: "I got notified when a friend added my song
to a playlist but not when they rated it."

add_to_playlist() notifies the song's sharer, but rate_song() saves the
rating and returns without ever calling create_notification() — no
'song_rated' notification exists anywhere in the codebase, even though
create_notification()'s docstring names it as an expected type. The
failing test here is EXPECTED TO FAIL until the omission in
services/notification_service.py is fixed.
"""

import pytest
from app import create_app, db
from models import User, Song
from services.notification_service import rate_song, get_notifications


@pytest.fixture
def app():
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()


@pytest.fixture
def sharer_and_song(app):
    """A user who shared a song, plus a friend who will rate it."""
    with app.app_context():
        sharer = User(username="sharer", email="sharer@example.com")
        friend = User(username="friend", email="friend@example.com")
        db.session.add_all([sharer, friend])
        db.session.flush()

        song = Song(title="Golden Hour", artist="Sunset Club", shared_by=sharer.id)
        db.session.add(song)
        db.session.commit()
        yield {"sharer": sharer, "friend": friend, "song": song}


def test_rating_notifies_song_sharer(app, sharer_and_song):
    """
    Regression: when a friend rates a song, the user who shared it must
    receive a 'song_rated' notification — same as they do when the friend
    adds it to a playlist.
    """
    with app.app_context():
        s = sharer_and_song
        rate_song(user_id=s["friend"].id, song_id=s["song"].id, score=5)

        notifications = get_notifications(s["sharer"].id)
        assert len(notifications) == 1  # Bug: no notification is ever created
        assert notifications[0]["type"] == "song_rated"


def test_rating_own_song_does_not_notify(app, sharer_and_song):
    """
    Guard for the fix: rating YOUR OWN song must not notify you —
    mirroring the self-notification check in add_to_playlist().
    """
    with app.app_context():
        s = sharer_and_song
        rate_song(user_id=s["sharer"].id, song_id=s["song"].id, score=4)

        notifications = get_notifications(s["sharer"].id)
        assert notifications == []


def test_rating_still_saved_correctly(app, sharer_and_song):
    """
    Guard for the fix: the rating itself must still be created with the
    right score — adding notification logic must not break the save path.
    """
    with app.app_context():
        s = sharer_and_song
        rating = rate_song(user_id=s["friend"].id, song_id=s["song"].id, score=3)
        assert rating.score == 3
        assert rating.user_id == s["friend"].id
        assert rating.song_id == s["song"].id
