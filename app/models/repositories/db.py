"""SQLite connection handling. Only repository classes should import this module."""
import sqlite3
from importlib import resources

import click
from flask import current_app, g


def get_db() -> sqlite3.Connection:
    """Return the connection for the current request, opening it on first use."""
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(exception=None) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db() -> None:
    """Drop and recreate all tables."""
    schema = resources.files(__package__).joinpath("schema.sql").read_text(encoding="utf-8")
    get_db().executescript(schema)


@click.command("init-db")
def init_db_command() -> None:
    """Clear the existing data and create new tables."""
    init_db()
    click.echo("Initialised the database.")


def init_app(app) -> None:
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)
