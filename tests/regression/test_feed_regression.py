"""
tests/regression/test_feed_regression.py — Mixtape

Regression tests for Bug 2: "Friends Listening Now shows people from yesterday."

get_friends_listening_now() uses a 24-hour recency window, so anyone who
listened at any point in the past day is presented as listening "now".
Per seed_data.py, only events from the past ~30 minutes should qualify,
and events 2+ hours old should not. The failing tests here are EXPECTED
TO FAIL until the bug in services/feed_service.py is fixed.

Note: the service reads the real clock (datetime.now), so events are
seeded relative to the current time rather than at fixed dates.
"""

import pytest
from datetime import datetime, timedelta, timezone
from app import create_app, db
from models import User, Song, ListeningEvent
from services.feed_service import get_friends_listening_now


@pytest.fixture
def app():
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()


def _seed_user_with_friend_event(minutes_ago):
    """Create a user with one friend who listened `minutes_ago` minutes ago."""
    user = User(username="listener", email="listener@example.com")
    friend = User(username="friend", email="friend@example.com")
    db.session.add_all([user, friend])
    db.session.flush()

    user.friends.append(friend)

    song = Song(title="Some Song", artist="Some Artist", shared_by=friend.id)
    db.session.add(song)
    db.session.flush()

    event = ListeningEvent(
        user_id=friend.id,
        song_id=song.id,
        listened_at=datetime.now(timezone.utc) - timedelta(minutes=minutes_ago),
    )
    db.session.add(event)
    db.session.commit()
    return user


def test_friend_listening_minutes_ago_is_shown(app):
    """
    Guard: a friend who listened 10 minutes ago IS listening now.

    This passes before and after the fix — it prevents an overcorrection
    that makes the recency window too narrow.
    """
    with app.app_context():
        user = _seed_user_with_friend_event(minutes_ago=10)
        feed = get_friends_listening_now(user.id)
        assert len(feed) == 1
        assert feed[0]["friend"]["username"] == "friend"


def test_friend_from_yesterday_is_not_shown(app):
    """
    Regression: the reported symptom — a friend who listened ~23 hours
    ago (yesterday) must NOT appear in "Friends Listening Now".
    """
    with app.app_context():
        user = _seed_user_with_friend_event(minutes_ago=23 * 60)
        feed = get_friends_listening_now(user.id)
        assert feed == []  # Bug: 24h window includes yesterday's listeners


def test_friend_from_hours_ago_is_not_shown(app):
    """
    Regression: per seed_data.py, events 2+ hours old should not appear
    in "listening now" — 2 hours ago is not "now" by any definition.
    """
    with app.app_context():
        user = _seed_user_with_friend_event(minutes_ago=120)
        feed = get_friends_listening_now(user.id)
        assert feed == []  # Bug: 24h window includes this too
