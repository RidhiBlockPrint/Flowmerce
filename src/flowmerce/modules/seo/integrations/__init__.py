"""Connectors to outside services. Each one reads its credentials from the environment (see .env.example)
and reports health through integrations.status so the dashboard can show last sync and errors.
To connect a new data source, add a module here, call mark_attempt / mark_success / mark_error around
each sync, and expose it from services/sync.py."""
