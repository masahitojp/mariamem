# mariamem / pgmem 性能調査の見取り図

更新日: 2026-11-02。既存計測の整理であり、新しい測定・改善案の承認・製品採用を示さない。
参照した最新の調査記録は `0eaa5cae11590b3c500fc40f16906137e251daf4`。
各資料は元の測定source、条件、生データ・checksumへの参照を保持する。

**比較した子DBライフサイクルではmariamemの方が遅く、ForkのCPU費用と子DB保持時の
メモリ増分も大きかった。具体的な無駄は一部特定したが、差全体の原因・改善可能量は未確定。**
一方、「mariamemは4並列が限界」という結論は支持されていない。

## 前提と読み方

主な比較環境はApple M1 / 16GiB / macOS27.2 / Go1.27.3 / CGO0 / GOMAXPROCS8。
mariamem v0.6.0とpgmem v1.18.2、MariaDB12.3.3とPostgreSQL18.3、両方TCP。
1,000整数行を用意したSnapshotから独立した子DBを作る。例外となる70テストの
アプリスイートなどは、行ごとの資料の条件に従う。

- 「確認した事実」は、そのホスト・fixture・計測回数内での観測。全用途への保証ではない。
- 別計測の絶対値をつなげて改善量を計算しない。CPU時間・経過時間・RSS・Goヒープも区別する。
- 子を順に作って保持する試験と、並列に作成・利用・破棄する試験は異なる。
- CPU時間は全threadの合計。「CPU使用率が高い」と同義ではない。
- 実験用overlayの改善結果は、正式guestの再生成やmain採用の証拠ではない。

## 事実・分かったこと・未解明点

### 処理時間とCPU

| ID | 確認した事実 | 分かっていること・調査済みの範囲 | 分かっていないこと | 根拠 |
| --- | --- | --- | --- | --- |
| F01 | 比較した子DBライフサイクルではmariamemの方が遅かった | 48子DBのバッチ中央値は4並列で1.115秒 / pgmem 0.269秒、8並列で0.600秒 / 0.266秒 | 差全体の処理別内訳と改善可能量。SQLエンジン単体の速度差ではない | [S3] |
| F02 | ForkのCPU費用が大きかった | 中央値49.23ms / pgmem 7.27ms。各5process。初期構築・拡張・ゼロ化の候補を調査した | 約6.8倍の差の大部分を説明する内訳は未確定。候補ごとの寄与を合計できる状態ではない | [S1] [S2] |
| F03 | Forkの経過時間が長かった | 中央値36.41ms / pgmem 5.30ms。整列修正の別A/Bでは40.71→38.73msと小幅改善 | Fork全体の経過時間を決める経路と、CPU処理・待機の完全な内訳 | [S1] [S5] |
| F04 | 最初の領域確保・初期構築だけでは大きなCPU費用を説明できなかった | 最初の確保は約0.01ms、構築は約1.56ms。その後のMariaDB起動に大きな仕事がある | 後続初期化の用途別費用、減らせる処理 | [S2] |
| F05 | 起動中に小刻みなメモリ拡張があった | 子ごとに101回。拡張→保護設定処理がCPU profileで目立った。呼出し回数を減らす試作では明確なFork高速化を示せなかった | 安全な拡張方式の変更が実用的な改善になるか | [S2] [S6] |
| F06 | buffer pool確保に具体的な無駄があった | 整列不足で確保をやり直し、余分にゼロ化。試作で約17.7MiBのゼロ化を除去し、Fork CPU中央値53.61→52.03ms、経過時間40.71→38.73ms | 正式guestでの再生成、他環境・OOM等の失敗経路を含む採用可否。速度改善は5組中4組で、安定した改善率の保証ではない | [S5] |
| F07 | 初回の重複ゼロ化を省くだけでは大きな保持メモリ削減は残らなかった | fresh-zero試作は構築直後に約8.55MiB減ったが、readyでは約0.19MiB差。Fork全体のCPU改善も一貫しなかった | 別の初期化条件での効果。構築時の節約を、そのまま最終保持量の節約にはできない | [S7] |

S2のmprotect経路22–25%は、Fork・接続・検証・Closeを含むcycle全体の累積CPUサンプル比率。
Forkだけの比率でも、22–25%高速化できるという予測でもない。

### メモリと子DBの保持

| ID | 確認した事実 | 分かっていること・調査済みの範囲 | 分かっていないこと | 根拠 |
| --- | --- | --- | --- | --- |
| F08 | 子DB保持時のメモリ増分が大きかった | 4子保持時のRSS増分は+311MiB / pgmem +103MiB。mariamemは1子で約+77MiB、2子で約+155MiB | 安全に共有・省略できる量、その変更の性能効果。増分を普遍的な1子サイズとはしない | [S1] |
| F09 | 子なしの基準RSSはmariamemの方が小さかった | 約50MiB / pgmem 約137MiB。source準備・Snapshot・source Close後の状態 | 内訳の完全な対応。Snapshot object単体のサイズではない | [S1] |
| F10 | mariamemのメモリ増分はGoヒープだけでは説明できなかった | 4子保持・GC後のGoヒープ増分約10MiBに対しRSS増分約311MiB。別の段階観測ではguest領域のready時residentが約75MiB/子 | guest内の用途別内訳、専有・共有・dirtyページの正確な構成。内容が同じページを安全に共有できるとは限らない | [S1] [S2] |
| F11 | 子DBのClose後にmariamemのRSSが大きく下がった | 約361→61MiB。GC前に低下した | 長時間・大量反復で蓄積しないか。これだけではリークの有無を確定しない | [S1] |
| F12 | idle CPUはこの計測では小さかった | 500ms待機区間のCPU時間中央値は約0.4ms。常時busy loopを優先する根拠はなかった | 別負荷・長時間待機での挙動 | [S1] |
| F13 | バッチ中のピークRSSはpgmemの方が大きい計測もあった | 4並列でmariamem約379MiB / pgmem約936MiB、8並列で約700MiB / 約994MiB | 再利用・GC・解放後の保持などの寄与。F08の保持増分とは別指標で、相互に否定しない | [S3] |

RSSはprocess観測値であり、専有物理メモリやPSSと同一ではない。
バッチピークは約20ms間隔の標本で、短いピークを取り逃し得る。

### 並列スケーリングと長い待ち

| ID | 確認した事実 | 分かっていること・調査済みの範囲 | 分かっていないこと | 根拠 |
| --- | --- | --- | --- | --- |
| F14 | 「4並列が限界」は確認されなかった | 最初の70テストでは4並列が最短。後の48子DB比較では3組すべて8並列が速く、約18–46%短縮した | 用途・マシンごとの最適並列度。二つの試験は異なる仕事・測定範囲で、直接の改善前後比較ではない | [S3] [S4] |
| F15 | 並列度4→8でCPU総時間とピークRSSが増えた | 同じ48子の処理でCPU時間は3組とも約15–22%増。RSSは約379→700MiB。一方、wall timeは短縮した | CPU配置・同期・帯域等の寄与。増加自体から性能制約の主因は決められない | [S3] |
| F16 | 一部のSQLに数百msの長い待ちがあった | 全体時間を延ばす例を確認。後続観測で、DB内poolの実行制限がqueued workを進めない場面を捕捉した | 残るworkerがCPU処理中か、別の待機中か。pgmemとの差全体への寄与 | [S3] [S9] |
| F17 | read1→4で速くなった計測があったが、安定した効果は未確認 | 最初はバッチ中央値約27%短縮。観測コードを追加した後続比較では約808→808ms。後続は完全な同条件の再試験ではない | 同条件での再現性、効いた機構、既定値を変える価値。無意味と証明されたわけでもない | [S8] |
| F18 | 待機通知の欠落を修正した試作で、一部のキュー待ちは改善した | 子ごとの最大キュー待ちの中央値9.50→8.12ms、p95は21.91→20.13ms。追加通知が実行されることも確認 | p99は776→786msで事前の分布受理条件は未達。残る長い待ちの修正箇所と正式guestでの採用可否 | [S9] |

F16–F18は主にForkが返った後のSQL待ちの調査。F02–F07のFork費用とは分ける。
長いSQL待ちの一因を特定したことを、ForkのCPU差や並列スケーリング全体の説明へ読み替えない。

## 現在の到達点と停止点

- 改善を考える元になる観測は、ライフサイクル時間、ForkのCPU費用、保持メモリ増分の差。
- 具体的な変更箇所まで到達した候補は、buffer pool整列とpool待機通知。いずれも実験段階で採用済みではない。
- 「4並列の壁の解消」「read4で27%改善」を確定した目的・効果にしない。
- [Issue #68](https://github.com/masahitojp/mariamem/issues/68)の今回の長時間待ち調査区間は終了。
  Issue自体は未解決のまま。別の調査を開始する判断は、この一覧を見て対象・期待成果・終了条件を選び直す。
- この文書の作成で新たな計測、実装、main採用、Qualification、releaseは行っていない。

## 根拠資料

リンクは内容を固定したGit commitを指す。各資料中のmeasured sourceは、報告を保存したcommitとは別に記録されている。

[S1]: https://github.com/masahitojp/mariamem/blob/34f9c7704e042fb36360bbd3b91603ed6611326c/benchmarks/fork-resources.md
[S2]: https://github.com/masahitojp/mariamem/blob/d5334cf8e40a77092cbe37c49b0112a7621b7707/benchmarks/fork-initialization.md
[S3]: https://github.com/masahitojp/mariamem/blob/5096a0c4931e2d30b56e1d1160b3e334f35df396/benchmarks/parallel-pressure.md
[S4]: https://github.com/masahitojp/mariamem/blob/73a0e091ba15d0f007a2f5bd2f040040002f855d/benchmarks/parallel-modelcase.md
[S5]: https://github.com/masahitojp/mariamem/blob/30239a34977c6eaaa2ca804fc28e2553e498af48/benchmarks/buffer-alignment.md
[S6]: https://github.com/masahitojp/mariamem/blob/1e1b46b0a2208ad66eea8752e1c2d54475a9cbdc/benchmarks/growth-prototype.md
[S7]: https://github.com/masahitojp/mariamem/blob/1597b7c41b26a75609a7ec383f3082792dc9cf3e/benchmarks/fresh-zero.md
[S8]: https://github.com/masahitojp/mariamem/blob/ff60566f5662e1d02d169574b8a7f40f1f1366b6/benchmarks/read-io4-evidence.md
[S9]: https://github.com/masahitojp/mariamem/blob/0eaa5cae11590b3c500fc40f16906137e251daf4/benchmarks/wait-accounting.md

| 資料 | 内容 |
| --- | --- |
| [S1] | ForkのCPU・経過時間、0/1/2/4子保持、Close後・idleの資源観測 |
| [S2] | 最初のメモリ構築と後続起動の切り分け、CPU profile、residentページ観測 |
| [S3] | 同一48子DB処理の4/8並列比較、CPU・RSS・SQL長時間待ち |
| [S4] | 最初の70テストの1/2/4/8並列比較 |
| [S5] | buffer pool整列の局所試作 |
| [S6] | メモリ保護設定の呼出し削減試作 |
| [S7] | fresh-memory重複ゼロ化の省略試作 |
| [S8] | read1/4の後続比較、初回結果と再現性の限界 |
| [S9] | 待機通知の試作、キュー分布、残るworkerの観測境界と停止記録 |
