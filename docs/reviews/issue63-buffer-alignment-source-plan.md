# Issue63：pool reserveに限定するguest変更案

**提案は3ファイルのWASM専用拡張。既存のallocator入口は4KiB整列のまま残し、
buffer poolの1か所だけが必要なextent alignmentを指定する。**
[Issue63](https://github.com/masahitojp/mariamem/issues/63)の設計checkpointであり、
guest実装・再ビルド・採用の完了記録ではない。

最も大きな懸念は、強い整列条件によるallocatorのpaddingと低メモリ時の失敗挙動。
前の試作で時間改善は小さく、効果を一般化できない。だから全callerの一律変更や大規模な
allocator設計変更を避け、既存のzero-filled契約と解放方式を維持する。

## 確認した固定ソース

product source_commit `b3b3b46a8807482ad3f96725af86e031fe369b01`、
MariaDB source_commit `83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e`。
[6ファイルのsource/hash receipt](../../benchmarks/forkcompare/results/source63.json)。

- `mysys/my_virtual_mem.c:42–59`: WASMのreserveは既存の `my_large_virtual_alloc(size)` へ委譲。
- `mysys/my_largepage.c:433`＋採用済みcommon-portability.patch：4KiB整列確保後に全域ゼロ化。
  元の関数コメントもzero-filledを要求する。
- `storage/innobase/buf/buf0buf.cc:1374`: buffer poolのreserve呼出し。
  整列で容量が不足するとrelease/retry。commitはその後。
- `storage/innobase/include/buf0buf.h:48–50`: `innodb_buffer_pool_extent_size` は
  sizeof(size_t)<8で2MiB、それ以外は8MiB。
- `mysys/my_virtual_mem.c` の採用済みWASM releaseは `free(ptr)`。
  poolのreleaseは整列後の内側アドレスではなく、確保で返された `memory_unaligned` を渡す。
- `include/my_sys.h` にallocator宣言、`include/my_virtual_mem.h` にreserve/commit/release宣言。

2つの移植済みCファイルはpatch適用前後のhashをv0.6.0 guest/input.jsonと一致確認。
他4ファイルは固定commit URLから取得しhashを記録した。これは対象の予約・解放経路の照合であり、
上流全体のcaller censusや正規ビルドの代わりではない。

## 具体的な案（未実装）

| 変更対象 | 変更 |
| --- | --- |
| `mysys/my_largepage.c` | WASM専用 `my_large_virtual_alloc_aligned(size_t *size, size_t alignment)` に既存のposix_memalign＋memset処理を抽出。既存 `my_large_virtual_alloc` のWASM分岐はalignment=4096で委譲する。 |
| `include/my_sys.h` | 同じWASM条件内で新しい内部関数を宣言。利用者向けGo/Python APIは追加しない。 |
| `storage/innobase/buf/buf0buf.cc` | pool reserveの1か所だけ、WASM時は新関数へ `innodb_buffer_pool_extent_size` を渡す。必要な宣言はmy_sys.hを明示include。非WASMは既存reserveのまま。 |

概念上のpool側の分岐：

```cpp
#if defined(__EMSCRIPTEN__) || defined(__wasi__)
    memory_unaligned= my_large_virtual_alloc_aligned(
        &size, innodb_buffer_pool_extent_size);
#else
    memory_unaligned= my_virtual_mem_reserve(&size);
#endif
```

WASMでは現行reserveがallocatorへ直接委譲しているため、この呼出しに限定して新入口を使う。
新しいvirtual_mem APIを全platformへ広げる必要はない。
2MiBの数値を呼出し側へ重複定義せず、pool自身のextent定義を使う。

守る条件：

- posix_memalign失敗時はNULL、成功時は要求size全域をゼロ化。サイズ値を勝手に増減しない。
- 旧入口のalignmentは4096、他callerを一律に2MiBへ変えない。
- poolの既存retry/commit/decommit/release経路を残す。低メモリ時の失敗を隠さない。
- zero-fillをcommitへ移さず、COW/shared memoryやhost memory protectionには触れない。
- 新しいalignmentの入力は内部の固定定義。将来一般化する場合の任意入力policyはここで持ち込まない。

## 次に正規candidateを作る場合の検証と費用

1. 別の `experiment/buffer-alignment-source` で `guest/experimental.patch` として最小変更を作る。
   canonical `guest/source.patch` は採用前に変更しない。
2. helperの成功/確保失敗時のNULL・zero-fill・size不変と、旧入口の4KiB整列をfocusedに確認。
   pool側の返却アドレスがextent境界に乗り、既存freeに元のpointerが渡ることを確認。
3. 正規guestの1 build→Go再生成→host buildを行う。旧overlayのreceiptを流用しない。
4. 同じ小fixtureで1回の16MiB pool zero化、SQL初期値・独立更新・cleanupを確認し、
   元版とのbounded比較を行う。低メモリ/失敗経路が安全でなければ採用しない。
5. 効果が消えた場合はその結果で停止する。採用レビュー時に必要なplatform検証を決める。

費用は少なくともguest build1回＋Go再生成1回＋host buildと小比較。
[古い記録](v05-fast-feedback-assessment.md)にはguest build約658秒があるが、別source/環境なので
今回の所要時間の保証にはしない。開始時に取得済みtoolchainとdiskを確認し、まず45分を実行上限の
目安として設定する案。超過時に自動でcampaignを拡張しない。このturnではguest buildを開始していない。

## 再確認

`benchmarks/forkcompare/check-source63.py` を使い捨てworkspaceの `evidence/` へコピーし、
receiptの6 URLの内容を `temp/source63/<path>` に置いて実行する。
スクリプトは2つの採用patchをtempコピーへ適用し、before/after hashと対象経路を再確認する。
元ファイル・照合receiptはSQL調査と同じraw evidence refに保存。
本記録でIssue全体をclosed、製品で修正済み、性能向上保証とはしない。
