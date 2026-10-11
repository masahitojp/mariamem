# MariaDB guestパッチ管理 — 共通＋系列固有

状態: **2026-10-12 maintainer承認済みの管理方針**。
方式B「共通のportability差分＋必要最小限の系列固有hunk」を採用する。
この文書を、今後のパッチ棚卸し・guest更新時の判断基準とする。
管理機構の実装は未着手。各実験は現在、1本の`guest/experimental.patch`を保持している。
guestの製品採用、複数系列のサポート、Release qualificationはそれぞれの検証結果で判断する。

## 比較した方式と採用理由

| 方式 | 構成 | 判断 |
| --- | --- | --- |
| A: 単一パッチ | 全系列に同じdiffを適用 | 共通部分には適するが、異なる上流contextや制御フローを1つに押し込まない |
| **B: 共通＋系列固有** | 共通差分を1か所に置き、異なるhunkだけvariantとして持つ | **採用**。重複を抑え、適用範囲と意味論の違いを明示できる |
| C: 完全に独立 | 各系列にパッチ一式を置く | 現状では不採用。同じ修正の二重保守と伝播漏れが増える |

12.3.3と13.2.0の比較では、18ファイル分の移植のうち17ファイル分を共通化できた。
残る`storage/innobase/log/log0log.cc`のredo mapping保護だけ、適用hunkが異なる。
15ファイル分は元のdiff bytesまで一致し、`configure.cmake`は行位置、
`mysys/my_virtual_mem.c`はコメントに違いがあった。
このため「共通17ファイル」は、元の17個のdiffがすべてbyte一致するという意味ではない。

共通17ファイル＋redo variantをGNU patchの`--fuzz=0`で適用する試験は、両版とも成功した。
各版の元の一体型パッチによる出力と、版名コメントを正規化した後の全18ファイルが一致した。
これはソース適用・出力比較の証拠であり、新たなビルドや実行qualificationではない。

## 管理する単位と選択ルール

構成は、共通portabilityパッチ、必要なredo hunkのvariant、入力と適用順序を結ぶ
小さなmanifestとする。ファイル名やディレクトリ構成の詳細は実装時に決める。

| 対象ソース | 適用するportability差分 |
| --- | --- |
| 固定したMariaDB 12.3.3の入力 | 共通パッチ → 12.3.3向けredo variant |
| 固定したMariaDB 13.2.0の入力 | 共通パッチ → 13.2.0向けredo variant |

「系列固有」は説明上の呼び名であり、major番号だけで自動選択しない。
実際の選択キーは**正確なpatch releaseとsource archiveのdigest**とする。
manifestは対象入力、順序付きパッチ一覧、各パッチのdigestを記録し、未登録入力や
hash不一致は拒否する。Git入力は`source_commit`と`tag_object_sha`を区別し、
公式tarballしか確認できない入力に架空のGit identityを与えない。

次のpatch releaseで適用条件・意味論に差がなければ同じvariantを再利用する。
variantは実際に異なるhunkだけ追加する。fuzzやignore-whitespaceで失敗を隠して
共用範囲を広げない。共通パッチの変更は、manifestで参照する各入力について確認する。
未使用platformの差分も自動的に必要と見なさず、棚卸しで用途を確認する。

責務は次の単位で管理する。

| 層 | 管理対象 |
| --- | --- |
| MariaDB portability | この方針の共通パッチ＋適用hunk variant |
| mariamem guest機能 | canonical `guest/source.patch`、wrapper、init/auth hooks |
| Wasm→Go変換 | converter pinと、そのconverterに必要なパッチseries |
| Host/Wire/SDK | guestとは別の実装・互換性検証 |

12.3.3／13.2.0の実験では、canonical `guest/source.patch`と実験時のconverterの7パッチは
変更不要だった。converterを本家へ移すTrack Aは独立の候補であり、その組合せの
実行成功をこの調査結果から推定しない。
実験中のguest差分は既存の`guest/experimental.patch`境界とprovenanceの記録を維持し、
新しい管理方式を理由にReleaseの実験差分拒否を弱めない。

## 棚卸しの初期一覧

この一覧は固定した12.3.3／13.2.0実験の観測を起点とする。
各行について、必要性、上流反映状況、適用条件、検証状態を更新していく。

| ファイル | 目的 | 現在の分類 | 更新時に確認する点 |
| --- | --- | --- | --- |
| `CMakeLists.txt` | embedded/WASIX target構成 | 共通 | client/tests/packageの除外とwasm target追加 |
| `cmake/os/Emscripten.cmake` | lite4由来の別platform profile | 共通候補・WASIXでは未使用 | production構成に残す必要性 |
| `cmake/os/WASIX.cmake` | threads、simulated AIO、host専用機能の無効化 | 共通 | feature optionとthread前提 |
| `cmake/pcre.cmake` | 子buildへのtoolchain伝播 | 共通 | cross-build設定と上流への還元可能性 |
| `configure.cmake` | fork/dlopen/fcntl等の誤検出回避 | 共通 | probeと行contextの変更 |
| `include/my_global.h` | lock定数・Dl_info競合の回避 | 共通 | WASIX libcのheader契約 |
| `include/my_stacktrace.h` | crash resolverのfork無効化 | 共通 | 未対応syscallの到達経路 |
| `libmysqld/libmysql.c` | getloginの未実装回避 | 共通 | libc capability |
| `mysys/CMakeLists.txt` | host用CRC assemblyの除外 | 共通 | wasm targetの選択条件 |
| `mysys/my_largepage.c` | aligned allocation＋zero-fill | 共通・VM契約 | 予約、初期化、失敗時の処理 |
| `mysys/my_lock.c` | file lockのno-op化 | 共通・所有権前提 | 独立DB backingの前提 |
| `mysys/my_timezone.cc` | tzname不在時のUTC | 共通 | timezoneの意味論 |
| `mysys/my_virtual_mem.c` | NULL commit、accounting、release、protect適応 | 共通・VM契約 | decommit/recommit、zeroing、protection、accounting |
| `sql/sql_plugin.cc` | loader無効経路の型整合 | 共通 | 上流修正で削除できるか |
| `storage/innobase/fil/fil0fil.cc` | absolute datadirの二重prefix回避 | 共通 | recovery/pathの意味論 |
| `storage/innobase/log/log0log.cc` | redo mappingのmprotect guard | **系列固有hunk** | mapping成功後の到達範囲と制御フロー |
| `storage/innobase/os/os0file.cc` | WASIX file lockのno-op化 | 共通・所有権前提 | 同一datadirの複数process共有を前提にしていないか |
| `storage/maria/ma_loghandler.c` | directory fsyncのEISDIR回避 | 共通 | guest filesystemとdurability契約 |

`my_virtual_mem.c`のNULL commit／protect適応は12.3だけの修正ではない。
比較した12.3.3／13.2.0の上流ファイルはbyte-identicalで、両方に同じ適応が必要だった。
番号から推測せず、実際のAPI契約に紐付けて分類する。

redoのmprotectは、12.3では`HAVE_PMEM && is_pmem`内、13.2では成功したlog mapping全体へ
移動している。移植の目的が同じでも適用範囲は拡大しており、PMEM無効という設定だけで
read-only／backup／archive等の全経路を未使用と判断しない。
decommitのaccountingのみの実装、nonnull recommitの非zero-fill、protectとfile lockの
no-opという制約は、パッチ共通化によって解消したとは扱わない。

## 更新時に残す棚卸し記録

| 項目 | 記録する内容 |
| --- | --- |
| 対象入力 | release名、source archive/hash、確認済みGit identity、recipe・dependency pins |
| 修正の根拠 | 問題、発生条件、守る契約、由来・上流commit/issue |
| 分類 | 共通／variant／canonical overlay／converter／host、分類理由 |
| 適用条件 | 対象source digest、ordered patch/hash、変更箇所と失敗条件 |
| 検証 | source apply・出力比較、実行した境界、結果・証拠、未検証経路 |
| 継続判断 | 維持／上流化／削除／再検討、次に確認する具体的条件 |

パッチ数・変更ファイル数・修正の意味論を別々に数える。
17＋1ファイルへの分割を「18本のパッチ」と表現せず、variant数の増加だけで
意味論上の変更が増えたとも判断しない。
上流に同等修正が入った場合は、削除後の適用・実行検証とともに差分を縮小する。

まず正確な入力に対する適用と出力比較を行い、変更した契約に応じて実行検証へ進む。
guest更新時のSQL/protocol/auth/sessions、Snapshot/Fork/isolation、両OS・consumer互換性、
thread/trap/race censusと独立再生成の必要性は既存の開発・Release境界に従う。
共通化の適用成功を、これらの実行検証やRelease資格の代わりにしない。

## 調査証拠と現在の実装状態

- [12.3.3 feasibility報告](https://github.com/masahitojp/mariamem/blob/5f14221463b6400e72e72a115bd1cc1a3acee88d/docs/reviews/v05-stable-guest-feasibility.md)
  は実build、SQL、所有権・lifecycle検証と残るVM契約の限界を記録する。
- [13.2.0 feasibility／方式比較](https://github.com/masahitojp/mariamem/blob/06ad7abf8c38248ceff0b0105af02c010f51f4fc/docs/reviews/v05-mariadb-132-feasibility.md)
  は18ファイルの差分、redoの制御フロー、A/B/C比較を記録する。
- [分割適用の証拠](https://github.com/masahitojp/mariamem/blob/06ad7abf8c38248ceff0b0105af02c010f51f4fc/docs/reviews/v05-mariadb-132-feasibility-evidence/split-layout-result.json)
  と[再現script](https://github.com/masahitojp/mariamem/blob/06ad7abf8c38248ceff0b0105af02c010f51f4fc/docs/reviews/v05-mariadb-132-feasibility-evidence/patch-layout-reproduce.py)
  は共通17ファイル＋2つのredo variantのsource-only検証を保存する。
- [handshake互換性報告](https://github.com/masahitojp/mariamem/blob/5c29ec91667136f827fbf9bd9009e5e87a3f70cf/docs/reviews/handshake-version-compatibility.md)
  はSQL値、Wire値、ORM判定を区別する。現行13.1.0での検証を12.3.3／13.2.0へ流用しない。

調査報告は当時の入力・結果を保存する。この文書は承認された管理方針と棚卸し基準を所有する。
今後の実装・棚卸し結果では、対象入力と証拠を追加し、実装済み／未実装を更新する。
