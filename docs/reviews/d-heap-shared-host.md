# D heap Snapshot＋Python共有host：実装記録

2026-10-16。`experiment/d-heap-shared-host`。**実装・検証中。採用判断はまだ求めない。**
Human承認済みの[設計と範囲変更](d-heap-productization-design.md)を実装している。
main統合・リリース準備は行わない。

## 対象と差分

基点はmain `a8137b8b444f86068d3128a291e3a848adfdfd56`。
過去のD/Python試作は設計上の根拠として参照し、実験overlayを製品コードへ
一括取り込みしていない。guest／converter／その13パッチは変更しない。

- MemFSの所有元を固定preimage検査付きで手書き境界へ移し、16 KiB blockを
  親・兄弟から不変共有する。子の変更だけ私有化する。metadataと実行状態はDB別。
- Snapshotはguest全workerの完了後に固定し、元内容・固定後・所有取得の
  全内容検査を維持する。通常経路はpayloadの一時fileを作らない。
- Pythonの独立したstartごとにhostを1個自動管理する。request ID、DB別制御、
  個別cancel、遅延成功回収、参照数と最終waitを追加する。
- Human指定で保存／loadと`db.snapshot(path)`を削除する。
  `snapshot()`→`fork()`を残す。GoのDestination／LoadSnapshotも削除。
  明示的な異なるhost binaryへのForkだけ、非公開の一時handoffを使用する。
- DBあたりの接続上限16、消費型Snapshot、busy／transaction拒否時の元DB保持は維持。

host停止時は同じ系統の基準・子が失効する。別startのhostは独立する。
個別のSQLエラー／Close／要求timeoutで、使用中の兄弟host全体をkillしない。
任意の非協調guestを個別に強制回収する保証は追加していない。

## 再現と所有元

guest Wasmは`7d1330e67b06eb810d0fafd649df0944dbca1b20cd7e49f8e5ecdde7f5ac8c09`。
正式guest buildの独立2回で一致し、古いCI artifactの別guestは入力採用前に拒否した。
正式translation→source adapter→`generate_runtime.py`を実行し、独立translationからも
canonical sourceと一致した。生成物の手編集はしていない。

生成差分は`base.go`からのMemFS切り出し、`relative.go`／`prepared_files.go`の
storage接続のみ。MariaDB由来の関数・データは同じ。
`runtime_memfs.py`とHANDWRITTEN_FILESが変更の所有元となる。
provenanceは`7c7ad7b5a14b55d3d63cb9bc2484e7c93e99860f0a1b0731104d01f8ecc94589`。
license continuityとPython mirrorも対応させた。

## 検証状況

macOS arm64の初回integrationはPASS。SQL／transaction、派生基準、4並列、
100 Fork/Close、10世代、host SIGKILL、異なるbinaryのhandoffを含む。
通常Go単体テストもPASS。追加した診断保持・失敗回収・並行read/writeを含む
最終候補のcheck／integration、外部consumer、規模比較は進行中。
Ubuntu x86_64は未実行でありPASSではない。

初回正式checkでは起動診断4件が失敗し、診断保持を修正した。protocol期待値のみ
新方式の2に変更し、終了code／cause／stderr／guest stageのassertは維持した。
初回integrationのPASSを、その後の修正全体のPASSとして転用しない。

既存Ubuntu証拠の`.log`名は公開source guardに反するため`.txt`へ変更した。
integration証拠内のCI絶対path1箇所はrepository相対pathへ正規化した。
元bytesは上記main commitに残る。guardは緩めていない。

## 完了判定

設計§6の固定集合で判断する。機能・所有・制御・consumer・独立生成・規模・
両native platform・正式候補対mainの限定比較が対象。
未実行をPASSや完了へ置換しない。比較は
[専用harness](../../benchmarks/sharedhost/README.md)の6通常対／3資源対を用い、
過去の試作数値を今回の性能結果として扱わない。

採用推薦と最も強い反論は、これらの結果を保存した後にHuman Reviewとして更新する。
