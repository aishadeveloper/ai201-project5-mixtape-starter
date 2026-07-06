## Codebase Map

### Root
- app.py
  - Main Flask app entrypoint.
  - Configures routes, app setup, and starts the server.

- models.py
  - Defines the data models and database structures.
  - Likely contains SQLAlchemy models or in-memory data classes for songs, playlists, users, etc.

- README.md
  - Project overview, setup instructions, and usage information.

- requirements.txt
  - Python dependency list for the project.

- seed_data.py
  - Script to populate initial data for the application.
  - Used to load demo songs, playlists, users, or other seed records.

### Routes
- __init__.py
  - Route package initializer.
  - Likely registers blueprints or imports route modules.

- feed.py
  - API endpoints related to feed content.
  - Probably handles fetching recommended songs or activity feed.

- playlists.py
  - Playlist-related endpoints.
  - Handles creating, viewing, updating playlists.

- songs.py
  - Song-related endpoints.
  - Handles searching, listing, or retrieving songs.

- users.py
  - User-related endpoints.
  - Handles login, signup, profile, or user state retrieval.

### Services
- __init__.py
  - Service package initializer.

- feed_service.py
  - Business logic for feed generation.
  - May compute recommendations or feed items.

- notification_service.py
  - Notification-related logic.
  - Likely handles creating and delivering notifications to users.

- playlist_service.py
  - Encapsulates playlist creation and management logic.
  - Likely used by playlists.py.

- search_service.py
  - Search business logic for songs/playlists/users.
  - Likely used by songs.py.

- streak_service.py
  - Tracks user streaks or activity streak logic.
  - Provides streak computations and updates.

### Tests
- __init__.py
  - Initializes the test package.

- test_playlists.py
  - Tests for playlist functionality.

- test_search.py
  - Tests for search functionality.

- test_streaks.py
  - Tests for streak-related logic.



## Data Flow: Playlists

1. Client request
   - `POST /playlists/` to create a playlist
   - `GET /playlists/<playlist_id>` to fetch playlist metadata
   - `GET /playlists/<playlist_id>/songs` to list songs
   - `POST /playlists/<playlist_id>/songs` to add a song

2. Route layer
   - playlists.py receives request JSON / URL params.
   - Validates required fields like `name`, `created_by`, `song_id`, `added_by`.

3. Service layer
   - `create_playlist(...)` in playlist_service.py
     - loads `User` by `created_by`
     - creates `Playlist` row
     - commits to DB
   - `get_playlist(...)`
     - loads `Playlist` by ID
     - returns playlist dict
   - `get_playlist_songs(...)`
     - loads `Playlist`
     - queries `Song` joined through `playlist_entries`
     - orders by `playlist_entries.position`
     - returns song dict list
   - `add_to_playlist(...)` in notification_service.py
     - verifies `Song`, `User`, `Playlist`
     - appends song to `playlist.songs` association
     - commits
     - optionally creates a `Notification` if the adder is not the song sharer

4. Data models
   - `Playlist` stored in models.py
   - playlist-song relation stored via `playlist_entries` association table
   - ordered playlist entries use `position`, `added_by`, `added_at`

5. Response
   - route returns JSON for created playlist, playlist details, song list, or add-song success

---

## Data Flow: Search

1. Client request
   - `GET /songs/search?q=<query>`

2. Route layer
   - songs.py reads query string `q`
   - returns 400 if no query provided

3. Service layer
   - `search_songs(query)` in search_service.py
   - queries `Song` records
   - filters by `Song.title.ilike(...)` or `Song.artist.ilike(...)`
   - optionally uses `song_tags` join so song tags are available
   - returns list of `song.to_dict()` results

4. Data models
   - `Song` model stores title, artist, album, genre, shared_by, tags
   - `Tag` and `song_tags` provide song metadata for search result payload

5. Response
   - route returns JSON with `results` array and `count`

---

## Data Flow: Streaks

1. Client request
   - `POST /songs/<song_id>/listen` with JSON `{ "user_id": ... }`

2. Route layer
   - songs.py validates `user_id`
   - calls `record_listening_event(user_id, song_id)`

3. Service layer
   - `record_listening_event(...)` in streak_service.py
     - loads `User` by ID
     - creates `ListeningEvent` with current UTC timestamp
     - calls `update_listening_streak(user, now)`
     - commits event and user changes
   - `update_listening_streak(...)`
     - if user has no prior `last_listened_at`, set streak to 1
     - if last listen was today, leave streak unchanged
     - if last listen was yesterday, increment streak
     - otherwise reset streak to 1
     - updates `user.last_listened_at`

4. Data models
   - `User` stores `listening_streak` and `last_listened_at`
   - `ListeningEvent` records each listen event with `song_id` and timestamp

5. Response
   - route returns JSON of the created `ListeningEvent`
   - streak state is updated in the user record for later retrieval



## Exact JSON fields returned by endpoints

### `POST /playlists/`
Success `201`
- `id`
- `name`
- `created_by`
- `created_at`
- `is_collaborative`

Error `400`
- `error`

---

### `GET /playlists/<playlist_id>`
Success `200`
- `id`
- `name`
- `created_by`
- `created_at`
- `is_collaborative`

Error `404`
- `error`

---

### `GET /playlists/<playlist_id>/songs`
Success `200`
- `songs`: array of song objects
- `count`: integer

Each song object includes:
- `id`
- `title`
- `artist`
- `album`
- `genre`
- `shared_by`
- `shared_at`
- `share_note`
- `tags`: array of strings

Error `404`
- `error`

---

### `POST /playlists/<playlist_id>/songs`
Success `201`
- `message` (`"Song added to playlist"`)

Error `400`
- `error`

---

### `GET /songs/search?q=<query>`
Success `200`
- `results`: array of song objects
- `count`: integer

Each song object includes:
- `id`
- `title`
- `artist`
- `album`
- `genre`
- `shared_by`
- `shared_at`
- `share_note`
- `tags`

Error `400`
- `error`

---

### `GET /songs/<song_id>`
Success `200`
- `id`
- `title`
- `artist`
- `album`
- `genre`
- `shared_by`
- `shared_at`
- `share_note`
- `tags`

Error `404`
- `error`

---

### `POST /songs/<song_id>/rate`
Success `201`
- `id`
- `user_id`
- `song_id`
- `score`
- `rated_at`

Error `400`
- `error`

---

### `POST /songs/<song_id>/listen`
Success `201`
- `id`
- `user_id`
- `song_id`
- `listened_at`

Error `400`
- `error`

---

### `GET /users/<user_id>`
Success `200`
- `id`
- `username`
- `listening_streak`
- `last_listened_at`

Error `404`
- `error`

---

### `GET /users/<user_id>/streak`
Success `200`
- `user_id`
- `streak`

Error `404`
- `error`

---

### `GET /users/<user_id>/notifications`
Success `200`
- `notifications`: array of notification objects
- `count`: integer

Each notification object includes:
- `id`
- `user_id`
- `type`
- `body`
- `created_at`
- `read`

Error `404`
- `error`

---

### `POST /users/notifications/<notification_id>/read`
Success `200`
- `message` (`"Notification marked as read"`)

Error `404`
- `error`

---

### `GET /feed/<user_id>/listening-now`
Success `200`
- `feed`: array of feed items
- `count`: integer

Each feed item includes:
- `friend`: user object
- `song`: song object
- `listened_at`

User object includes:
- `id`
- `username`
- `listening_streak`
- `last_listened_at`

Song object includes:
- `id`
- `title`
- `artist`
- `album`
- `genre`
- `shared_by`
- `shared_at`
- `share_note`
- `tags`

Error `404`
- `error`

---

### `GET /feed/<user_id>/activity`
Success `200`
- `feed`: array of feed items
- `count`: integer

Each feed item includes:
- `friend`: user object
- `song`: song object
- `listened_at`

Error `404`
- `error`