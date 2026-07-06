# Mixtape

A social music app where friends share songs, build collaborative playlists, and track listening stats.

This is the starter repo for **Project 5: Mixtape Bug Hunt**. The app has five open issues in its tracker. Your job is to find, fix, and document at least three of them.

---

## App Structure

```
ai201-project5-mixtape-starter/
├── app.py                      # Flask app factory and DB setup
├── models.py                   # SQLAlchemy models for all entities
├── routes/
│   ├── songs.py                # Song sharing, search, and rating routes
│   ├── playlists.py            # Playlist creation and song management
│   ├── users.py                # User profiles, streaks, notifications
│   └── feed.py                 # Friends listening now, activity feed
├── services/
│   ├── streak_service.py       # Listening streak logic
│   ├── feed_service.py         # Friends listening now feed logic
│   ├── search_service.py       # Song search logic
│   ├── notification_service.py # Notification creation and retrieval
│   └── playlist_service.py     # Playlist retrieval logic
├── tests/
│   ├── test_streaks.py
│   ├── test_search.py
│   └── test_playlists.py
├── seed_data.py                # Populates DB with test data
├── requirements.txt
└── .gitignore
```

The bugs live in the `services/` layer. The routes call services — if something is broken in an endpoint, trace it back to the service it calls.

---

## Setup

Create and activate a virtual environment:

```bash
python -m venv .venv

# macOS / Linux
source .venv/bin/activate

# Windows (Command Prompt)
.venv\Scripts\activate.bat

# Windows (Git Bash)
source .venv/Scripts/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Seed the database with test data:

```bash
python seed_data.py
```

Run the app:

```bash
FLASK_APP=app:create_app flask run
```

> **macOS note:** If the app starts but requests hang or return connection refused, try `http://127.0.0.1:5000` instead of `http://localhost:5000`. On macOS, `localhost` sometimes resolves to an IPv6 address that Flask isn't listening on.

Run tests:

```bash
pytest tests/
```

---

## The Five Open Issues

| # | Title | Affected service |
|---|-------|-----------------|
| 1 | My listening streak keeps resetting | `streak_service.py` |
| 2 | Friends Listening Now shows people from yesterday | `feed_service.py` |
| 3 | The same song keeps showing up twice in search | `search_service.py` |
| 4 | I got notified when a friend added my song to a playlist but not when they rated it | `notification_service.py` |
| 5 | The last song in a playlist never shows up | `playlist_service.py` |

Full issue descriptions are in the **Project 5 brief**. Read them carefully before opening any service file.

---

## Root Cause Analysis

### Bug 1 — My listening streak keeps resetting

**Affected service:** `services/streak_service.py` — `update_listening_streak()`

**Symptom:** Users who listened every single day still saw their streak collapse back to 1 once a week. From the user's perspective the resets looked random, but they always happened on a Sunday.

**Root cause:** The consecutive-day branch contained a spurious day-of-week condition:

```python
elif days_since_last == 1 and today.weekday() != 6:
    user.listening_streak += 1
else:
    user.listening_streak = 1
```

Python's `weekday()` returns 6 for Sunday. So when a user listened on Saturday and again on Sunday, `days_since_last` was 1 (consecutive — should increment), but the `today.weekday() != 6` clause made the condition false, execution fell into the `else`, and the streak was reset to 1. Every user's streak was wiped every Sunday regardless of how consistently they listened. The function's own docstring states the intended rule with no day-of-week exception: "If the user listened yesterday: streak increments by 1."

**The fix:** Remove the spurious weekday clause so consecutiveness is judged purely by calendar-day difference:

```python
elif days_since_last == 1:
```

**How it was diagnosed:** `tests/test_streaks.py::test_streak_increments_on_sunday` failed with `assert 1 == 2` — Saturday→Sunday reset instead of incrementing, while Monday→Tuesday incremented fine. A reset that only occurs on one specific weekday, with `days_since_last` logic otherwise correct, pointed directly at the `weekday() != 6` clause in the increment condition.

**Regression coverage:** `tests/regression/test_streak_regression.py`:

- `test_saturday_to_sunday_is_consecutive` — minimal reproduction: Saturday then Sunday must give a streak of 2.
- `test_week_long_streak_survives_sunday` — the user-visible symptom: listening Monday through Sunday must give a streak of 7, not drop to 1 on day seven.
- `test_skipping_into_sunday_still_resets` — guard against overcorrection: Friday→Sunday genuinely skips Saturday, so the reset to 1 must still happen.

The first two failed before the fix (streak stuck at 1) and pass after it; the guard passes in both states. Full suite after the fix: 18/18 passing.

### Bug 2 — Friends Listening Now shows people from yesterday

**Affected service:** `services/feed_service.py` — `get_friends_listening_now()`

**Symptom:** The "Friends Listening Now" feed (`GET /<user_id>/listening-now`) showed friends who had listened up to a full day earlier. Someone who played a song at 9 PM yesterday still appeared as listening "now" at 8 PM today.

**Root cause:** The query logic — filtering friends' listening events by a recency cutoff, ordering newest-first, and deduplicating to one entry per friend — was all correct. The bug was the recency constant itself:

```python
RECENT_THRESHOLD = timedelta(hours=24)
```

A 24-hour window means "listened at any point in the past day," not "listening now." The intended window is documented in `seed_data.py`, which seeds events "within the past 30 minutes" as *should appear in "listening now"* and events 2+ hours old as *should NOT appear after fix*. Showing older history is explicitly the job of the separate `get_activity_feed()` function, whose docstring notes it is "not filtered by recency."

**The fix:** Set the threshold to the documented 30-minute window:

```python
RECENT_THRESHOLD = timedelta(minutes=30)
```

**How it was diagnosed:** The symptom ("people from yesterday") implied the recency filter was either missing or too wide. Reading `get_friends_listening_now()` showed the filter present and correctly applied, which narrowed the problem to the threshold value. The seed data comments confirmed the intended window (~30 minutes) and the expectation that 2-hour-old events be excluded.

**Regression coverage:** `tests/regression/test_feed_regression.py` (events seeded relative to the real clock, since the service calls `datetime.now`):

- `test_friend_listening_minutes_ago_is_shown` — a friend who listened 10 minutes ago must appear; guards against overcorrecting to a too-narrow window.
- `test_friend_from_yesterday_is_not_shown` — the reported symptom: a friend who listened ~23 hours ago must not appear.
- `test_friend_from_hours_ago_is_not_shown` — pins the seed-data contract: a 2-hour-old event must not appear.

The last two failed before the fix and pass after it; the first passes in both states. Full suite after the fix: 21/21 passing.

### Bug 3 — The same song keeps showing up twice in search

**Affected service:** `services/search_service.py` — `search_songs()`

**Symptom:** A song appeared in search results once per tag it had — a song with three tags showed up three times.

**Root cause:** The search query outer-joined the `song_tags` association table for no reason:

```python
db.session.query(Song)
.outerjoin(song_tags, Song.id == song_tags.c.song_id)
.filter(...)
```

The join contributed nothing — the filter only references `Song.title` and `Song.artist`, no tag columns are selected, and the tags in each result come from the `Song.tags` relationship inside `to_dict()`, not from this join. Its only effect was row multiplication: joining a song to its N `song_tags` rows yields N identical song rows.

**A subtlety — why the tests passed anyway:** in this environment the duplicates were *masked* by a deprecated side effect of SQLAlchemy's legacy `Query.all()` API, which deduplicates full-entity rows before returning them. Probing the same query showed the defect was real underneath: the service returned 1 result for a 3-tag song, but the SQL produced 3 rows (`.count()` said 3, and a SQLAlchemy 2.0-style execution returned 3). The user-reported duplicates were one pagination call, `.count()` usage, or SQLAlchemy migration away from surfacing.

**The fix:** Remove the spurious join (and the now-unused imports), leaving the title/artist filter untouched:

```python
db.session.query(Song)
.filter(
    db.or_(
        Song.title.ilike(f"%{query}%"),
        Song.artist.ilike(f"%{query}%"),
    )
)
```

**How it was diagnosed:** The reported symptom (duplicates proportional to tag count) pointed at a join against the tags table. The join was present but unused by filter or select — and since the existing no-duplicate tests passed, the query was probed directly, comparing the service's output count against the raw SQL row count (1 vs 3), confirming latent row multiplication hidden by legacy-Query deduplication.

**Regression coverage:** `tests/regression/test_search_regression.py`:

- `test_search_sql_produces_one_row_per_song` — captures the exact SQL `search_songs()` executes (via an event listener), re-executes it raw, and asserts one row per returned song. Failed before the fix (`assert 3 == 1`, the same song row appearing three times); passes after.
- `test_multi_tag_song_returned_once_with_all_tags` — user-facing guard: a multi-tag song appears exactly once and still carries all its tags, proving the join removal doesn't affect tag delivery.

Full suite after the fix: 23/23 passing.

### Bug 5 — The last song in a playlist never shows up

**Affected service:** `services/playlist_service.py` — `get_playlist_songs()`

**Symptom:** Viewing any playlist (`GET /playlists/<id>/songs`) always showed one fewer song than the playlist actually contained. Whichever song was in the final position was silently missing, and a playlist with exactly one song appeared completely empty.

**Root cause:** The database query in `get_playlist_songs()` was correct — it joined `playlist_entries`, filtered by playlist ID, and ordered by position, returning every song. The bug was in the return statement, which sliced off the last element of the result list:

```python
return [song.to_dict() for song in songs[:-1]]
```

In Python, `songs[:-1]` means "everything except the last item," so the highest-position song was always dropped after the query. Because the slice never raises an error (on a one-element list it just returns `[]`), the bug failed silently: no exception, no log entry — just a quietly truncated playlist. This also contradicted the function's own docstring, which states "This function returns all songs in the playlist."

**The fix:** Remove the slice so the full ordered result is returned:

```python
return [song.to_dict() for song in songs]
```

**How it was diagnosed:** `tests/test_playlists.py::test_playlist_returns_all_songs` failed with `assert 4 == 5` — the returned list contained Tracks 1–4 of a 5-song playlist, in correct order. Correct ordering plus exactly one missing item at the end pointed away from the query (a wrong join or filter would scramble or drop arbitrary rows) and toward post-query truncation, which led straight to the `[:-1]` slice.

**Regression coverage:** `tests/regression/test_playlist_regression.py` pins down the exact symptom so the bug can't be silently reintroduced:

- `test_last_song_is_not_dropped` — asserts the song in the *final* position is present in the results.
- `test_single_song_playlist_returns_that_song` — asserts a one-song playlist returns that song rather than an empty list (the worst case of the bug).

Both tests failed before the fix, reproducing the bug's behavior, and pass after it. Full suite: all playlist tests green.

---

## How to Read the Code

Start with `models.py` to understand the data model. Then trace a feature through from its route to its service. For example:

- A user rates a song → `POST /songs/<song_id>/rate` → `routes/songs.py` → `notification_service.rate_song()`
- A user views a playlist → `GET /playlists/<id>/songs` → `routes/playlists.py` → `playlist_service.get_playlist_songs()`

Understanding the full call chain is part of the exercise — don't skip to the service file directly.

---

## Submission

Create a branch named `bugfix/mixtape` for your fixes. Each bug fix should be its own commit using conventional format:

```
fix: correct Sunday boundary condition in streak reset logic
```

See the project brief for full submission requirements.
