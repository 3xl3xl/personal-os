from __future__ import annotations
import ast
import datetime as dt
import uuid
from pathlib import Path
from personal_os.domain.enums import AccountStatus, AccountType
from personal_os.domain.money import Money
from personal_os.domain.read_contracts import MonthlyRevenueReadValue, ValueKind
from personal_os.domain.records import AccountRecord
from personal_os.services.read_contract import FinanceReadContract, FinanceReadDependencies

UTC = dt.timezone.utc
NOW = dt.datetime(2026, 9, 22, 12, 0, tzinfo=UTC)

class Accounts:
    def list_all(self):
        return [AccountRecord(id=uuid.uuid4(), name="synthetic", account_type=AccountType.CASH, status=AccountStatus.ACTIVE, currency_code="JPY", opened_at=NOW)]
class Empty:
    def list_by_account(self, _): return []
    def list_by_bucket(self, _): return []
    def list_by_metric(self, _): return []
    def list_by_metric_year_month(self, *_): return []

def _contract():
    empty=Empty()
    return FinanceReadContract(FinanceReadDependencies(Accounts(), empty, empty, empty, empty, empty))

def test_net_worth_contract_is_derived_and_preserves_as_of():
    r=_contract().get_net_worth(evaluation_time=NOW)
    assert r.metric_key=="net_worth" and r.value==Money(0,"JPY") and r.as_of==NOW
    assert r.kind is ValueKind.DERIVED

def test_contract_exposes_exactly_five_initial_read_operations():
    public={n for n in dir(FinanceReadContract) if n.startswith("get_") and callable(getattr(FinanceReadContract,n))}
    assert public=={"get_net_worth","get_available_capital","get_tax_reserve","get_goal_gap","get_required_revenue"}

def test_monthly_result_tags_are_explicit():
    r=MonthlyRevenueReadValue("revenue",2026,9,Money(10,"JPY"),Money(4,"JPY"),Money(6,"JPY"),Money(6,"JPY"),NOW)
    assert (r.target_kind,r.actual_kind,r.variance_kind,r.required_kind)==(ValueKind.TARGET,ValueKind.ACTUAL,ValueKind.DERIVED,ValueKind.DERIVED)

def test_contract_module_has_no_adapter_or_persistence_imports():
    tree=ast.parse(Path("src/personal_os/services/read_contract.py").read_text())
    imports=[]
    for node in ast.walk(tree):
        if isinstance(node,ast.Import): imports.extend(x.name for x in node.names)
        elif isinstance(node,ast.ImportFrom) and node.module: imports.append(node.module)
    forbidden=("sqlalchemy","sqlite3","personal_os.database","personal_os.adapters","mcp")
    assert not any(x.startswith(forbidden) for x in imports)

def test_contract_defines_no_write_operations():
    assert not any(n.startswith(("add_","create_","update_","delete_","execute_")) for n in dir(FinanceReadContract))
