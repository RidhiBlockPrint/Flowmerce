"""ASGI entry point: `uvicorn flowmerce.modules.seo.main:app`. run.py uses this too."""
from .app import startup

app = startup()
