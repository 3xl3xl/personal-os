"""Step 14: real Repository/UoW -> permission -> Finance Core read integration."""
from __future__ import annotations

import datetime as dt
import uuid
from zoneinfo import ZoneInfo

from personal_os.domain.enums import (
    AccountStatus, AccountType, BucketRole, CapitalBucketStatus,
    EntryType, TransactionKind, TransactionStatus,
)
from personal_os.domain.money import Money
from personal_os.domain.records import (
    AccountRecord, BucketAllocationRecord, CapitalBucketRecord,
    FinancialMetricRecord, FinancialTargetRecord, MonthlyTargetRecord, TransactionRecord,
)
from personal_os.repository.unit_of_work import UnitOfWork
from personal_os.services import reads

UTC = dt.timezone.utc
NOW = dt.datetime(2026, 9, 22, 12, 0, tzinfo=UTC)


def _seed(sf):
    cash=uuid.uuid4()
    general=uuid.uuid4()
    tax=uuid.uuid4()
    with UnitOfWork(sf) as uow:
        uow.accounts.add(AccountRecord(cash,"synthetic cash",AccountType.CASH,"JPY",NOW,AccountStatus.ACTIVE))
        uow.financial_metrics.add(FinancialMetricRecord(uuid.uuid4(),"self_generated_revenue","Synthetic revenue",NOW))
        uow.transactions.add(TransactionRecord(uuid.uuid4(),cash,TransactionKind.NORMAL,Money(100_000,"JPY"),NOW,TransactionStatus.ACTIVE,metric_key="self_generated_revenue"))
        uow.capital_buckets.add(CapitalBucketRecord(general,cash,"synthetic general",BucketRole.GENERAL,False,CapitalBucketStatus.ACTIVE,NOW))
        uow.capital_buckets.add(CapitalBucketRecord(tax,cash,"renamed reserve",BucketRole.TAX_RESERVE,True,CapitalBucketStatus.ACTIVE,NOW))
        uow.bucket_allocations.add(BucketAllocationRecord(uuid.uuid4(),general,cash,Money(60_000,"JPY"),EntryType.CASH_LINKED,NOW,originating_transaction_id=None))
        uow.bucket_allocations.add(BucketAllocationRecord(uuid.uuid4(),tax,cash,Money(40_000,"JPY"),EntryType.CASH_LINKED,NOW,originating_transaction_id=None))
        uow.financial_targets.add(FinancialTargetRecord(uuid.uuid4(),"self_generated_revenue",Money(150_000,"JPY"),NOW-dt.timedelta(days=1),NOW-dt.timedelta(days=1)))
        uow.monthly_targets.add(MonthlyTargetRecord(uuid.uuid4(),"self_generated_revenue",2026,9,Money(120_000,"JPY"),NOW-dt.timedelta(days=1),NOW-dt.timedelta(days=1)))
        uow.commit()


def test_all_five_reads_use_real_repositories_and_finance_core(session_factory):
    _seed(session_factory)
    assert reads.get_net_worth(lambda: UnitOfWork(session_factory),evaluation_time=NOW).value == Money(100_000,"JPY")
    assert reads.get_available_capital(lambda: UnitOfWork(session_factory),evaluation_time=NOW).value == Money(60_000,"JPY")
    assert reads.get_tax_reserve(lambda: UnitOfWork(session_factory),evaluation_time=NOW).value == Money(40_000,"JPY")
    assert reads.get_goal_gap(lambda: UnitOfWork(session_factory),metric_key="self_generated_revenue",evaluation_time=NOW).value == Money(50_000,"JPY")
    q5=reads.get_required_revenue(lambda: UnitOfWork(session_factory),metric_key="self_generated_revenue",evaluation_time=NOW,business_timezone=ZoneInfo("Asia/Tokyo"))
    assert q5.target == Money(120_000,"JPY")
    assert q5.actual == Money(100_000,"JPY")
    assert q5.variance == Money(20_000,"JPY")
    assert q5.required == Money(20_000,"JPY")


def test_reads_do_not_commit_or_mutate(session_factory):
    _seed(session_factory)
    with UnitOfWork(session_factory) as uow:
        before=(len(uow.accounts.list_all()),sum(len(uow.transactions.list_by_account(a.id)) for a in uow.accounts.list_all()))
    reads.get_net_worth(lambda: UnitOfWork(session_factory),evaluation_time=NOW)
    reads.get_available_capital(lambda: UnitOfWork(session_factory),evaluation_time=NOW)
    reads.get_tax_reserve(lambda: UnitOfWork(session_factory),evaluation_time=NOW)
    with UnitOfWork(session_factory) as uow:
        after=(len(uow.accounts.list_all()),sum(len(uow.transactions.list_by_account(a.id)) for a in uow.accounts.list_all()))
    assert after == before


def test_integration_uses_only_temporary_fixture_database(session_factory, temp_db_path):
    _seed(session_factory)
    result=reads.get_net_worth(lambda: UnitOfWork(session_factory),evaluation_time=NOW)
    assert result.value == Money(100_000,"JPY")
    assert temp_db_path.exists()
