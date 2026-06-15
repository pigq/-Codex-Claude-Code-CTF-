CREATE TABLE IF NOT EXISTS intents (
  id TEXT PRIMARY KEY,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  source_id TEXT NOT NULL,
  source_name TEXT NOT NULL,
  source_version TEXT,
  intent_type TEXT NOT NULL,
  intent_type_label TEXT NOT NULL,
  name TEXT NOT NULL,
  contact TEXT NOT NULL,
  message TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'new',
  client_key TEXT NOT NULL,
  user_agent TEXT
);

CREATE INDEX IF NOT EXISTS idx_intents_created_at ON intents(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_intents_source_id ON intents(source_id);
CREATE INDEX IF NOT EXISTS idx_intents_status ON intents(status);
CREATE INDEX IF NOT EXISTS idx_intents_client_key_created_at ON intents(client_key, created_at);
