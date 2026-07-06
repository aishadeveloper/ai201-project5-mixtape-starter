"""
tests/test_playlist_regression.py — Mixtape

Regression tests for the "playlist drops the last song" bug.

get_playlist_songs() truncates its results with songs[:-1], so the
song in the final position is always missing. These tests are EXPECTED
TO FAIL until the bug in services/playlist_service.py is fixed.
"""

import pytest
from app import create_app, db
from models import User, Song, Playlist, playlist_entries
from services.playlist_service import get_playlist_songs


@pytest.fixture
def app():
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()


def _seed_playlist_with_songs(song_count):
    """Create a user and a playlist containing `song_count` positioned songs."""
    user = User(username="dj", email="dj@example.com")
    db.session.add(user)
    db.session.flush()

    songs = [
        Song(title=f"Track {i}", artist="Various", shared_by=user.id)
        for i in range(1, song_count + 1)
    ]
    db.session.add_all(songs)
    db.session.flush()

    playlist = Playlist(name="Regression Playlist", created_by=user.id)
    db.session.add(playlist)
    db.session.flush()

    for i, song in enumerate(songs):
        db.session.execute(
            playlist_entries.insert().values(
                playlist_id=playlist.id,
                song_id=song.id,
                position=i + 1,
                added_by=user.id,
            )
        )

    db.session.commit()
    return playlist


def test_last_song_is_not_dropped(app):
    """
    Regression: the song in the FINAL position must be returned.

    The bug slices the result list with [:-1], so whichever song is
    last in the playlist silently disappears.
    """
    with app.app_context():
        playlist = _seed_playlist_with_songs(3)
        titles = [s["title"] for s in get_playlist_songs(playlist.id)]
        assert "Track 3" in titles  # Bug: last song is sliced off


def test_single_song_playlist_returns_that_song(app):
    """
    Regression: a playlist with exactly one song must return it.

    This is the worst case of the bug — [:-1] on a one-element list
    returns [], so the playlist looks completely empty.
    """
    with app.app_context():
        playlist = _seed_playlist_with_songs(1)
        songs = get_playlist_songs(playlist.id)
        assert len(songs) == 1  # Bug: returns [] instead
