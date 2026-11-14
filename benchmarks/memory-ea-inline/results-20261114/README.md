# MemoryEA境界検査保持inline試作 — Issue190、2026-11-14

**結論: 次の候補化・受入れ検討へ進める価値がある。** 差分加算triggerを保持したraw100明細INSERTは、P1/P8とも5/5組で短縮し、CPUも全組で減少した。一方、test binaryは約74%増加する。製品採用・統合・releaseは今回行っていない。

最も強い反対材料はコード増加と検証範囲。元SUM条件、70テストsuite全体、Ubuntu、製品基準Go1.26.10、新converterによる全面再生成は未検証。局所probeの利益だけで全体比較差10%達成や汎用的な改善を断定しない。candidateのcold panic内部スタックからnamed trap helper frameがなくなる意味差も明記する。

## 一案の変更と生成元

`benchmarks/spikes/wasm2go/pure-memory32.patch` がcanonical生成元。上流converter 730057c146463f663e8774587bc96fb2bea91af8へ適用するこのpatch内のmemoryEAで、`wasm_trap_memory_oob()` を**同じ値の直接panic**へ置換した。MemoryInBoundsのaddr/offset/size判定、atomic MemSizeの読取、返すアドレスは変更しない。atomic helperやmemcpy/memsetを変更せず、bounds検査を省略していない。

実際にコンパイルした生成Goは同じ一行の診断overlay。canonical patchもexperiment branchに保存し、生成済みファイルだけの手編集を製品候補としない。release pinやguest source.patchは変更しない。

```go
func MemoryEA(m *Module, addr, offset, size uint64) uint64 {
    if !MemoryInBounds(m, addr, offset, size) {
        panic("wasm: memory access out of bounds")
    }
    return addr + offset
}
```

Go1.27.4の実base.go compiler診断はbaseline cost100>budget80、candidate cost44でinline可。compiler-probeは理由確認用の小さい構造例でcost99/43となり、実Moduleと同じcostとは主張しない。原因はnoinline trap helperへの呼出しがinline budgetへ加わっていたこと。panic文字列・型は同じだが、内部stacktraceは同一ではない。

## 実機械語 — 全関数で消えるわけではない

| 生成関数 | baseline MemoryEA call箇所 | candidate |
|---|---:|---:|
| Fn13460 close_thread_table |157|0|
| Fn15541 Table_triggers_list::mark_fields_used |68|0|
| Fn15594 update_single_table |853|853|
| Fn13338 sp_head::execute |426|426|
| Fn14146 Write_record::write_record |387|387|

これは静的なcallsite数で、実行回数ではない。ほかにFn13977/Fn17041も今回の機械語では変化なし。大きい関数にはcallが残り、小さい関数でinline展開した。候補化にはcompilerのlarge-caller条件等も考慮し、全部の呼出しを削れたと扱わない。mechanism.jsonと選択した実assemblyを保存。Fn68はこのprobe binaryに独立symbolがなく、call0の証拠には使っていない。

## 固定性能対照

baseline source_commit bb1e937ae75b5788c8548a52987d9d42f78292d5、canonical guest SHA256 77b2ab49a9927f15c899ad34f9f40e5f06ac42589b1d4f926fd0c5b0f1f19450。source.jsonでbuild前にcommit identity確認。候補はそのbaseからのcanonical patch一行とoverlay。source-binding.jsonに生成元before/after hash、各overlay/binary hashを保存。

Go1.27.4/macOS arm64/CGO0/GOMAXPROCS8/GOGC100。harness706072d8、差分加算trigger・監査status限定・5 triggers・注文UPDATE・制約/indexを両arm同じに保持。INSERT_STAGES=0、CPU profileなし。既存の無効な観測hook/Moduleフィールドは両binaryに残るので、無加工の製品binary比較とは言わない。REVENUE_PREAGG=1設定保持（専用probeは売上queryを実行しない）。

P1/P8各arm1warmup＋交互順5組、合計24process/192 DB/19,200 raw INSERT。Fork・40親注文・BEGIN/PREPARE・COMMIT・oracle/Closeはraw区間外。process全体wallはそれらと起動・停止を含み、70テストsuite全体ではない。

| 指標 | P1 baseline | P1 candidate | 対応変化率中央値 | P8 baseline | P8 candidate | 対応変化率中央値 |
|---|---:|---:|---:|---:|---:|---:|
| raw100件p50、ms |12.807|10.434|**-18.78%**|22.136|18.650|**-16.50%**|
| probe process wall、ms |484.127|435.290|-10.09%|287.719|235.311|-18.28%|
| process total CPU、ms |657.557|577.950|-12.00%|753.731|655.495|-13.03%|
| 最大RSS、MiB |617.781|623.047|+1.14%|613.734|617.547|+0.63%|

rawは各process内の8 DBの中央値を、5processでさらに中央値化した独立値。対応変化率は同じroundのcandidate/baselineから計算した値の中央値で、独立中央値比ではない。RSS/CPU/wallも同じ集計。

raw/wall/CPUはP1/P8とも各5/5組でcandidateが小さい。P8 raw変化率は-17.31〜-6.31%、process wallは-19.97〜-0.52%と変動を保持。最後のP8候補のwall利益が小さい個体も除外しない。共有hostの有限結果で追加反復や補正は行っていない。

process wallは両arm `/usr/bin/time -l` のwrapperを含む。raw spanはharness内の既存時計。最大RSSはmacOS timeのbytesを記録してMiBへ換算。CPUはRUSAGE_CHILDREN差分、他のowned build/再帰容量走査を重ねていない。最大RSS追加はbinary増加判明後、性能計測前にIssueへ固定した。

## コード増加

同じgo test -cの非strip binary: baseline111,000,530 bytes（105.858MiB）、candidate192,899,954 bytes（183.964MiB）、**+73.78%**。コードだけのサイズとは区別する。最大RSS増加は約1%に収まったが、disk・link/build負担・cold実行・instruction cacheの交換条件が消えたわけではない。compile時間のarm別正確な対照は取っておらず、遅く見えたという観測を定量的な工数差にしない。binary削減を別候補として自動探索しない。

## 正しさと到達した境界

両armのfocused base検査成功。独立big.Int oracleで端点、zero-size、最大uint64を含む組合せとランダム計24,641件の判定/返値/panicを照合。10,000回ずつのshared atomic bound読取/変更対照も実施。実アドレスをdereferenceする全範囲の証明ではなくMemoryEAの算術規則の検査である。

既存 `go test -tags=integration ./tests/generatedmemory` を両armで実行し、5 top-levelすべてPASS:

- 実生成load/storeのOOB、幅の跨ぎ、非wrap offset、grow後のzero領域。
- shared workerの可視性/TLSとgrow、worker OOBのjoinへの伝播、繰返しjoinの失敗保持。
- CRUD/session/Fork、placeholder credentials、RepeatedClose、独立root/snapshotのprocess image。

24processの全192 DBで実登録trigger本文、orders40/items100/audit40/合計/stock500/FK/CHECK拒否、公開Closeを検査し成功。base focusedのbulk bounds、host logical memory、narrow atomic、prepared growth/ownershipも成功。フルrace/全consumer/両OSの製品受入れを実施したとは言わない。

## 推奨と残る条件

この一案の有限試作は完了し、効果とコード増加が両方分かった。候補化の検討を推奨する。次の判断は約74%のbinary増加を受入れ検討へ進む価値があるか。次を実施したと誤認しない:

1. canonical converter patchを適用した新converter build・同じguestの全面再生成。unused trap helperが生成inventoryから消える可能性、source/manifest/provenanceを確認する。今回は生成元変更＋同じbodyのoverlayまで。
2. 製品基準Go1.26.10と対応両OSの正しさ、元SUM workloadと70テストsuiteのP1/P4/P8での観測なし利益/悪化、必要な公開consumer/停止契約。
3. code size/cold/RSS/build負担を含むHuman採用判断。採用とmain統合/releaseを別にする。

今回のraw短縮を他エンジンとの現在差や全suite差10%達成へ換算しない。さらに別のinline方法やengineパッチへ自動拡大しない。

## 再現と保存

固定bb1e937aからexperiment-workspaceをprepare（name memory-ea-inline、8GiB予算/最低空き8GiB）、本bundleをevidenceへコピー。repo root cwdで `python3 evidence/setup190.py` を実行（実際はworkspace evidenceの絶対pathを指定）。固定706072d8のharness/基本overlayをGitから展開し、保存された最終property testを適用する。setup190.pyは生成元patchも変更するため新しいcleanなfixed-source worktreeを使用する。

`python3 evidence/build.py`→`verify-runtime.py`→`check-mechanism.py`→`measure.py`→`analyze.py`。各scriptは自分の配置からworkspaceを解決する。両overlay hash/harness/最終binary hashを照合する。baseline/candidate二binaryで同じ設定、observer off。各build20分・campaign15分上限。compiler-probeは補助資料で実生成コードの代用ではない。

全標本・検査・compiler診断・選択assembly・生成元変更を固定refで保存。巨大binary/cacheは再現可能なのでpush/照合後にcleanupする。helper監視のbuild peak owned約4.08GB、最低空き約17.58GBで8GiB/8GiB予算内。測定中にowned buildを重ねていない。
