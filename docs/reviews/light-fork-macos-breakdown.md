# v0.5.1 Light Fork — macOS lifecycle breakdown

2026-10-17。macOSでの追加計測は完了。**Snapshotは今回約193msで、停止後の固定・digest作成・
2回の内容検証がほぼ全体を占めた。Forkは約52ms/子で、guest開始からreadyまでが約35ms/子。**
このLight条件では、Snapshotを速くする第一候補は停止方式の変更より、重複走査の安全な統合である。

## Human Review

**次の判断は、追加hash削減の設計検討を先に進めるか。私は進めることを推薦する。**
既存コードで確認した3回走査が、今回もそれぞれ約63msの区間として現れた。
一方、Snapshot停止・worker合流・回収等を含むfreeze外の残差は約2.5msだった。
削れる区間の大きさに根拠が得られたため、MariaDB停止方式を変えるより先に、
検証済み不変backingと所有取得を結ぶ設計を検討する価値がある。

**最も強い反論は、これらが正確な対象の破損検出を支えており、単純な検証削除は保証を落とす点。**
約63msをそのまま回収できるとは断定しない。所有・alias・failure oracleを維持できる方法を
設計レビューしてから実装を判断する。Forkのguest内部初期化約35msの内訳は未解明なので、
そこにも改善余地はあるが、今回の結果から停止・再起動方式全体の変更は推薦しない。

## Inputs and boundaries

- Published v0.5.1 source_commit `7a82f338cf111d5d52538b5a3f7bf129c12e2dbb`、tag_object_sha `089b32e09608902f6d46e7ab9527d09922dcf065`。型付き[pin](../../release/baselines/v0.5.1.json)を`git_identity.py`で検査。
- macOS27.0.1 arm64／Apple M1、Go1.26.8、CGO=0、`-p 1 -trimpath -buildvcs=true`。
- cleanな独立cloneから、benchmarkと手書きhostの計測だけをGo overlayで追加。実binaryのVCS revision／modified=falseとhashを確認し、overlay source/hashを明示した。stampのcleanはoverlayなしの意味ではない。
- guest／生成Go／ライブラリの処理分岐／API／GC設定／SQL oracleは変更していない。productionへの修正はない。
- 既存Go Light：1表、1024-byte行1個、4直列Fork、`app-connections`。準備→Snapshot→子ごとのcount/point・commit/rollback・SQL切断待ち・Close→基準Close。
- 計測なし／traceありを交互に各10回。同一observer binaryを使用。traceなしも、無変更binaryとの独立校正ではない。
- ユーザー提示のLinux/pgmem workloadとのfixture／SQL／終了境界の同一性は未確認。pgmem再計測とLinux実行は行っておらず、提示値との直接差分は算出しない。

## Whole workflow

各10回の中央値、ms。各操作は試行内で4子分を合計してから中央値を取った。
行の中央値を足しても全体中央値には一致しない。

| 区間 | traceなし | traceあり |
| --- | ---: | ---: |
| 起動＋データ準備 | 56.55 | 55.86 |
| Snapshot | 192.86 | 193.70 |
| 4子Fork起動 | 206.64 | 209.59 |
| 4子SQL | 26.96 | 21.57 |
| 4子SQL切断待ち＋Close | 34.37 | 35.12 |
| 基準Close | 0.001 | 0.001 |
| 全product区間 | **517.67** | **516.63** |

全体は近いが、SQL区間などの差もある。これで計測負荷ゼロや統計的同等性を証明しない。
traceは既存の時刻記録・file書き出しを含み、区間間のスケジューリングにも影響しうる。
通常の全体時間はtraceなし、詳細はtraceありを独立して報告する。

## Snapshot: three logical passes dominate

traceあり10回の区間中央値、ms。

| 内訳 | 中央値 | 正確な意味 |
| --- | ---: | --- |
| 固定＋元内容digest作成 | 63.75 | `freezeHeap` begin→source_inventory_hashed。内容読み取り、hash、不変blockへの移行等を含む |
| 固定後の内容検証＋metadata | 63.33 | source_inventory_hashed→target_verified。NewHeap／対象descriptorからの全量Verify等 |
| 所有取得の内容検証 | 63.31 | `OwnHeap` begin→end。同じimmutable backingを再度Verify |
| finishのうちfreeze外 | 2.48 | finish envelopeからfreeze envelopeを引いた残差。純粋なInnoDB終了時間ではない |

freeze全体127.18ms、snapshot finish129.69ms、snapshot capture全体193.47ms。
finishはfreezeを内包するので両者を足さない。guest root／worker合流後にfreezeし、
その後のdescriptor／memory解放・transport完了を待ってfinishが戻る。
残差には停止・worker合流・回収・trace書き出し等を含み、それぞれは未分離。
LightはSQL投入が軽い意味であり、内部DBファイルの論理長が1KiBという意味ではない。
内部ファイル別の論理長・hash CPU単独・各copy量は今回追加計測していない。

**この結果は「固定・検証区間が支配的」を示すが、「すべてhash CPU」「検証を外してよい」を示さない。**

## Fork and Close: preserve the user-visible boundary

4子合計のtrace中央値：

| 区間 | 合計ms | 1子あたりの換算 |
| --- | ---: | ---: |
| Fork API | 209.59 | 52.40 |
| linked execution開始→最初のready frame受信 | 139.13 | 34.78 |
| host内部startup全体 | 140.10 | 35.03 |
| APIのoptions ready→runtime directory ready | 34.78 | 8.70 |
| host callのうち内部startupの外側 | 33.62 | 8.40 |
| 子SQL切断待ち＋Close | 35.12 | 8.78 |
| host finish全体 | 8.72 | 2.18 |
| 上記finish内のShutdown call | 8.70 | 2.17 |

Forkの基準Acquireからlinked execution開始までを含むhost前段は4子合計0.46ms、
ready header後のhost後段も合計0.46ms。今回の大きなguest区間は開始→ready。
ここにはmemfs復元、memory module準備、MariaDB初期化、応答transport等が含まれ、
その内部を純粋なInnoDB時間や特定の初期化へ帰属していない。

API前段とhost内部startup外にはそれぞれ`ValidatePlatform`があり、macOSでは毎回
`/usr/bin/sw_vers -productVersion`を実行する。上記2区間は合計で約68ms/4子だが、
sw_vers単独の所要時間を計測したわけではない。directory作成等も含む。
Linuxは別のOS判定経路であり、この約17ms/子をLinuxの説明へ転用しない。

既存harnessの`child_close`は`disconnect(child,pool)`（pool.Close＋WaitDisconnected）と
Database.Closeの合計。**35.12msを純粋なDB Close時間と呼ばない。**
`WaitDisconnected`には5msのpoll間隔があるが、外側との差を全てpoll待ちと断定しない。
host finishは約8.72ms/4子で、さらに外側のSQL切断待ち・directory cleanup等は未分離。
pgmemの非同期Closeとの同条件比較は今回していない。

## Verification, evidence and stop

20実行／100 DBで既存SQL・commit/rollback・子の独立性oracle PASS。
各processのmapping creates=releases=5、最終active mapping／reserved／RW／release failureはゼロ。
traceあり各試行でfreeze/own/capture各1、startup5、Fork4、finish5を確認。
source statusとbinary hashは実行後も不変。

[receipt／全20実行／全trace／解析](../../benchmarks/light-fork-breakdown/evidence)、
[再現手順と測定境界](../../benchmarks/light-fork-breakdown/README.md)、
[集計source](../../benchmarks/light-fork-breakdown/analyze.py)を保存。
実行部分は約29秒、ビルドは別。workspace peak1.451GiB／空き最小67.723GiB。
失敗workloadの再試行、遅い観測の削除、guard緩和はない。

今回完了したのはmacOSでの外側区間と3回走査の分解。
未完了はguest初期化内部、純粋なhash CPU、個別SQL切断／directory cleanup等への帰属。
これらを未完了として残し、追加修正や測定へ自動的に範囲を広げない。
main統合・新しいリリースは行わない。raw evidenceを保存し、使い捨てclone／cache／binaryを片付ける。
