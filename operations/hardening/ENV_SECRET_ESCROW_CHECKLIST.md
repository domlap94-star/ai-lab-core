# Protected environment-secret escrow checklist

The production checkpoint intentionally excludes `.env` values. Recovering
the stack therefore requires a separate manual escrow kept outside Git, the
repository, release artifacts and ordinary backup manifests.

## Required variable-name inventory

Record the current values for the variable names listed by the checkpoint's
`configuration/required-env-names.txt`. At minimum the categories cover:

- PostgreSQL database, user and password;
- backend signing/secret key and administrator bootstrap credentials;
- n8n ingestion key and n8n credential-encryption key;
- production CORS/API/release configuration;
- Vision supervisor bridge derivation input and automation flag;
- any configured Google/Gmail source credentials referenced by n8n.

Do not copy values into this document, the backup manifest, command-line
arguments, logs, screenshots or issue trackers.

## Storage and access

1. Store the escrow in an approved encrypted vault or encrypted removable
   medium outside the active host and repository.
2. Restrict access to the designated operator and recovery administrator;
   record ownership and recovery contacts separately.
3. Keep the decryption/recovery key outside the same physical or logical
   location as the escrow payload.
4. Record the source release, source HEAD, creation date and variable names,
   but never secret values, in the operational inventory.
5. Verify access through a controlled read test without printing values.
6. Review the escrow after credential rotation and at each disaster-recovery
   drill. Never overwrite the only known-good copy before validation.

This is a manual operational requirement. CHUNK 17 does not copy `.env`, rotate
credentials or install an automated secret-export task.
