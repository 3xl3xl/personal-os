# Personal OS — 実接続検証手順

対象: default branch の Finance 実装、ADR-009 / 013–019。
この文書は実行手順であり、実機・実データ検証の完了報告ではない。
結果、口座名、残高、外部ID、認証情報は Git に保存しない。

## 1. 外部ログイン前に行う確認

Mac の Terminal で実行する。既存 checkout を使い、未コミット変更があれば
先に内容を確認する。pull が失敗した場合は強制 reset せず停止する。

```sh
cd ~/personal-os
git status --short
git pull --ff-only
git rev-parse HEAD
uv sync --locked
uv run pytest -q
```

合格: 同期・テストが終了コード0。検証した commit SHA は私的な記録に残す。
テストは合成データであり、実データや macOS の承認操作の合格を意味しない。

### 1.1 既存DBのバックアップと別ファイルへの復元試験

Claude Desktop の Personal OS 接続を停止する。最初の runtime 起動は自動的に
Alembic head まで移行するため、既存DBがあれば起動前に行う。
既定DBは ~/PersonalOS-data/personal_os.db。別パスを使っている場合は
以下の source を実際のパスに変更する。

暗号化可能な私的ストレージを使い、Git の外に保存する。
この操作は既存DBを更新せず、復元試験も別ファイルに行う。

```sh
umask 077
uv run python - <<'PY'
from pathlib import Path
import os
import sqlite3
import uuid
from personal_os.database.backup import create_backup, restore_backup

root = Path.home() / "PersonalOS-data"
source = root / "personal_os.db"
if not source.is_file():
    print("NO EXISTING DB: stop here and confirm whether this is a new setup or a different database path.")
    raise SystemExit(1)
backups = root / "backups"
backups.mkdir(parents=True, exist_ok=True)
os.chmod(backups, 0o700)
snapshot = create_backup(source, backups)
os.chmod(snapshot, 0o600)
destination = root / ("restore-check-" + uuid.uuid4().hex + ".db")
restore_backup(snapshot, destination)
os.chmod(destination, 0o600)
with sqlite3.connect(snapshot) as a, sqlite3.connect(destination) as b:
    assert a.execute("PRAGMA integrity_check").fetchone() == ("ok",)
    assert b.execute("PRAGMA integrity_check").fetchone() == ("ok",)
    assert list(a.iterdump()) == list(b.iterdump())
print("BACKUP AND RESTORE CHECK: PASS")
print("snapshot:", snapshot)
print("restored copy:", destination)
PY
```

合格: PASS、snapshot と restored copy が作成される。
失敗: runtime を起動せず、パス・空き容量・整合性を確認する。
初回でDBが存在しない場合はバックアップ不能が正常。ただし別パスの既存DBを
誤って無視していないと確認した上で、次の合成環境検証へ進む。

### 1.2 合成DBで起動・登録・承認の検証

```sh
mkdir -p ~/PersonalOS-verification
chmod 700 ~/PersonalOS-verification
uv run python -m personal_os.adapters.mcp.runtime_server --database-path ~/PersonalOS-verification/synthetic.db --enable-writes
```

これは stdio サーバーであり、HTTP URLではない。Terminalで待機するだけでは
MCP疎通の合格にならない。Ctrl-Cで終了し、MCPクライアントの手動設定で
同じ module / 引数を指定して接続する。クライアントから起動する場合は
checkout を作業ディレクトリにするか、次の command / args を使用する。

- command: 自分のMacで `command -v uv` が返す絶対パス
- args: `--directory`, checkout の絶対パス, `run`, `python`, `-m`,
  `personal_os.adapters.mcp.runtime_server`, `--database-path`,
  合成DBの絶対パス, `--enable-writes`

合格:
- read: get_net_worth / get_available_capital / get_tax_reserve /
  get_goal_gap / get_required_revenue の5つ
- write: add_account / add_transaction / add_opening_balance / add_metric /
  add_financial_target / add_monthly_target / import_bank_transactions /
  add_capital_bucket / add_cash_linked_allocation / reallocate_capital の10個
- 同じ設定で --enable-writes を外すと read 5つのみ
- 合成DBの add_account をキャンセルすると APPROVAL_REQUIRED、
  同じIDを明示的に承認して再提案できる
- 合成データの単独writeでは承認タイムアウト後に保存されない。
  クライアント側だけのタイムアウトは取消の証拠ではない。
- 応答の error を確認し、通信成功だけで書き込み成功と判定しない

実データの追加前に、承認ダイアログの口座・金額・日時・監査情報が読めることを確認する。

## 2. Mac上のClaude Desktop接続が必要な確認

MCPB は ~/personal-os の checkout を使い、既定の実DBに対して
--enable-writes で起動する。合成DBの上記手動設定とは別物。
先に実DBのバックアップを済ませる。

```sh
npm install -g @anthropic-ai/mcpb
cd ~/personal-os/packaging/mcpb
mcpb validate manifest.json
mcpb pack . ../../personal-os.mcpb
```

Claude Desktop の Extensions から生成した .mcpb をインストールする。
合格: 接続が有効、15ツールが見える、意図したcheckout/DBを使用。
ランチャーは /usr/bin/python3 と既知の場所の uv を使用する。
別のcheckoutパスなら server/launch.py の PERSONAL_OS_REPO を確認・変更して再pack。
通常のアプリコード更新だけならpackし直す必要はない。

切断時: checkout の存在、uv の絶対パス、Python起動、クライアントのログを確認する。
個人値やtokenを含むログをGitや公開issueへ貼らない。

## 3. 既存データを確認してから1口座を照合する

現在のMCPには口座一覧・取引一覧ツールがない。既存IDが不明なら、
実DBを read-only でローカル確認する。存在確認をせず新口座を重複作成しない。

```sh
uv run python - <<'PY'
from pathlib import Path
import sqlite3
path = Path.home() / "PersonalOS-data/personal_os.db"
with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True) as db:
    print("integrity:", db.execute("PRAGMA integrity_check").fetchone())
    print("tables:", db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall())
    for name in ("accounts", "transactions", "financial_metrics", "financial_targets",
                 "monthly_targets", "capital_buckets", "bucket_allocations", "audit_logs"):
        columns = db.execute('PRAGMA table_info("' + name + '")').fetchall()
        if columns:
            print(name, "columns:", [c[1] for c in columns])
            print(name, "rows:", db.execute('SELECT count(*) FROM "' + name + '"').fetchone()[0])
PY
```

これは件数・列名だけの確認。既存ID/内容の照合は確認したschemaに対するSELECTで
私的に行い、UPDATE/INSERTは使わない。

### 3.1 不足分だけMCPから提案する

UUIDは `uv run python -c 'import uuid; print(uuid.uuid4())'` で生成できる。
値は本人の原資料から入力する。日時はtimezone付きISO 8601、
金額は整数のminor units（JPYなら円）。下記は引数一覧であり実データではない。

| ツール | 必須引数 |
| --- | --- |
| add_account | id, name, account_type, currency_code, opened_at, reason |
| add_opening_balance | id, account_id, amount_minor, currency_code, occurred_at, reason |
| add_metric | id, key, display_name, reason |
| add_financial_target | id, metric_key, target_amount_minor, currency_code, effective_from, reason |
| add_monthly_target | id, metric_key, year, month, target_amount_minor, currency_code, effective_from, reason |
| add_transaction | id, account_id, amount_minor, currency_code, occurred_at, reason |

普通預金のローカル口座記録は account_type=CASH。
NORMAL取引には必要に応じて metric_key、memo を付ける。
開始残高には metric_key を付けない。実際の銀行口座を開設・接続する操作ではない。

既存Accountがあれば再利用し、既存OPENING_BALANCEがあれば追加しない。
開始日時以前の残高を開始残高に含める場合、その同じ取引を後から取り込まない。
成功時のentity ID・audit IDと確認日時はGit外に保存する。

### 3.2 読み取りの合否基準

evaluation_time は照合対象のtimezone付き日時。Q5では
business_timezoneを本人の事業基準に合わせ明示する。

| 検証 | 合格基準 |
| --- | --- |
| Q1 get_net_worth(evaluation_time) | 対象時点までのACTIVE開始残高＋符号付き取引の合計と一致。全Account対象なので複数口座があれば全体を照合 |
| Q4 get_goal_gap(metric_key, evaluation_time) | 当該時点で有効な金融目標−Q1と一致。超過時は負値 |
| Q5 get_required_revenue(metric_key, evaluation_time, business_timezone) | 当該月の対象指標実績、目標、signed variance、max(0, variance)が一致 |
| Q2 get_available_capital(evaluation_time) | CASH口座の非保護bucket allocationのみの合計と一致 |
| Q3 get_tax_reserve(evaluation_time) | 名前でなくTAX_RESERVE roleのallocation合計と一致 |

Q4は現在、metric_keyに対応する目標と純資産を比較する。任意KPIのactualを
計算する汎用関数とは扱わない。Q5用の自営売上指標とは区別する。
目標のeffective_fromは有効開始日時で、達成期限ではない。

空DBでは通貨を推測せずNoFinancialDataError。
現在のfinance.pyでは、Accountだけある空の台帳は口座通貨の0を返す
（ADR-018の過去の説明より現在のコードを優先）。
0という結果だけではデータ入力完了を証明しない。
複数通貨を暗黙に合算しない。通貨不一致は換算せず検証停止。

Q2/Q3の合成検証は下記§3.3の承認付きMCP経路を使用する。
既存取引・開始残高を後から割り当てる経路は未実装。既存データの不足が
この制約に該当する場合は「入力経路不足で未検証」と記録し、
直接DB書き込みや新しい取引の二重登録で回避しない。Q3のbucket自体がなければ0でなく
NoFinancialDataErrorになり得る。税額推計の合格とは区別する。

### 3.3 Q2/Q3を合成データだけで検証する

必ず§1.2の新しい合成DBを使い、実DBに接続しない。自動検証:

```sh
uv run pytest -q tests/integration/test_bucket_write.py tests/approval/test_bucket_dialog.py tests/adapters/mcp/test_runtime_stdio.py
```

合格: 終了コード0。以下の手動MCP検証も実データを使わない。
各記号には新しいUUIDを一つずつ割り当て、応答と対応をローカルに記録する。
共通 `reason="synthetic Q2/Q3 verification"`、日時はtimezone付き。

1. `add_account(id=A, name="SYNTHETIC", account_type="CASH", currency_code="JPY", opened_at="2026-10-07T00:00:00Z", reason=...)`。
2. `add_capital_bucket(id=B, account_id=A, name="GENERAL", bucket_role="GENERAL", is_protected=false, created_at="2026-10-07T00:00:00Z", reason=...)`。
3. `add_capital_bucket(id=T, account_id=A, name="arbitrary name", bucket_role="TAX_RESERVE", is_protected=true, created_at="2026-10-07T00:00:00Z", reason=...)`。
4. `add_cash_linked_allocation(id=C, bucket_id=B, amount_minor=100000, currency_code="JPY", created_at="2026-10-07T00:00:00Z", reason=...)`。
   まず取消→APPROVAL_REQUIRED。同じ引数で承認→replayed=false。
   これは新しいNORMAL取引も作る。add_transaction等で同じ金額を追加しない。
5. `evaluation_time="2026-10-07T00:00:00Z"`でQ1=100000、Q2=100000、Q3=0 JPY。
6. Cの全引数（reason含む）をそのまま再送して承認→replayed=true、audit_id同一、数値不変。
   Cのamount_minorだけ変更して承認→INVALID_INPUT、数値不変。
7. `reallocate_capital(id=R, from_bucket_id=B, to_bucket_id=T, amount_minor=30000, currency_code="JPY", created_at="2026-10-08T00:00:00Z", reason=...)`。
   承認後、10/7時点は不変。10/8時点はQ1=100000、Q2=70000、Q3=30000 JPY。
8. 新しいIDでT→B、同額、10/9日時の逆振替を承認する。reasonにRを明記する。
   10/8値は不変、10/9値はQ1=100000、Q2=100000、Q3=0。
9. 合成DBを再接続して同じas-of値を確認する。監査をread-onlyで確認:
   actor/reason/model_or_agent/source/tool、EXPLICITLY_APPROVED、完全なnew_value、
   元の履歴と相殺2行、各操作一つのaudit receiptがあること。

上記のexpected値は合成テスト用であり本人の残高・税額ではない。
複数TAX_RESERVE bucketは名前に依存せず合算される。保護フラグのみでQ2除外。
未割当の既存開始残高をこのツールで埋めるとQ1を二重計上するため禁止。
WRITE_FAILED/通信断では監査とIDを確認し、再試行は元の全引数のみ。
取消後は本人の再提案の意思がある場合だけ再試行する。

## 4. freeeログイン・両MCP接続が必要な検証

ここまでの起動・合成検証・バックアップにはfreee資格情報は不要。
この段階は本人によるfreee公式MCPの認証と、同一AIセッションでの両サーバー接続が必要。
Personal OS側にtokenや銀行passwordを入力しない。

1. freee側は読み取りのみで少数明細を取得する。書き込み系freeeツールを使わない。
2. 実レスポンスからsource, external_office_id, external_account_id,
   external_transaction_id, account_id, amount_minor, currency_code,
   occurred_at, optional descriptionに正規化する。
   APIフィールドやIDを推測しない。sourceの許可値は接続時のschemaで確認する。
3. 口座対応、符号、通貨、タイムゾーン、開始残高との重複を原資料と照合する。
4. import_bank_transactions(transactions=[正規化した明細], reason=確認理由)を呼ぶ。
   最初は1明細。承認画面で本人が対象を選択する。
5. imported / skipped_external_transaction_ids とerrorを確認し、
   Q1とローカルの監査記録を照合する。
6. 同じ外部IDの同じ明細を再送し、重複計上されないことを確認する。
   changed-recordの扱い・中途失敗は先に合成DBで確認する。
7. 両サーバーを再接続し、同じDBの読み取り結果が維持されることを確認する。

合格: 原資料と値・IDの対応が一致、未選択行が保存されない、
再送で残高が増えない、監査情報が揃う、再起動後も保持される。
importは明細ごとのcommit。途中失敗でも前の成功明細は残る。

import入力にはmetric_keyがない。銀行入金だけでQ5の自営売上実績に
分類されたとは扱わない。importした入金をQ5のためにNORMAL取引として
二重登録しない。既存取引の分類・修正経路が必要なら別実装課題として止める。

## 5. 失敗時の対応と完了判定

- APPROVAL_REQUIRED: 承認なし。本人の再提案の意思なしに再試行しない。
- INVALID_INPUT / CURRENCY_MISMATCH: 原資料とschemaを照合する。
  importでは既commit行の有無も確認する。
- WRITE_FAILED / 通信切断: 保存結果不明。ID、外部ID、target versionキー、
  auditをread-onlyで確認するまで再送しない。
- 誤った入力: correction/deleteツールはない。黙って履歴を変更しない。
  targetは正しい後続versionを承認付きで追加できるが、過去versionは残る。
- 復元が必要: 全接続を停止し、現状を別snapshotに保存。
  正しいbackupをまず別ファイルにrestoreして照合する。
  実DBへの復元はその後の個別判断・明示承認で行う。
  Alembic downgradeをデータ保持目的の復旧に使わない。

完了チェックをGit外に記録する:

- [ ] 検証commitとDBパス確認
- [ ] 合成テスト・ツール登録・承認/拒否確認
- [ ] 実DB backupと別ファイルrestore照合
- [ ] Desktop MCPB起動と再接続確認
- [ ] Q1原資料照合
- [ ] Q4/Q5原資料照合（指標分類含む）
- [ ] Q2/Q3照合、または入力経路不足を明記
- [ ] freee少量import・dedup・監査・永続性確認
- [ ] 残る未検証項目と理由を記録

Q2/Q3やQ5の入力経路に未解消の不足があれば、
「Finance全体の実接続検証完了」とは記録しない。
