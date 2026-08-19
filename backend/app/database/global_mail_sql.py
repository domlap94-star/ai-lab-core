"""Canonical PostgreSQL expressions used by the Global Mail projection."""

GMAIL_SOURCE_PREDICATE_SQL = (
    "source_type = 'gmail_message' AND deleted_at IS NULL"
)

GMAIL_DIRECTION_SQL = """
CASE
  WHEN lower(coalesce(raw_payload ->> 'direction', ''))
       IN ('sent', 'outgoing', 'wyslana', 'wysłana')
    OR upper(coalesce((raw_payload -> 'labelIds')::text,
                      (raw_payload -> 'labels')::text, '[]')) LIKE '%"SENT"%'
    THEN 'sent'
  WHEN lower(coalesce(raw_payload ->> 'direction', ''))
       IN ('received', 'incoming', 'odebrana')
    OR upper(coalesce((raw_payload -> 'labelIds')::text,
                      (raw_payload -> 'labels')::text, '[]')) LIKE '%"INBOX"%'
    THEN 'received'
  ELSE 'unknown'
END
""".strip()

GMAIL_DIRECTION_SQL = """
CASE
  WHEN lower(coalesce(raw_payload ->> 'direction', ''))
       IN ('sent', 'outgoing', 'wyslana', 'wysłana')
    OR upper(coalesce((raw_payload -> 'labelIds')::text,
                      (raw_payload -> 'labels')::text, '[]')) LIKE '%"SENT"%'
    THEN 'sent'
  WHEN lower(coalesce(raw_payload ->> 'direction', ''))
       IN ('received', 'incoming', 'odebrana')
    OR upper(coalesce((raw_payload -> 'labelIds')::text,
                      (raw_payload -> 'labels')::text, '[]')) LIKE '%"INBOX"%'
    THEN 'received'
  ELSE 'unknown'
END
""".strip()

GMAIL_READ_STATE_SQL = """
CASE
  WHEN coalesce(raw_payload -> 'labelIds', raw_payload -> 'labels') IS NULL
    THEN NULL
  WHEN json_typeof(coalesce(raw_payload -> 'labelIds',
                            raw_payload -> 'labels')) <> 'array'
    THEN NULL
  WHEN upper(coalesce((raw_payload -> 'labelIds')::text,
                      (raw_payload -> 'labels')::text, '[]'))
       LIKE '%"UNREAD"%'
    THEN 'unread'
  ELSE 'read'
END
""".strip()

GMAIL_MESSAGE_TIME_SQL = """
CASE
  WHEN json_typeof(raw_payload -> 'date') = 'string'
   AND raw_payload ->> 'date' ~
       '^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}[.][0-9]{3}Z$'
    THEN make_timestamp(
      substring(raw_payload ->> 'date', 1, 4)::integer,
      substring(raw_payload ->> 'date', 6, 2)::integer,
      substring(raw_payload ->> 'date', 9, 2)::integer,
      substring(raw_payload ->> 'date', 12, 2)::integer,
      substring(raw_payload ->> 'date', 15, 2)::integer,
      substring(raw_payload ->> 'date', 18, 6)::double precision
    )
  WHEN json_typeof(raw_payload -> 'internalDate') = 'string'
   AND raw_payload ->> 'internalDate' ~ '^[0-9]{13}$'
    THEN timestamp 'epoch'
       + ((raw_payload ->> 'internalDate')::double precision / 1000.0)
         * interval '1 second'
  ELSE created_at AT TIME ZONE 'UTC'
END
""".strip()

GMAIL_SEARCH_DOCUMENT_SQL = """
to_tsvector(
  'simple',
  coalesce(raw_payload ->> 'subject', '') || ' ' ||
  coalesce(raw_payload ->> 'Subject', '') || ' ' ||
  coalesce(raw_payload ->> 'from', '') || ' ' ||
  coalesce(raw_payload ->> 'From', '') || ' ' ||
  coalesce(raw_payload ->> 'to', '') || ' ' ||
  coalesce(raw_payload ->> 'To', '') || ' ' ||
  coalesce(raw_payload ->> 'text', '') || ' ' ||
  coalesce(raw_payload ->> 'textPlain', '') || ' ' ||
  coalesce(raw_payload ->> 'snippet', '') || ' ' ||
  coalesce(extracted_text, '')
)
""".strip()

GMAIL_SEARCH_DOCUMENT_SQL = """
to_tsvector(
  'simple',
  coalesce(raw_payload ->> 'subject', '') || ' ' ||
  coalesce(raw_payload ->> 'Subject', '') || ' ' ||
  coalesce(raw_payload ->> 'from', '') || ' ' ||
  coalesce(raw_payload ->> 'From', '') || ' ' ||
  coalesce(raw_payload ->> 'to', '') || ' ' ||
  coalesce(raw_payload ->> 'To', '') || ' ' ||
  coalesce(raw_payload ->> 'text', '') || ' ' ||
  coalesce(raw_payload ->> 'textPlain', '') || ' ' ||
  coalesce(raw_payload ->> 'snippet', '') || ' ' ||
  coalesce(extracted_text, '')
)
""".strip()
