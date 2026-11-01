# 16MiB → 17.707MiBのゼロ化は、buffer poolの整列による再確保だった

**用途と再試行の理由を特定できた。InnoDB buffer poolの確保で、WASM向けの
4KiB整列と、buffer poolが要求する2MiB整列が一致していなかった。**
最初の領域はbuffer poolとして利用される前に解放されるが、移植層が既に全域をゼロ化していた。
同じguestアドレスが再利用されたため、前回の観測では同じ範囲への2回のゼロ化として見えていた。

推奨する次の候補は、**buffer poolの予約を初回から必要な境界へ揃え、再試行を避ける**
小さな試作。ゼロを返す契約は維持する。最も強い懸念は、高い整列条件がallocatorの
過剰確保・断片化・失敗率を変えることと、実時間の改善が小さい可能性である。
今回で原因追跡は終了し、その試作やguest再ビルド、採用はまだ行っていない。

## 確保と解放の流れ

[前回の6子の観測](https://github.com/masahitojp/mariamem/blob/d6e9249906b38ed1cc842865fda4b18364bd26c8/benchmarks/zero-fill.md)
は、全て次の計算に一致した。

```text
16MiBを4KiB整列で確保 → 16MiBをゼロ化
  ↓ buffer poolの2MiB境界へ揃えると、利用可能な容量が不足
解放（buffer poolとしての利用・commitより前）
  ↓ 不足分を追加して再試行
17.707MiBを確保 → 17.707MiBをゼロ化
  ↓ 先頭1.707MiBを飛ばして2MiB境界へ揃える
16MiBをbuffer poolとして利用
```

| 項目 | 観測／計算値 |
| --- | ---: |
| 返されたguestアドレス（両回とも） | 419,737,600 |
| 2MiB境界からのずれ | 307,200 bytes = 300KiB |
| 次の境界までの余白 | 1,789,952 bytes = 1.70703125MiB |
| 最初の要求 | 16,777,216 bytes = 16MiB |
| 再試行の要求 | 18,567,168 bytes = 17.70703125MiB |
| 実際のpool先頭 | 421,527,552（2MiB整列） |
| 利用可能なpool容量 | 16MiB |

この2MiBは32-bit guestのbuffer pool extentの配置条件。
[buf0buf.h](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/storage/innobase/include/buf0buf.h#L48)
はsize_tが8bytes未満なら2MiB、64-bitなら8MiBとしている。ホストM1のOSページサイズや
Go heapの整列条件と混同しない。

## 原因を支える3つの一致

1. **元のMariaDB処理。** 固定commitの
   [buf_pool_t::create](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/storage/innobase/buf/buf0buf.cc#L1370)
   は予約後に整列で失う量を算出し、容量不足ならreleaseして要求量を増やしretryする。
   poolの利用とcommitはその判定より後にある。最初の領域はpoolデータとして使われない。
2. **実際に採用した移植処理。** `guest/patches/common-portability.patch` の
   my_large_virtual_alloc向けWASM分岐はposix_memalign(4096)の直後に全域memset(0)を行う。
   my_virtual_mem_reserveはその関数へ委譲し、WASMのreleaseはfreeする。
   取得した2ファイルのbefore hash、patch全体のhash、適用後のafter hashが、全て
   v0.6.0のguest/input.jsonと一致した。上流の未改変挙動だけからの推測ではない。
3. **生成コードと実測。** exact guestのFn18568内に、4096整列確保、zero fill、
   2MiB maskによる不足判定、Fn153による解放、size増加と再試行の対応する制御フローがある。
   同じ箇所が参照する2つのbuffer-poolログ文字列を生成済みDataSegsから復元し、元ソースと
   照合した。さらに前回全6子のアドレス・2つの長さが、上の整列式へ厳密に一致した。

Fn18568全体をbuf_pool_t::createと命名したのではなく、内部にインライン化された該当領域を
特定した。exact symbol mapや新規のfreeイベント計測は行っていない。
今回の結論は、pinned source/patch/generated control flowと既存traceの対応による。
同じアドレスだから同じ生存中のallocationである、とは扱わない。

## どこを改善候補にするか

最初から必要な整列を満たせれば、今回の形の16MiB要求に対してreserveをやり直す理由がなくなる。
ゼロ化量の計算上は33.707MiBから16MiBへ減る可能性がある。ただし、別のallocator挙動や
paddingが発生するので、これをRSSの削減量や速度改善として扱わない。

候補はbuffer poolの確保に限定し、全てのposix_memalign要求を一律に変更しない。
2MiBを埋め込むなら対象guestのextent定義との一致を保つ必要があり、64-bit側へ一般化しない。
また、上流my_large_virtual_allocはzero-filledの契約を持つ。単にmemsetを取り除く案や、
reserveからcommitへゼロ化を移す案は、他のcallerや再commitの意味まで変えるため今回選ばない。

前回の最初のclearは中央値1.198ms、2回目は0.441msだった。
一方をなくしても残るclearが初回アクセスの費用を引き受けるため、1.198ms全部を節約できるとは
限らない。期待値を過大に置かず、試作する場合は同じfixtureでallocation数・zero bytes・
Fork CPU/wall・RSSとSQL独立性を比較し、効果がなければそこで停止する。

**正規の変更対象はWASM向けの確保処理（guest移植層）。** GoのMemoryFillを速くする変更ではない。
採用可能な実装にはguest再ビルドと生成Goへの反映が必要になる。
ただし効果を先に調べるなら、生成Goの該当buffer-pool予約callsiteだけをoverlayで2MiB整列へ
変える診断用試作ができる。これならguest再ビルド前に効果とallocatorの挙動を観測できる。
その試作は元Cの変更・再生成との同一性を証明せず、採用候補にはしない。
効果がなければそこで止める。この次の試作の実行条件・予算は別に固定する。
本調査は4つの小さな上流ファイルを取得し、既存コードとtraceを照合しただけで完了した。
400MBのcorresponding-source archive取得やguest再ビルドは不要だった。

## 入力・検証・再現

- product source_commit: `b3b3b46a8807482ad3f96725af86e031fe369b01`（v0.6.0）
- tag_object_sha: `b57183b08d48884840111e8b53daa500734337f0`
- MariaDB source_commit: `83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e`
- guest SHA256: `8f6177627855232d096cfb3987d94e35c19fc4fc0c7f32ca8c69ff9fd4990a40`
- trace/report source_commit: `d6e9249906b38ed1cc842865fda4b18364bd26c8`

[照合結果](zerofillcause/results/correspondence.json)に4つの上流URL/hash、採用patchのbefore/after
hash、生成コードhash、復元したログ文字列、全6子の計算を保存した。
[checksum](zerofillcause/results/SHA256SUMS.json)で固定し、[check.py](zerofillcause/check.py)で検査する。

cleanup後も保存済みreceiptのhashと計算を読み取り専用で確認できる：

```sh
python3 benchmarks/zerofillcause/check.py --receipt-only
```

完全なsource照合を再実行する場合は、JSONに列挙した4ファイルをexact upstream commitから
取得し、upstream/以下へ同じ相対パスで置く。そのコピーpatched/のmysys/my_largepage.cと
mysys/my_virtual_mem.cへ、固定productのcommon-portability.patchの該当2節だけを適用する。
Gitにproductとtraceのcommitが必要（後者はexperiment/zero-fillで公開済み）。

```sh
python3 benchmarks/zerofillcause/check.py --upstream upstream --patched patched --check
```

source照合とreceipt-onlyの両方、Python syntax、diff、public-source boundaryを検査。
観測内容を変える実装がないため、Go runtime/SQL/CIの再実行はしていない。
product/API/guest/generated/releaseファイルの変更・mainへのmerge・最適化採用はない。
