## Main App Flow

```mermaid
flowchart TD
    A[app.py create_app()] --> B[Configure app & init db]
    B --> C[Register blueprints]
    C --> D[Songs route /songs]
    C --> E[Playlists route /playlists]
    C --> F[Users route /users]
    C --> G[Feed route /feed]
    B --> H[db.create_all()]

    subgraph RouteLayer[Route Layer]
        D --> D1[GET /songs/search]
        D --> D2[GET /songs/<song_id>]
        D --> D3[POST /songs/<song_id>/rate]
        D --> D4[POST /songs/<song_id>/listen]

        E --> E1[POST /playlists/]
        E --> E2[GET /playlists/<playlist_id>]
        E --> E3[GET /playlists/<playlist_id>/songs]
        E --> E4[POST /playlists/<playlist_id>/songs]

        F --> F1[GET /users/<user_id>]
        F --> F2[GET /users/<user_id>/streak]
        F --> F3[GET /users/<user_id>/notifications]
        F --> F4[POST /users/notifications/<notification_id>/read]

        G --> G1[GET /feed/<user_id>/listening-now]
        G --> G2[GET /feed/<user_id>/activity]
    end

    subgraph ServiceLayer[Service Layer]
        S1[search_service]
        S2[playlist_service]
        S3[notification_service]
        S4[streak_service]
        S5[feed_service]
    end

    D1 --> S1
    D2 --> S1
    D3 --> S3
    D4 --> S4

    E1 --> S2
    E2 --> S2
    E3 --> S2
    E4 --> S3

    F1 --> M1[Direct User load]
    F2 --> S4
    F3 --> S3
    F4 --> S3

    G1 --> S5
    G2 --> S5

    subgraph DataModels[Data / Model Layer]
        M2[User]
        M3[Song]
        M4[Playlist]
        M5[ListeningEvent]
        M6[Rating]
        M7[Notification]
        M8[Tag]
    end

    S1 --> M3
    S1 --> M8
    S2 --> M2
    S2 --> M4
    S2 --> M3
    S3 --> M2
    S3 --> M3
    S3 --> M4
    S3 --> M6
    S3 --> M7
    S4 --> M2
    S4 --> M5
    S5 --> M2
    S5 --> M4

    classDef appStyle fill:#f9f,stroke:#333,stroke-width:2px;
    classDef routeStyle fill:#bbf,stroke:#333;
    classDef serviceStyle fill:#bfb,stroke:#333;
    classDef dataStyle fill:#ffd,stroke:#333;
    class A,B,C,H appStyle;
    class D,E,F,G,D1,D2,D3,D4,E1,E2,E3,E4,F1,F2,F3,F4,G1,G2 routeStyle;
    class S1,S2,S3,S4,S5 serviceStyle;
    class M1,M2,M3,M4,M5,M6,M7,M8 dataStyle;
```

### Flow summary
- `app.py` initializes the Flask app, configures database settings, and registers blueprints.
- Each blueprint route maps HTTP endpoints to one or more service functions.
- Service functions contain business logic, validate data, and read/update the database.
- Models such as `User`, `Song`, `Playlist`, `ListeningEvent`, `Rating`, `Notification`, and `Tag` represent persistent data.
- The request path is: client → blueprint route → service layer → model/db → JSON response.

