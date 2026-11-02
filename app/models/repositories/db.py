"""Neo4j connection handling. Only repository classes should import this module."""
from datetime import datetime
from importlib import resources

import click
from flask import current_app
from neo4j import GraphDatabase, NotificationDisabledClassification

from app.models.enums import Allergen, DietaryLabel, EventCategory

# Node label -> enum whose values become the fixed value nodes (created by init_db).
VALUE_NODES = {"EventCategory": EventCategory, "Allergen": Allergen, "DietaryLabel": DietaryLabel}


def get_driver():
    return current_app.extensions["neo4j"]


def verify_connection() -> None:
    """Fail fast (ServiceUnavailable or AuthError) if Neo4j is not reachable, without the driver's retries."""
    get_driver().verify_connectivity()


def query(cypher: str, **params) -> list:
    """Run one statement in its own transaction and return all records."""
    records, _, _ = get_driver().execute_query(cypher, parameters_=params,
                                               database_=current_app.config["NEO4J_DATABASE"])
    return records


def write(work):
    """Run `work(tx)` in one write transaction, for changes that need several statements.
    The driver may retry `work` on a transient error, so it must be safe to run again."""
    with get_driver().session(database=current_app.config["NEO4J_DATABASE"]) as session:
        return session.execute_write(work)


def next_ids(tx, label: str, n: int = 1) -> list[int]:
    """Reserve `n` new integer ids for nodes with this label."""
    if n == 0:
        return []
    last = tx.run("MERGE (c:Counter {name: $name}) SET c.value = coalesce(c.value, 0) + $n RETURN c.value AS last",
                  name=label, n=n).single()["last"]
    return list(range(last - n + 1, last + 1))


def to_db_time(value):
    """Datetimes are stored to the second, as before in SQLite."""
    return value.replace(microsecond=0) if isinstance(value, datetime) else value


def to_native(value):
    """Convert a Neo4j date/time back to a Python date or datetime."""
    return value.to_native() if value is not None else None


def init_db() -> None:
    """Delete all nodes, then create the constraints and the fixed value nodes."""
    query("MATCH (n) DETACH DELETE n")
    schema = resources.files(__package__).joinpath("schema.cypher").read_text(encoding="utf-8")
    statements = "\n".join(line for line in schema.splitlines() if not line.strip().startswith("//"))
    for statement in statements.split(";"):
        if statement.strip():
            query(statement)
    for label, enum in VALUE_NODES.items():
        query(f"UNWIND $values AS value MERGE (:{label} {{value: value}})", values=[v.value for v in enum])


@click.command("init-db")
def init_db_command() -> None:
    """Clear the existing data and create the constraints."""
    init_db()
    click.echo("Initialised the database.")


def close_driver(app) -> None:
    driver = app.extensions.pop("neo4j", None)
    if driver is not None:
        driver.close()


def init_app(app) -> None:
    # The driver connects lazily, on the first query. "Unrecognized" notifications are switched off: on a fresh
    # database they warn about relationship types (e.g. HAS_CART) that simply have not been created yet.
    app.extensions["neo4j"] = GraphDatabase.driver(
        app.config["NEO4J_URI"], auth=(app.config["NEO4J_USER"], app.config["NEO4J_PASSWORD"]),
        notifications_disabled_classifications=[NotificationDisabledClassification.UNRECOGNIZED])
    app.cli.add_command(init_db_command)
