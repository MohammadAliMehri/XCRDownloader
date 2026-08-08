"""WSGI entry point for `flask run`."""
from src.web import create_app

app = create_app("downloads")
