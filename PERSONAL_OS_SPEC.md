PERSONAL OS — MASTER SPECIFICATION
Version: 0.1
Start: 2026-09
Primary Target: 2027-12-31
1. PURPOSE
Personal OSは単なる家計簿、タスク管理、CRM、AIチャットではない。
ユーザー自身の

* Finance
* Business
* Goals
* Work
* Learning
* Creative activity
* Time
* Decisions

を共通データとして保持し、
OBSERVE → UNDERSTAND → PLAN → ACT → REVIEW
のループを継続的に回すPersonal Operating Systemである。
最終的な目的は、AIに人生を決定させることではない。
AIが現在の状態を正確に理解し、目標との差分を計算し、必要な行動を提示・支援することで、ユーザー自身がより良い意思決定をできる状態を作る。
2. CORE PRINCIPLES
2.1 USER OWNS DATA
ユーザーのデータはPersonal OS側に保存する。
Claude、ChatGPT、その他LLMの会話履歴をPrimary Databaseとして使用しない。
LLMは交換可能であること。
2.2 MODEL AGNOSTIC
Claude固有のシステムにしない。
可能な限りMCPなど標準化されたInterfaceを使用し、

* Claude
* ChatGPT
* future AI clients

から同じPersonal Dataへアクセスできる構造にする。
2.3 SINGLE SOURCE OF TRUTH
Goals、Finance、Revenue、Transactionsなどの正式状態はDatabaseをSource of Truthとする。
チャット履歴はSource of Truthにしない。
2.4 FACT ≠ INFERENCE
以下を必ず区別する。
FACT
USER_STATEMENT
OBSERVATION
AI_INFERENCE
AI_RECOMMENDATION
AIの推測をユーザーについての事実として保存してはいけない。
3. AUTONOMY MODEL
Personal OSは以下の順序で動作する。
OBSERVE
↓
UNDERSTAND
↓
PLAN
↓
PROPOSE
↓
USER APPROVAL
↓
ACT
↓
REVIEW
4. PERMISSION POLICY
AUTO
AIが自律実行可能。

* Database read
* Financial calculation
* Forecast
* Analysis
* KPI calculation
* Report generation
* Anomaly detection
* Expense classification suggestion
* Goal progress calculation
* Task suggestion

APPROVAL REQUIRED
必ずUser approvalを取得する。

* Calendar変更
* Task作成・変更（外部サービスの場合）
* Email / DM送信
* External systemへの書き込み
* Important financial record correction
* Goal変更
* Personal policy変更

BLOCKED
AI単独では実行不可。

* Bank transfer
* Investment order
* Financial product purchase
* Contract execution
* Credit transaction
* Loan
* Destructive financial action

Financial execution権限はAnalysis権限から完全に分離する。
5. NORTH STAR
Personal OS must be able to store and track a long-term life/financial target profile. This profile must support, as configurable private runtime data (not fixed values in this specification):
- financial target (net worth / capital target, including a minimum-success level, a target level, and a stretch level)
- income target (self-generated monthly revenue target, employment-dependency target)
- location / life goal (e.g. a relocation or lifestyle target)
- emergency fund target
- travel / relocation fund target (ideally tracked separately from long-term wealth)
- living cost target (maximum monthly living cost)
- work-hour target (maximum weekly working hours)
Revenue must be reproducible rather than the result of a single exceptional month.
Revenue growth must not be achieved solely through unlimited increases in working hours.
Actual target values and life goals belong to the private runtime data store and must never be committed to Git.
6. CURRENT STATE
CURRENT STATE must support, as fields only (no actual values in this specification):
- cash_balance
- investment_balance
- liabilities
- current_employer (name/identifier, generic — not fixed in this specification)
- employment_income
- self_generated_revenue
- rental_income
- living_expenses
- housing_expenses
- working_hours
- social_insurance_status
- business_registration_status (e.g. sole proprietor / filing status)
Actual values belong to the private runtime data store and must never be committed to Git.
7. REVENUE ENGINES
Initial revenue engines:

1. Graphic Design
2. Web / Shopify
3. Jewelry
4. Own Product
5. Music / Creative IP

These allocations are hypotheses, NOT fixed quotas.
Personal OS should learn from actual performance and recommend resource allocation based on evidence.
8. REVENUE TARGET — INITIAL HYPOTHESIS
Personal OS must support a per-revenue-engine monthly target value (e.g. for Graphic Design, Web / Shopify, Jewelry, Own Product, Music), stored as configurable planning data rather than fixed constants in this specification.
The sum of per-engine targets is intended to exceed the overall income target slightly, to provide buffer.
Do not automatically treat failure of one category as failure of the overall plan.
Actual target values belong to the private runtime data store and must never be committed to Git.
9. REVENUE STAGES
Personal OS must support a sequence of self-generated revenue stages, each defined by:
- stage_id
- threshold (self-generated monthly revenue required to reach this stage)
- primary_objective
Example primary objectives, in increasing order of stage: prove ability to generate revenue independently; prove repeatability; prove independence viability; achieve location-independent, diversified, reproducible income.
Actual stage thresholds belong to the private runtime data store and must never be committed to Git.
10. EMPLOYMENT EXIT POLICY
Do NOT recommend leaving the user's current employer based solely on date.
Employment exit eligibility should support configurable conditions:
self_generated_income >= configured_threshold
FOR configured_consecutive_months
AND
emergency_fund >= configured_emergency_target
AND
pipeline >= configured_pipeline_requirement
Actual threshold values belong to the private runtime data store and must never be committed to Git.
When conditions are satisfied:
status = ELIGIBLE_FOR_REVIEW
NOT:
status = QUIT_JOB
Final employment decision belongs to the User.
11. FINANCE MODEL
Never treat these as equivalent:
REVENUE
PROFIT
TAKE_HOME
AVAILABLE_CASH
NET_WORTH
They must be separate fields and calculations.
Basic flow:
Revenue
− Cost of Goods Sold
− Business Expenses
=
Business Profit
↓
Tax Reserve
Social Insurance Reserve
↓
Owner Available Cash
↓
Personal Expenses
↓
Savings / Capital Allocation
12. BUSINESS EXPENSE MODEL
Initial general operating expense assumption:
15% of revenue.
This is a planning assumption only.
Actual expenses must replace assumptions when available.
For service businesses such as Graphic / Web:
0–10%:
LEAN
10–20%:
TARGET RANGE
20–25%:
REVIEW
25–30%:
WARNING
30%+:
ALERT
Do NOT apply this blindly to Jewelry or physical products.
For product businesses track separately:
Revenue
COGS
Gross Profit
Operating Expenses
Operating Profit
Gross Margin
Operating Margin
13. TAX MODEL
Tax calculations must be versioned and assumption-driven.
Never hard-code one universal tax percentage.
Track separately:

* Business revenue
* Business expenses
* Business profit
* Rental income
* Employment income
* Blue Return deduction
* Other applicable deductions
* Income tax reserve
* Resident tax reserve
* Social insurance reserve

Tax Reserve is NOT available spending money.
Support:
estimated_tax
actual_tax
tax_reserve
tax_liability
tax_paid
as separate concepts.
The system must clearly display:
GROSS CASH
minus
UNPAID TAX LIABILITY
minus
UNPAID SOCIAL INSURANCE LIABILITY
=
AVAILABLE CAPITAL
Tax rules change over time.
Every tax rule must include:
jurisdiction
effective_year
source
last_verified_at
assumption_status
14. SOCIAL INSURANCE
While employed by the user's current employer:
Do not double-count employer health insurance or Employees' Pension because salary input is take-home income.
When employer coverage ends:
evaluate:

* National Health Insurance
* voluntary continuation of employer insurance when applicable
* National Pension

Do not assume the cheapest option without calculation.
User jurisdiction must be stored as private runtime data.
The tax engine must support:
- country
- prefecture/state
- municipality
- tax year
Jurisdiction-specific rules must be loaded without requiring the user's actual jurisdiction to be committed to Git.
15. CAPITAL BUCKETS
Personal capital should be conceptually separated into:
OPERATING CASH
EMERGENCY FUND
EUROPE FUND
WEALTH
TAX RESERVE
BUSINESS CASH
Never show all bank balances as freely spendable money.
16. MASTER FINANCIAL TRAJECTORY
Personal OS must support a month-by-month self-generated revenue trajectory: a series of (month, target_revenue) planning values leading toward the overall income target.
These are planning targets, not facts, and must be stored separately from actual revenue.
Actual trajectory values belong to the private runtime data store and must never be committed to Git.
17. BUSINESS KPI MODEL
For every revenue engine track:
Revenue
COGS
Expenses
Profit
Margin
Hours
Effective Revenue Per Hour
Effective Profit Per Hour
Leads
Qualified Leads
Proposals
Deals Won
Conversion Rate
Average Order Value
Repeat Rate
Recurring Revenue
30-Day Pipeline
90-Day Pipeline
18. PIPELINE MODEL
Stages:
LEAD
CONTACTED
MEETING
PROPOSAL
NEGOTIATION
WON
PAID
LOST
Each opportunity should support:
client
revenue_engine
service
estimated_value
probability
stage
expected_close_date
next_action
next_action_date
actual_value
hours_estimated
hours_actual
19. TIME MODEL
Maximum target:
55 hours / week.
Time should be categorized.
Initial categories:
CLIENT_WORK
SALES
PRODUCT
JEWELRY
MUSIC
LEARNING
ADMIN
FINANCE
REST
Personal OS must detect when financial optimization destroys other explicitly important life goals.
Example:
High Graphic revenue must NOT automatically imply that all Music time should be removed.
Each activity may have a different role.
Possible roles:
CASH
GROWTH
LEARNING
CREATIVE
IP
LIFE
20. GOAL MODEL
Goals must support:
id
title
description
target_date
status
priority
metrics
related_domains
parent_goal
created_at
updated_at
source_type
Goals may span multiple modules.
Example:
EUROPE_2027
Finance:
capital requirement
Business:
location-independent revenue
Learning:
language ability
Calendar:
travel timing
21. DATABASE — INITIAL ENTITIES
Implement only what is necessary for v0.1.
Core:
users
goals
goal_metrics
observations
audit_logs
Finance:
accounts
transactions
capital_buckets
monthly_financial_snapshots
tax_reserves
financial_assumptions
Business:
revenue_engines
clients
projects
opportunities
invoices
business_expenses
revenue_records
Time:
time_entries
System:
permissions
automation_rules
data_sources
Do not over-engineer schema before real usage validates the need.
22. AUDIT SYSTEM
Every AI write operation must record:
timestamp
actor
model_or_agent
tool
action
affected_entity
old_value
new_value
reason
approval_status
source
Writes should be reversible where practical.
23. MCP — INITIAL TOOLS
Start READ-heavy.
Finance:
get_financial_state
get_cashflow
get_net_worth
get_available_capital
get_goal_progress
get_tax_reserve
get_expense_ratio
forecast_finances
Business:
get_revenue_summary
get_revenue_engine
get_pipeline
get_required_revenue
get_required_deals
get_effective_hourly_rate
Goals:
get_goals
get_goal
get_goal_gap
Planning:
get_monthly_review
get_weekly_review
get_next_actions
Writes may later include:
add_transaction
add_revenue
add_expense
add_opportunity
update_opportunity
create_goal
update_goal
Write operations must follow permission policy.
24. BANK / CARD INTEGRATION
Architecture must allow future read-only integration.
Target structure:
BANK / CARD / BROKERAGE
↓
AUTHORIZED DATA PROVIDER
↓
NORMALIZATION LAYER
↓
PERSONAL DATABASE
↓
MCP
↓
AI CLIENT
Never require the LLM to know bank passwords.
Initial version may use:
manual input
CSV import
or other controlled read-only sources.
Do not implement payment execution in v0.1.
25. AI REVIEW LOOP
DAILY:
optional lightweight observation.
WEEKLY:
Revenue progress
Pipeline
Spending
Time allocation
Goal risk
Next actions
MONTHLY:
Income statement
Cashflow
Net worth
Tax reserve
Expense ratio
Revenue engine performance
Goal trajectory
Europe Fund
Emergency Fund
Work hours
Plan vs Actual
The system should answer:
WHAT HAPPENED?
WHY?
WHAT DOES IT CHANGE?
WHAT SHOULD BE CONSIDERED NEXT?
26. ADAPTIVE PLANNING
Plans are hypotheses.
Actual data must be allowed to invalidate them.
Example:
If Shopify consistently produces:
higher profit/hour
higher repeat rate
higher conversion rate
than Graphic,
the system may recommend reallocating business-development time.
It must explain:
evidence
expected benefit
tradeoff
confidence
It must NOT silently change major goals.
27. ANTI-OPTIMIZATION POLICY
Personal OS must not optimize only for money.
Never assume:
highest revenue = best life decision
lowest expense = best decision
maximum working hours = best productivity
non-monetized creative activity = useless
User-defined life goals take precedence over simplistic financial optimization.
Music and creative work may retain allocated time even when current revenue is zero.
28. SECURITY
Principle of least privilege.
Secrets must never be committed to git.
Use environment variables or secure secret storage.
Separate:
READ
WRITE
EXTERNAL_ACTION
FINANCIAL_ACTION
permissions.
Financial execution should remain unavailable in initial versions.
Sensitive data should not appear unnecessarily in logs.
29. REPOSITORY STRUCTURE
Suggested starting structure:
personal-os/
README.md
PERSONAL_OS_SPEC.md
CLAUDE.md
core/
database/
mcp/
modules/
finance/
goals/
revenue/
time/
agents/
observer/
analyst/
planner/
reviewer/
policies/
permissions.yaml
privacy.yaml
automation.yaml
migrations/
tests/
docs/
Do not create empty complexity merely to match this tree.
Only create components when needed.
30. EXISTING / FUTURE MODULES
RE:WORD should eventually connect as:
modules/learning/reword
Do NOT rewrite RE:WORD during Personal OS v0.1 unless integration requires a small interface change.
Personal OS should treat RE:WORD as an independent Learning module.
Future modules may include:
Creative
Career
Calendar
Health
Documents
Contacts
but these are OUT OF SCOPE for initial implementation.
31. v0.1 SCOPE
Implement:
CORE
GOALS
FINANCE
REVENUE
AUDIT
Basic MCP interface
Do NOT initially implement:
bank write access
payments
investment execution
full autonomous scheduling
email sending
complex UI
all future modules
32. v0.1 SUCCESS TEST
The system is successful when an authorized AI client can ask:
"What is my current financial state?"
and receive correct database-backed information.
Then:
"How far am I from my 2027 goal?"
Then:
"How much self-generated revenue do I need this month?"
Then:
"How many deals does that imply based on my current average deal size?"
Then:
"What are the biggest risks to the plan right now?"
Every answer must distinguish:
ACTUAL
TARGET
FORECAST
ASSUMPTION
AI INFERENCE

32.1 FINANCE v0.1 — Q1-Q5 CALCULATION DEFINITIONS

The following definitions are normative for Finance v0.1. They define read-time calculations only. Derived values are not persisted as a new source of truth.

Q1 — NET WORTH

Net Worth(currency) = sum of derived Account balances in that currency.

An Account balance is derived from its ACTIVE Transaction ledger entries. CapitalBucket balances must not be added to Net Worth because buckets allocate existing cash and are not independent assets.

Different currencies must never be implicitly combined. FX conversion is outside Finance v0.1.

Q2 — AVAILABLE CAPITAL

Available Capital(currency) = sum of current CASH-account CapitalBucket allocations in that currency where is_protected = false.

Protected buckets are excluded. CapitalBucket is an allocation of existing cash and must not be added to Net Worth.

Q3 — TAX RESERVED

Tax Reserved(currency) = sum of current CapitalBucket allocations in that currency where bucket_role = TAX_RESERVE.

Tax Reserved is determined by bucket_role, never by a user-editable bucket name. Multiple TAX_RESERVE buckets are allowed and are summed.

Tax Reserved means capital currently reserved for tax. It is not estimated_tax, actual_tax, tax_liability, or tax_paid.

Q4 — GOAL GAP

For an evaluation_time, the active FinancialTarget is the version satisfying effective_from <= evaluation_time with the greatest effective_from.

Goal Gap(currency) = Active FinancialTarget(currency) - Derived Actual(currency).

For the Finance v0.1 net-worth goal, Derived Actual is Q1 Net Worth in the same currency.

Goal Gap is signed and is not clamped to zero. A negative value means the target has been exceeded.

Q5 — REQUIRED MONTHLY REVENUE

Q5 answers: "How much self-generated revenue do I still need this month?"

For an evaluation_time and an explicit business timezone, determine the target local calendar year and month. The active MonthlyTarget is the version for metric_key, year, and month satisfying effective_from <= evaluation_time with the greatest effective_from.

Monthly Actual Revenue(currency) = sum of ACTIVE Transaction amounts in that target local calendar month belonging to the selected self-generated revenue metric.

Monthly Revenue Variance(currency) = Active MonthlyTarget(currency) - Monthly Actual Revenue(currency).

Required Monthly Revenue(currency) = max(0, Monthly Revenue Variance(currency)).

Monthly Revenue Variance remains signed so target over-performance is preserved. Required Monthly Revenue is clamped at zero because it represents the remaining amount required in the current target month.

Revenue, Profit, Take-Home, Available Cash, and Net Worth remain distinct concepts. Q5 must use the selected self-generated revenue metric and must not substitute profit, income, take-home pay, or net worth.

The month boundary must be evaluated in the explicitly supplied business timezone. Do not hard-code Japan or any other jurisdiction/timezone.

Different currencies must never be implicitly combined. A target/actual currency mismatch is an error. FX conversion is outside Finance v0.1.

Long-term trajectory calculations such as dividing a long-term target gap by remaining months are not Q5. They belong to a separate planning/forecast calculation and must not be silently substituted for Required Monthly Revenue.

TARGET VERSIONING

FinancialTarget and MonthlyTarget are append-only planning facts. At evaluation_time, select only versions with effective_from <= evaluation_time and choose the greatest effective_from. Future versions must not affect historical or current evaluation.

FACT / DERIVED VALUE BOUNDARY

Accounts, Transactions, CapitalBuckets, BucketAllocations, FinancialTargets, and MonthlyTargets are stored facts/planning records. Net Worth, Available Capital, Tax Reserved, Goal Gap, Monthly Revenue Variance, and Required Monthly Revenue are derived at read time and must not be persisted as replacement facts.

33. CLAUDE CODE OPERATING INSTRUCTIONS
Do not attempt to implement the entire Personal OS in one pass.
Before modifying architecture:

1. Read PERSONAL_OS_SPEC.md.
2. Inspect existing repository.
3. Identify smallest coherent implementation step.
4. Present or record implementation plan.
5. Implement.
6. Add tests.
7. Run tests.
8. Verify migration safety.
9. Update documentation.
10. Record architectural decisions.

Prefer simple, reversible architecture.
Do not introduce a service merely because it may be useful someday.
Never modify financial history silently.
Never convert AI inference into fact.
Never weaken permission boundaries for convenience.
When implementation conflicts with this specification, document the conflict before changing the specification.
34. FIRST IMPLEMENTATION MILESTONE
Build Personal OS v0.1 locally.
Minimum functionality:

1. Database initializes.
2. Current financial state can be seeded.
3. 2027 North Star can be seeded.
4. Monthly revenue targets can be stored.
5. Actual revenue can be recorded separately.
6. Expenses can be recorded.
7. Net worth can be calculated.
8. Tax reserve can be represented separately.
9. Revenue engines can be tracked.
10. MCP exposes read-only financial and goal tools.
11. Audit log records writes.
12. Automated tests verify core calculations.

The first milestone is NOT a dashboard.
The first milestone is:
TRUSTWORTHY DATA + TRUSTWORTHY CALCULATIONS + SAFE AI ACCESS.
35. FIRST COMMAND
After reading this specification:
Do not immediately build everything.
First:

1. Inspect the current repository.
2. Identify any existing RE:WORD architecture that should remain independent.
3. Propose the minimum technical architecture for Personal OS v0.1.
4. Choose the database and migration strategy.
5. Define the first schema.
6. Define the first MCP read tools.
7. Define tests for financial calculations and permission boundaries.
8. Explain major architecture decisions and tradeoffs.

Then begin implementation in small tested milestones.
The system should become useful before it becomes large.
