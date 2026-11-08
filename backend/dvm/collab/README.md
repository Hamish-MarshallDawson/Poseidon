# Shared investigation sessions (issue #100)

Backend for collaboration: log in, resume your last session, invite a friend, and see live what each member is
viewing and tracking, plus the session's shared tracking list and documents. It is a **shared investigation
workspace**: never call it a dashboard in the UI.

Built on our own WebSocket hub (research report option a): presence lives in memory, everything else in Tiger
(plain tables `users`, `collab_sessions`, `collab_members`, `collab_invites`, `collab_list`, `collab_documents`,
`collab_activity`, created at start-up by `schema.py`). Without `TIGER_DATABASE_URL` (local dev, CI) the same
API runs on an in-memory store that is lost on restart.

Files: `schema.py` (tables), `store.py` (Postgres and in-memory stores), `live.py` (WebSocket messages, presence
fan-out, token expiry), `routes.py` (REST). `app.py` only mounts the router, starts `hub.run` in `lifespan`, and
hands the new `/ws` message types to `hub.on_ws`.

## Conventions

- Paths below are backend paths; through the site they sit under `/api` like the other routes.
- Every route needs `Authorization: Bearer <Auth0 access token>` (401 without). **The identity is the token's
  `sub`**; the user row is created on first call. Name and picture are display only.
- Local dev without Auth0: no token needed, and the header `X-Dev-User: <name>` makes you the user `dev|<name>`
  (on the socket, put `"dev_user": "<name>"` in `session_join`), so two browsers can be two users.
- Times are epoch ms UTC. User and session ids are uuid strings; document and activity ids are integers.
- A session you are not a member of answers **404**, the same as one that doesn't exist.
- 503 means the collaboration tables aren't ready (Tiger not connected yet); retry.
- Render every name, title and document body as **plain text**, never HTML.

Shapes used below:

```
User    {id, name|null, picture|null}
Member  {id, name, picture, role: "owner"|"member", joined_at, last_active_at}
Entry   {mmsi, status: "open"|"reviewed"|"no_action", added_by: userId, added_at, updated_by: userId, updated_at}
Doc     {id, mmsi|null, author_id: userId, body, created_at, kind: "note"|"briefing"|"summary", mmsis: [mmsi]}
Session {id, title, created_by: userId, created_at, members: [Member], list: [Entry], documents: [Doc]}
```

`documents` holds the newest 200, oldest first. `mmsi: null` on a document means a note on the whole session.

## REST

| Method and path | Body | Answer |
|---|---|---|
| `GET /me` | | `{user: User, last_session: {id, title, role, last_active_at} \| null}` |
| `POST /me` | `{name?, picture?}` (name at most 80 chars; picture an `https://` URL) | `{user: User}` |
| `POST /sessions` | `{title}` (1 to 120 chars) | 201, `Session` (you are its owner) |
| `GET /sessions` | | `{sessions: [{id, title, role, created_at, last_active_at, members: count, online: [User]}]}`, most recent first; `online` = other members in it now (not private) |
| `GET /sessions/{id}` | | `Session` |
| `GET /sessions/{id}/activity?limit=50` | | `{activity: [{id, actor_id, kind, mmsi\|null, at}]}`, newest first |
| `POST /sessions/{id}/invites` | | 201, `{token, session_id, expires_at}`; **owner only** (403 for a member) |
| `POST /invites/{token}/accept` | | `Session`; 404 if the link is unknown, expired, or used by someone else |
| `POST /sessions/{id}/list` | `{mmsi, status?: "open"}` | 201, `{entry: Entry}`; a ship already listed comes back unchanged |
| `PATCH /sessions/{id}/list/{mmsi}` | `{status}` | `{entry: Entry}`; 404 if not listed |
| `DELETE /sessions/{id}/list/{mmsi}` | | 204 |
| `POST /sessions/{id}/documents` | `{mmsi?: number\|null, body, kind?: "note"\|"briefing", mmsis?: [mmsi]}` (body 1 to 4000 chars, trimmed; a `briefing` needs 1 to 10 `mmsis`, the ships it covers) | 201, `{document: Doc}` |
| `POST /sessions/{id}/summary` | | 201, `{document: Doc}` of kind `summary`: Gemini summarises the notes, saved briefings and tracked ships in neutral wording. Any member. 503 without `GEMINI_API_KEY`, 502 if Gemini fails |

Activity `kind`s: `created`, `joined`, `added`, `removed`, `status_open`, `status_reviewed`, `status_no_action`,
`noted`, `briefing_saved`, `summarised`.

**Wording for documents and the list (show it above the note box):** "A flag is a prompt to review, not an
accusation." Statuses are deliberately neutral (`open`, `reviewed`, `no_action`); there is no free-text status.
Documents are append-only: no edit or delete.

### Login flow ("Hello, welcome Hamish. Resume your last session?")

1. After Auth0 login, `POST /me` with `{name: user.name, picture: user.picture}` from the Auth0 SPA user profile.
2. `GET /me`: greet `user.name`; if `last_session` is set, offer to resume it.

### Invite flow

1. The owner calls `POST /sessions/{id}/invites` and shares `https://<site>/?invite=<token>` (the frontend picks
   the URL; the backend only knows the token). The link is one-time and lasts 7 days; only its SHA-256 is stored.
2. The friend opens it, logs in, and the frontend calls `POST /invites/{token}/accept`, then joins the session.

## WebSocket (`/ws`, after the usual `{"type": "auth", "token"}` first message)

Messages from the server carry `seq` as all `/ws` messages do. Ship deltas keep flowing as before.

Client to server:

```
{"type": "session_join", "session_id": "<uuid>"}           one session per socket; joining another leaves the first
{"type": "session_leave"}
{"type": "presence", "viewing": mmsi|null, "following": [mmsi], "bbox": [minLon, minLat, maxLon, maxLat]|null,
 "private": false}
{"type": "auth", "token": "<fresher access token>"}        same user only; extends the socket past the old exp
```

- Send `presence` about once every 2 s while something changes, and **at least every 10 s** as a heartbeat: a
  user silent for 30 s drops off everyone's list. `private: true` hides you from the others (you still see them).
- `following` keeps at most 100 valid 9-digit MMSIs; anything else is dropped.

Server to client:

```
{"type": "session_joined", "session_id", "role", "user_id", "session": Session}
{"type": "presence", "session_id", "users": [{id, name, picture, viewing, following, bbox, ts}]}
{"type": "list_delta", "session_id", "op": "put", "entry": Entry}
{"type": "list_delta", "session_id", "op": "remove", "entry": {mmsi, updated_by, updated_at}}
{"type": "document", "session_id", "document": Doc}
{"type": "member_joined", "session_id", "member": Member}
{"type": "error", "code": "forbidden"|"bad_request"|"unavailable", "for": "<message type>", ...}
```

- `presence` is the full list for the session (including you, unless private), sent within about 1 s of any
  change, only to that session's members. One entry per user (their most recent tab).
- `list_delta` and `document` arrive for changes made by anyone, including you (apply them idempotently by
  `mmsi` and `id`). An unknown `added_by` or `author_id` means a new member: refetch `GET /sessions/{id}`.
- `forbidden` on `session_join`: not a member (or no such session). Nothing about the session is sent.

### Token expiry

The token is checked at connect and again on every `session_join`. When the token's `exp` passes, the server
closes the socket with code **1008, reason "token expired"**. To stay connected, get a fresh token from the Auth0
SDK (`getAccessTokenSilently`) shortly before `exp` and send it as `{"type": "auth", "token"}`; a token for a
different user closes the socket. On a 1008 close, reconnect with a fresh token.

## Not built (MVP cuts)

Emailed invites, Auth0 Organizations, a roles UI (roles are fixed: owner invites, members do everything else),
CRDT editing, editing or deleting documents, removing members, presence deltas (full list each time), more than
one backend process (presence is in this process's memory). Name and picture are taken from the client's Auth0
profile unverified; a later step could read them from Auth0's `/userinfo` with the same token.

## Invites with an addressee (issue #117)

`invites.py`. `POST /sessions/{id}/invites` takes an optional body `{to}`: a user id or an email (lowercased; it matches
a user once they have posted that email in `POST /me {email}`). Answer: `{id, token, session_id, expires_at}`; with no
`to` it is the link invite as before. Owner only. 409 if the addressee is already in the session (you included); 422 for a bad email or id.

| Route | Answer |
|---|---|
| `GET /invites` | `{incoming: [{id, session_id, session_title, from: User, created_at, expires_at}], outgoing: [{id, session_id, session_title, to: User\|{email}\|null, created_at, expires_at, status: "pending"\|"accepted"\|"declined"}]}`; revoked and expired ones are left out |
| `POST /invites/{id-or-token}/accept` | `Session`; an id works only for the addressee; the accepter's other sockets also get `invites_changed` |
| `POST /invites/{id}/decline` | 204; the addressee only (their other sockets get `invites_changed` too) |
| `DELETE /invites/{id}` | 204; the creator only (revoke; the link stops working too) |

Server to client (any open socket of that user, no session needed; a local-dev socket says who it is with
`{"type": "auth", "dev_user": "<name>"}`): `{"type": "invite", "invite_id", "session_id"}` when an invite arrives for you,
and `{"type": "invites_changed"}` when one of yours or for you was accepted, declined, revoked, or newly matched by an
email. On both, re-read `GET /invites`. Only a link's SHA-256 is stored, so an old link can't be copied again; the UI
keeps the links it created. The addressee's email is unverified client input (see the shortcut note in `invites.py`).
