# Decision 4: API alignment explained

Status: 未採択。2026-10-07、Decision 1/2/3/5/6 採択後の説明。
新しい API の実装や削除はこの文書では行わない。
現行挙動の baseline: `c8bd25a56e9d5221abaf40b2c98102bd60c217ae`。

Decision 4 は「Go/Python の全部を同じ形にする」判断ではない。
独立した六つの選択を一括の KEEP/REMOVE 表にしてしまったため、
契約を成立させる変更と、単に入口を少なくする整理が混ざっていた。

## 1. Snapshot の作成と path 保存

通常の使い方は migration/fixture → `db.snapshot()` → `snapshot.fork()`。
成功すると準備用 DB は閉じ、子の変更は Snapshot に書き戻されない。

現行の Python `db.snapshot(path)` と Go `SnapshotOptions.Destination` は、
その呼出元 DB の固定した状態を外部 directory に残す追加機能。
子の現在状態を保存したければ、その子で別の snapshot を作る。
既存 destination は上書きしない。

提案は path 指定の保存を通常 Snapshot から除くこと。
`rollback`、timeout/context や Snapshot/Fork 自体の廃止ではない。
保存先の排除は product preference であり、現在の保存内容が mutable DB
を直接再開するから危険、という説明は誤り。

失うのはこの API による新しい reusable external artifact の作成。
ログの保存先指定は別責任であり廃止対象ではない。
診断/export/cache の代替 API を同時に追加する根拠はまだない。

## 2. 外部状態を読む入口

`Snapshot.open(path)` は維持可能な explicit import boundary。
現行は path を参照する handle で、full content/inventory 検証を行うが
actual guest compatibility は Fork の host 起動で確認する。
Owned contract では open 成功前に compatibility も含め完全検証し、
独立した内部 backing を取得する。以後 Fork は元 path を信頼し直さない。

入力は mariamem の対応 guest/format の prepared artifact。
SQL dump reader や通常の MariaDB datadir import ではない。
writer を除くと public producer がなくなることは具体的な downside。
既存の compatible artifact を入力として使う advanced 例外で、永続 cache
を core にする根拠ではない。guest 更新で compatibility は失われ得る。
Go にも open を増やす必要は、言語 parity だけからは生じない。

## 3. 重複した作成入口

Python には現在、明示的な `Snapshot.open(path)` / `s.fork()` に加えて
`Snapshot(path)` と `Database/start(snapshot=path or handle)` がある。

原提案は import を open、子の作成を fork に集約すること。
ただし、重複しているだけで unsafe ではない。
現行の `Database(snapshot=s)` は s の path を再度開くため、closed persistent
handle から再起動でき、同じ owned resource を使用する契約になっていない。

必要なのはその挙動の修正。入口そのものの削除は選択肢であって、
OwnedPrepared を成立させるための必須条件ではない。
残すなら live handle の所有/lifetime を守る `s.fork()` と同じ動作へ揃える。
path 入力を残す場合は、明示 import と同じ完全検証/独立取得を必ず通す。
SDK 内部の descriptor handoff は public 入口の有無とは別。

## 4. Snapshot の path / manifest / validate

現行 Go `Path()`、Python `path` / `manifest` / `validate()` は backing の
directory/format/hash の情報を公開している。
通常のテストは初期状態の lifetime と独立した子を使うだけで、これらを
理解する必要はない。INTERNALIZE は通常の契約から storage details を外す提案。

Owned backing は普通の path が生存する resource とは限らない。
外部 import の入力 path を、現在 Fork が読む backing path と呼んではならない。
新契約では validate を毎 Fork/hash 操作として使う必要もない。

ただし read-only diagnostics/provenance metadata を公開すること自体は
ownership と両立する。消すべきなのは mutable path を resource identity にする
依存であり、全 metadata を隠すことが correctness 上必須ではない。
caller-visible manifest が必要なら、内部の trusted manifest を変更できない
値として公開できる。具体需要と公開内容は別途決める。

## 5. pytest の baseline scope と child scope

現行 `mariamem_snapshot` は worker ごとの session baseline、
`mariamem_fork` は function child。準備を共有しても個別 test の mutation は共有しない。

現行 `mariamem_class_fork` は一つの可変 DB を class 全体で使う。
A が INSERT/CREATE TABLE したら、B にも見える。method 間で reset しない。
`mariamem_class_connection_info` の wait は disconnect 待ちで、data reset ではない。

原提案は mutable class-sharing の二 fixture を builtin から除くこと。
失うのは複数 method にまたがる stateful scenario の convenience。
一つの test 内の複数 step は通常の独立 DB で実現できる。
意図的に共有する custom fixture を pytest で書く能力は失われない。

「class ごとに migration を一度行い、各 method は独立」が目的なら、
class-scoped Snapshot と function-scoped Fork を組み合わせる。
class baseline 作成は、その class の setup DB を所有する必要がある。
session の mariamem_server を class ごとに何度も snapshot してはいけない：
最初の成功でその DB は閉じる。

`prepare_and_disconnect` は利用者の migration/fixture と接続終了の関数。

```python
import mariamem
import pytest

@pytest.fixture(scope="class")
def mariamem_snapshot(mariamem_options):
    with mariamem.start(**mariamem_options) as setup:
        prepare_and_disconnect(setup)
        setup.wait_disconnected()
        with setup.snapshot() as baseline:
            yield baseline
# Builtin mariamem_fork remains function-scoped.
```

session/class/module scope の baseline は、その scope 内・worker 内で共有する。
xdist worker 間で自動的に一つの Snapshot が共有されるわけではない。

## 6. mariamem_server の位置付け

名前はそのまま、baseline を作るための setup builder として説明を揃える案。
現行は session-scoped mutable DB。直接普通の test に渡せば mutation が共有され、
依存 Snapshot が成功した後は閉じている。この二つを usage で明記する。
function-scoped child を削除する案ではない。
fixture 名の rename や利用者の custom scope の禁止は提案していない。

## 分けて決めるべきこと

- path 指定 write の廃止：既に示された product preference の具体化。
- explicit read/import の ownership：採択済み integrity contract の適用。
- constructor aliases の削除：安全に ALIGN して残す案と比較できる。
- metadata の公開範囲：owned resource の identity と diagnostic value を分ける。
- mutable class fixture の存廃：baseline の準備 scope と独立した子の scope を分ける。
- setup fixture：残して準備用であることを明示する。

この説明は各選択の理解を助けるためのもの。原提案全体を採択済みとは扱わない。
