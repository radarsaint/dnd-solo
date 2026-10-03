# Discord harvest schema

One SQLite database per Discord server at `discord/<server-slug>/<server-slug>.sqlite`.
All IDs are Discord snowflakes stored as TEXT. All timestamps are UTC ISO 8601 TEXT.

```sql
CREATE TABLE servers (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  harvested_at TEXT
);

CREATE TABLE channels (
  id TEXT PRIMARY KEY,
  server_id TEXT NOT NULL REFERENCES servers(id),
  name TEXT NOT NULL,
  type TEXT,
  category TEXT,
  topic TEXT,
  position INTEGER
);

CREATE TABLE threads (
  id TEXT PRIMARY KEY,
  channel_id TEXT NOT NULL REFERENCES channels(id),
  name TEXT,
  created_at TEXT,
  archived INTEGER DEFAULT 0
);

CREATE TABLE users (
  id TEXT PRIMARY KEY,
  username TEXT,
  display_name TEXT,
  is_bot INTEGER DEFAULT 0
);

CREATE TABLE messages (
  id TEXT PRIMARY KEY,
  channel_id TEXT NOT NULL REFERENCES channels(id),
  thread_id TEXT REFERENCES threads(id),
  author_id TEXT REFERENCES users(id),
  created_at TEXT NOT NULL,
  edited_at TEXT,
  content TEXT,
  reply_to_id TEXT
);
CREATE INDEX idx_messages_channel_time ON messages(channel_id, created_at);
CREATE INDEX idx_messages_author ON messages(author_id);

CREATE TABLE attachments (
  id TEXT PRIMARY KEY,
  message_id TEXT NOT NULL REFERENCES messages(id),
  filename TEXT,
  url TEXT,
  content_type TEXT,
  size INTEGER,
  sha256 TEXT,
  local_path TEXT  -- repo-relative, e.g. discord/<server-slug>/attachments/<channel_id>/<attachment_id>-<filename>
);

CREATE TABLE reactions (
  message_id TEXT NOT NULL REFERENCES messages(id),
  emoji TEXT NOT NULL,
  count INTEGER NOT NULL,
  PRIMARY KEY (message_id, emoji)
);

-- Full-text search over message content
CREATE VIRTUAL TABLE messages_fts USING fts5(
  content, content='messages', content_rowid='rowid'
);
CREATE TRIGGER messages_ai AFTER INSERT ON messages BEGIN
  INSERT INTO messages_fts(rowid, content) VALUES (new.rowid, new.content);
END;
CREATE TRIGGER messages_ad AFTER DELETE ON messages BEGIN
  INSERT INTO messages_fts(messages_fts, rowid, content) VALUES ('delete', old.rowid, old.content);
END;
CREATE TRIGGER messages_au AFTER UPDATE ON messages BEGIN
  INSERT INTO messages_fts(messages_fts, rowid, content) VALUES ('delete', old.rowid, old.content);
  INSERT INTO messages_fts(rowid, content) VALUES (new.rowid, new.content);
END;
```

Attachment files are downloaded and committed under `discord/<server-slug>/attachments/<channel_id>/<attachment_id>-<filename>`, with `local_path` and `sha256` filled in. Discord CDN URLs expire, so the stored file is the real record and `url` is only the original source. Run `VACUUM` before committing.

## Example search

```sql
SELECT m.created_at, u.display_name, c.name AS channel, m.content
FROM messages_fts f
JOIN messages m ON m.rowid = f.rowid
JOIN channels c ON c.id = m.channel_id
LEFT JOIN users u ON u.id = m.author_id
WHERE messages_fts MATCH 'NEAR(lich phylactery, 5)'
ORDER BY m.created_at;
```
