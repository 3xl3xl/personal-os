"""Step 16: full Finance read path through the real MCP protocol.

temporary SQLite -> Alembic migration -> synthetic facts -> Repository/UoW ->
permission/read contract -> Finance calculations -> MCP adapter -> MCP Client.
"""
from __future__ import annotations

import datetime as dt
import uuid

import pytest
from mcp import Client

from personal_os.adapters.mcp.server import create_server
from personal_os.domain.enums import (
    AccountStatus, AccountType, BucketRole, CapitalBucketStatus,
    EntryType, TransactionKind, TransactionStatus,
)
from personal_os.domain.money import Money
from personal_os.domain.records import (
    AccountRecord, BucketAllocationRecord, CapitalBucketRecord,
    FinancialMetricRecord, FinancialTargetRecord, MonthlyTargetRecord,
    TransactionRecord,
)
from personal_os.repository.unit_of_work import UnitOfWork

UTC=dt.timezone.utc
NOW=dt.datetime(2026,9,22,12,0,tzinfo=UTC)
EVALUATION_TIME="2026-09-22T21:00:00+09:00"


def _seed(sf):
    cash=uuid.uuid4()
    general=uuid.uuid4()
    tax=uuid.uuid4()
    tx=uuid.uuid4()
    with UnitOfWork(sf) as uow:
        uow.accounts.add(AccountRecord(cash,"synthetic cash",AccountType.CASH,"JPY",NOW,AccountStatus.ACTIVE))
        uow.financial_metrics.add(FinancialMetricRecord(uuid.uuid4(),"self_generated_revenue","Synthetic revenue",NOW))
        uow.transactions.add(TransactionRecord(tx,cash,TransactionKind.NORMAL,Money(100_000,"JPY"),NOW,TransactionStatus.ACTIVE,metric_key="self_generated_revenue"))
        uow.capital_buckets.add(CapitalBucketRecord(general,cash,"synthetic general",BucketRole.GENERAL,False,CapitalBucketStatus.ACTIVE,NOW))
        uow.capital_buckets.add(CapitalBucketRecord(tax,cash,"synthetic tax reserve",BucketRole.TAX_RESERVE,True,CapitalBucketStatus.ACTIVE,NOW))
        uow.bucket_allocations.add(BucketAllocationRecord(uuid.uuid4(),general,cash,Money(60_000,"JPY"),EntryType.CASH_LINKED,NOW,originating_transaction_id=tx))
        uow.bucket_allocations.add(BucketAllocationRecord(uuid.uuid4(),tax,cash,Money(40_000,"JPY"),EntryType.CASH_LINKED,NOW,originating_transaction_id=tx))
        uow.financial_targets.add(FinancialTargetRecord(uuid.uuid4(),"self_generated_revenue",Money(150_000,"JPY"),NOW-dt.timedelta(days=1),NOW-dt.timedelta(days=1)))
        uow.monthly_targets.add(MonthlyTargetRecord(uuid.uuid4(),"self_generated_revenue",2026,9,Money(120_000,"JPY"),NOW-dt.timedelta(days=1),NOW-dt.timedelta(days=1)))
        uow.commit()


@pytest.mark.anyio
async def test_all_five_finance_reads_end_to_end_over_mcp(session_factory,temp_db_path):
    _seed(session_factory)
    server=create_server(lambda: UnitOfWork(session_factory))

    async with Client(server,raise_exceptions=True) as client:
        listed=await client.list_tools()
        assert {tool.name for tool in listed.tools}=={
            "get_net_worth","get_available_capital","get_tax_reserve",
            "get_goal_gap","get_required_revenue",
        }

        net=await client.call_tool("get_net_worth",{"evaluation_time":EVALUATION_TIME})
        available=await client.call_tool("get_available_capital",{"evaluation_time":EVALUATION_TIME})
        tax=await client.call_tool("get_tax_reserve",{"evaluation_time":EVALUATION_TIME})
        gap=await client.call_tool("get_goal_gap",{"metric_key":"self_generated_revenue","evaluation_time":EVALUATION_TIME})
        monthly=await client.call_tool("get_required_revenue",{
            "metric_key":"self_generated_revenue",
            "evaluation_time":EVALUATION_TIME,
            "business_timezone":"Asia/Tokyo",
        })

    assert net.is_error is False
    assert net.structured_content["value"]=={"amount_minor":100_000,"currency_code":"JPY"}
    assert available.structured_content["value"]=={"amount_minor":60_000,"currency_code":"JPY"}
    assert tax.structured_content["value"]=={"amount_minor":40_000,"currency_code":"JPY"}
    assert gap.structured_content["value"]=={"amount_minor":50_000,"currency_code":"JPY"}

    m=monthly.structured_content
    assert m["target"]=={"amount_minor":120_000,"currency_code":"JPY"}
    assert m["actual"]=={"amount_minor":100_000,"currency_code":"JPY"}
    assert m["variance"]=={"amount_minor":20_000,"currency_code":"JPY"}
    assert m["required"]=={"amount_minor":20_000,"currency_code":"JPY"}
    assert temp_db_path.exists()


@pytest.mark.anyio
async def test_mcp_e2e_reads_do_not_mutate_stored_facts(session_factory):
    _seed(session_factory)

    def counts():
        with UnitOfWork(session_factory) as uow:
            accounts=uow.accounts.list_all()
            return (
                len(accounts),
                sum(len(uow.transactions.list_by_account(a.id)) for a in accounts),
                sum(len(uow.capital_buckets.list_by_account(a.id)) for a in accounts),
            )

    before=counts()
    server=create_server(lambda: UnitOfWork(session_factory))
    async with Client(server,raise_exceptions=True) as client:
        await client.call_tool("get_net_worth",{"evaluation_time":EVALUATION_TIME})
        await client.call_tool("get_available_capital",{"evaluation_time":EVALUATION_TIME})
        await client.call_tool("get_tax_reserve",{"evaluation_time":EVALUATION_TIME})
        await client.call_tool("get_goal_gap",{"metric_key":"self_generated_revenue","evaluation_time":EVALUATION_TIME})
        await client.call_tool("get_required_revenue",{
            "metric_key":"self_generated_revenue",
            "evaluation_time":EVALUATION_TIME,
            "business_timezone":"Asia/Tokyo",
        })
    assert counts()==before
