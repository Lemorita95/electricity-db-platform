"""Compares the tables a migration's upgrade() creates with the SQLModel tables, without a database."""
import importlib.util
from pathlib import Path
from unittest import mock

import sqlalchemy as sa

VERSIONS = Path(__file__).resolve().parents[1] / "migrations" / "versions"


def created_tables(migration_file: str) -> dict[str, sa.Table]:
    spec = importlib.util.spec_from_file_location(migration_file.removesuffix(".py"), VERSIONS / migration_file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.op = mock.MagicMock()
    module.upgrade()

    metadata = sa.MetaData()
    return {c.args[0]: sa.Table(c.args[0], metadata, *c.args[1:]) for c in module.op.create_table.call_args_list}


def describe(table: sa.Table):
    base_type = lambda t: t.impl if isinstance(t, sa.types.TypeDecorator) else t  # sqlmodel's AutoString wraps String
    return (
        [(c.name, base_type(c.type).python_type, c.nullable) for c in table.columns],
        {(c.name, tuple(c.columns.keys())) for c in table.constraints if isinstance(c, sa.UniqueConstraint)},
        {(fk.parent.name, fk.target_fullname) for fk in table.foreign_keys},
    )


def assert_migration_creates(migration_file: str, *models):
    tables = created_tables(migration_file)
    assert set(tables) == {m.__tablename__ for m in models}
    for model in models:
        assert describe(tables[model.__tablename__]) == describe(model.__table__)
