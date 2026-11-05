## 問いと仮説

Snapshotからデータを読むhost側で、直後にmapped dataで上書きする領域まで先にclearしている。この重複書込みを省くと、ForkのCPU・経過時間、特に並列時の費用を減らせるのではないか。

2026-11-05 Human: 直近のFork内訳を踏まえ、まず仮説をIssue化する。本Issueは候補登録で、製品実装・採用・新しいrelease必須条件の承認ではない。

## 根拠と未確定点

- product source `1862f4a89397bddfa1820d835106d3437a438cf7`、guest `6d7442204d39bc28eb4b34401874b84b4d3f517c2bb698ba7f3a465027c36cbe`。Go Pipe、M1/16GiB/macOS27.2、Go1.27.3/CGO0/GOMAXPROCS8。
- `internal/prepared/root.go` のrootRead、mapped fallback経路は `clear(dst)` の後に `copy(dst[:nr], ...)`。コピーされるprefixのclearは、コピー成功を保証できる同じ経路では不要な書込み候補。
- 別採取の48子batch CPU profileでrootRead→memclrのsampleはP1約140ms、P8約300ms。これは全batchの約6.0% /8.8%であり、Fork単独CPUでも、除去できる時間の確約でもない。profileは各P一回の短いsample。
- ゼロ埋め全体を不要とはしない。hole、mappingの範囲外、block.valid以降、short read、resizeによるゼロ領域は維持必須。
- #64のmodule初期clear省略、#63のbuffer pool整列とは別経路。過去の削減量を再計上しない。

## 最小の検証案（実行は次の選択）

1. このread経路だけを対象に、変更前と「mapped prefixをcopyし未充足suffixだけclear」のhost-only A/Bを作る。guest/config/公開APIは固定。
2. 非zeroで汚したdestinationを使い、full mapped・partial mapped・hole・EOF/short read・block境界・dirty block・truncate/resize後の内容と返り値を既存契約と照合する。親/兄弟Snapshotの独立性とcleanupも確認。
3. source/guest/binary/overlayを固定。まず1host/1,000行、Go Pipe、48子、P4/P8、別warmup、同一binary条件で交互5ペア。通常timingと診断カウンタ/profileを分離し、全試行を保持。
4. 主指標はFork経過と48子batch wall、補助はbatch CPU/child。診断では実際に避けた書込みbytesを確認。RSSを測る場合も「保持子」と「batch peak」を区別する。400–800ms SQLを事後除外しない。

## 終了条件・費用

初期案はactive60分（tooling20分以内）、heavy CI0。機構上の重複除去と実利用速度の改善は別々に結論を出す。正しさFAIL、寄与が小さい、効果不安定、保守費用が大きい場合も見送りで終了できる。一般的なゼロ化省略や共有memory設計へ広げない。

採用候補になった場合だけ変更境界相応の両OS correctnessと別Human Review。main統合・Qualification・releaseは別。

## 証拠

- [今回の工程別内訳・全結果・profile・checksum](https://github.com/masahitojp/mariamem/blob/3dbfff01b428d54cbc77c3281400cbb683ac4ac6/benchmarks/forkstages/results/README.md)
- [同じ候補のPipe/TCPとpgmem比較](https://github.com/masahitojp/mariamem/blob/707463f33f3191a511175248a73ef80f763f898e/benchmarks/uca-pipe-pgmem/README.md)

## 2026-11-05: 実行前固定 — 数値閾値とserver_init予測

Human: 「(a) 数値閾値と (b) server_init予測を追記してから開始」。以下は結果を見る前の選定基準。条件を満たしても自動採用せず、候補継続を推薦する根拠とする。

### (a) 数値閾値

- 正しさ・独立性・返り値/EOF・cleanupは全件PASSが必須。1件でもFAILなら性能で相殺しない。
- まず機構を確認: 診断経路で避ける重複clear量が平均1MiB/Fork以上。未達なら寄与小として本試作を終了可能。この値はRSS削減量ではない。
- 主判定は診断なしP4、48子×交互5ペア。各processの48子Fork中央値を用い、ペアごとの改善量の中央値が **1.0ms以上かつ3%以上**、かつ **5ペア中4以上で短縮**。
- 同じP4のbatch process CPU/48子は、ペア改善率中央値 **3%以上**、かつ **5ペア中4以上で減少**。これはFork単独CPUではない。
- P8は交換条件確認。同じ5ペアでFork中央値またはbatch CPU/childのペア中央値が **5%超悪化**すれば無条件の候補継続を勧めない。batch wall、p95、>100ms SQL件数は全件を併記し、外れ値を削らない。
- batch wallはP4/P8とも全5ペアを保存し、ペア中央値が5%超悪化した場合は尾部との関係を説明したうえで「保留/見送り」。事後除外で合格にしない。
- 閾値未達・方向不安定でも、機構上の無駄削減と利用者性能を区別して本ラウンドを終了する。追加repeatで合格に寄せない。

### (b) server_initの事前予測

仮説は「server_initが内部で行うprepared file読取りの重複clearを省くため、主な短縮はメモリmodule構築ではなくserver_initに現れる」。前回profileはbatch全体であり、rootRead sample全量をこの区間へ帰属しない。

- P4: 対照に比べserver_init子平均が **1〜3ms短縮**するという弱い事前予測。前回の診断値32.96msなら概ね30〜32msに相当するが、旧cohortを今回の対照に使わない。
- P8: **2〜5ms短縮**を予測するが、資源競合による不確実性が大きい。P1は今回の主matrixに追加しない。
- memory reserve/constructは変更しないので、一貫した大幅短縮は予測しない。
- server_initは同じobserver・同じbinary条件の別診断で各P3交互ペア、全sample保持。診断なし性能判定と混ぜない。
- P4 server_initの平均短縮が0.5ms未満、または3ペア中2以上で短縮しない場合、この帰属予測は支持されないと記録する。CPUだけ減った場合も「server_init改善を確認」と書かない。

実行はexperiment/issue116-read-clearのdisposable workspace、host-only overlay、guest/公開API/config固定。初期active60分/tooling20分/heavy CI0、build/process timeoutとdisk上限をmanifestへ固定。ここでの承認はbounded prototypeであり、main採用・全面matrix・releaseではない。


### 実装前source照合による経路の補足（性能結果を見る前）

FrozenFile.Forkはsealed heap blockを継承し、mappingを引き継がない。通常子のrootReadは主に `e.block.ReadAt(dst,in)` を通る。そのBlock.ReadAt（internal/prepared/heap.go）にも全dst clear→valid prefix copyがある。profileのrootRead→memclrをmapped fallbackだけの費用と読まない。

試作は **rootRead内の継承block読取りとmapped fallbackの2分岐** に限定し、どちらも有効prefixをcopy、未充足suffixのみclearする。同じ重複書込みの仮説の経路修正であり、一般Block.ReadAt/他のheap利用者の契約や実装は変えない。診断counterは継承block・mappedを分離する。通常Snapshot経路で実際に避けたprefix clear量を機構ゲートに使う。既存の数値閾値・server_init予測・試行数を変えない。
