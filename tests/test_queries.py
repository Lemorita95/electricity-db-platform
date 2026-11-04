"""
Tests for src/master/db/queries.py — the DB session is faked, so no database.
"""
from datetime import date
from unittest import mock

from master.db import queries
from master.db.models import ProductionResource, GeneratingUnit


def test_upsert_graph_batches_parents_and_children():
    implementation_date = date(2025, 1, 1)
    records = [
        ProductionResource(resource_mrid=f"R{i}", resource_name=f"plant {i}", zone="SE3", business_type="B11",
                           psr_type="B14", implementation_date=implementation_date, source_ts_mrid="1",
                           units=[GeneratingUnit(unit_mrid=f"U{i}", name=f"unit {i}", nominal_p_mw=1.0,
                                                 psr_type="B14", implementation_date=implementation_date)])
        for i in range(2500)
    ]
    batches = [records[i:i + queries.BATCH_SIZE] for i in range(0, len(records), queries.BATCH_SIZE)]
    # what the parent INSERT ... RETURNING id, resource_mrid, implementation_date gives back, per batch
    returned = iter(
        [(n, r.resource_mrid, r.implementation_date) for n, r in enumerate(batch, start=k * queries.BATCH_SIZE)]
        for k, batch in enumerate(batches)
    )

    def fake_exec(stmt):
        result = mock.Mock()
        result.all.return_value = next(returned, [])
        return result

    session = mock.Mock()
    session.exec.side_effect = fake_exec
    queries.upsert_graph(session, ProductionResource, records)

    tables = [call.args[0].table.name for call in session.exec.call_args_list]
    assert tables == ["production_resource"] * 3 + ["generating_unit"] * 3
    assert records[-1].units[0].resource_id == 2499
    session.commit.assert_called_once()
