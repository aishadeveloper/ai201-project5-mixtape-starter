"""
tests/regression/test_streak_regression.py — Mixtape

Regression tests for Bug 1: "My listening streak keeps resetting."

update_listening_streak() has a spurious weekday check that wipes every
user's streak to 1 on Sundays, even when they listened the day before.
The failing tests here are EXPECTED TO FAIL until the bug in
services/streak_service.py is fixed.
"""

import pytest
from datetime import datetime, timedelta, timezone
from app import create_app, db
from models import User
from services.streak_service import update_listening_streak


@pytest.fixture
def app():
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()


@pytest.fixture
def user(app):
    with app.app_context():
        u = User(username="streaker", email="streaker@example.com")
        db.session.add(u)
        db.session.commit()
        yield u


def test_saturday_to_sunday_is_consecutive(app, user):
    """
    Regression: listening Saturday then Sunday must increment, not reset.

    This is the minimal reproduction of the bug — the week boundary is
    the only place the streak wrongly resets.
    """
    with app.app_context():
        u = db.session.get(User, user.id)
        saturday = datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        sunday = datetime(2024, 6, 16, 12, 0, 0, tzinfo=timezone.utc)

        update_listening_streak(u, saturday)
        update_listening_streak(u, sunday)
        assert u.listening_streak == 2  # Bug: resets to 1 every Sunday


def test_week_long_streak_survives_sunday(app, user):
    """
    Regression: the user-visible symptom — a streak built up all week
    is wiped out on Sunday.

    Listening every day Monday through Sunday should produce a streak
    of 7. With the bug, six days of progress vanish on day seven.
    """
    with app.app_context():
        u = db.session.get(User, user.id)
        monday = datetime(2024, 6, 10, 12, 0, 0, tzinfo=timezone.utc)

        for day in range(7):  # Monday 6/10 ... Sunday 6/16
            update_listening_streak(u, monday + timedelta(days=day))

        assert u.listening_streak == 7  # Bug: drops back to 1 on Sunday


def test_skipping_into_sunday_still_resets(app, user):
    """
    Guard for the fix: a GENUINE skipped day that lands on Sunday must
    still reset the streak. Friday -> Sunday skips Saturday, so the
    streak should be 1. This prevents an overcorrection that makes
    Sunday always increment.
    """
    with app.app_context():
        u = db.session.get(User, user.id)
        friday = datetime(2024, 6, 14, 12, 0, 0, tzinfo=timezone.utc)
        sunday = datetime(2024, 6, 16, 12, 0, 0, tzinfo=timezone.utc)

        update_listening_streak(u, friday)
        update_listening_streak(u, sunday)
        assert u.listening_streak == 1  # Saturday was skipped — reset is correct
