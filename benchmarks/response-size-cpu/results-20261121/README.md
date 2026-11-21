# 大応答でのリングとOSパイプの比較

**16 KiBリングの応答側を64 KiBに広げる変更とコピー削減の試作は、今回の結果からは推奨しない。** 256 KiBのSQL結果でCPU増加が6組すべてで再現し、対応中央値は+7.85%（OS同士の絶対差中央値1.64%）、経過時間は−7.95%。CPU増加の帰属は未確定。固定Go候補の採否は保留。事前に定めた原因帰属の条件で終了した。[事前条件](protocol.md)

| 実転送量の平均/SQL | CPU差 | OS再測定のCPU差（絶対値） | 経過差 | リング満杯待ち/96応答 |
|---:|---:|---:|---:|---:|
| 8 KiB | −0.65% | 2.64% | +4.87% | 18 |
| 16 KiB | −5.42% | 2.69% | +3.18% | 74 |
| 32 KiB | −4.80% | 1.46% | −0.15% | 184 |
| 64 KiB | +6.13% | 1.23% | −5.28% | 422 |
| 256 KiB | +8.39% | 1.91% | −6.75% | 1,569 |
| 512 KiB（元の256 KiB SQL結果） | +7.85% | 1.64% | −7.95% | 3,128 |

最初の比較は検査対象のSQL値を8〜256 KiBとした。Go内部で運ぶ形式は約2倍のバイト数になるため、追加の比較では実転送量を8〜256 KiBに合わせた。各バッチは独立プロセスの8接続×12要求。毎回、全バイトと要求固有の接頭辞を照合した。両方式の読取・書込バイト数は全10サイズで一致。表のCPU/経過は診断なしの6組の対応差中央値。OSとの再比較は同一バイナリを再起動したもの。満杯待ちは診断あり各1バッチで数えた。符号が変わる位置はこの端末・負荷の測定点間に限られる。[全10点](summary.csv)

## 原因について分かったこと

元の256 KiB SQLでは、96件で内部を50,365,909 B運んだ。リングは3,264回読み、3,128回満杯待ちに入った。OSは960回読んだ。リングのコピー総量は100,731,818 Bで、書き込みと読み出し各1回分に一致する。片方を安全に省ける経路は特定できなかった。OS側のコピー回数やパイプ内部の満杯待ちは未計測。診断CSV中のOSの該当カウンタはゼロ初期値。

別の80バッチを同じ回数ずつCPUプロファイルした。リングの総標本98.68 CPU秒中、リングのRead/Writeをスタックに含む標本は5個（0.05 CPU秒）。うち直接のメモリコピーは2個。全体の差ではランタイムの usleep が+7.25 CPU秒で、その中にスケジューラ、プリエンプション、GC停止に関わるスタックがある。リングの満杯待ちが別のスレッドでのスケジューラ負荷を誘発する可能性は残るが、これらの標本を当該リングの通知に結び付けられない。待ち回数は停止した回数で、待機中に消費したCPU時間を意味しない。直接の標本は少なく、プロファイルは各条件1プロセスの補助診断である。[差分](differential.txt) · [リングの直接スタック](ring-io.txt) · [スケジューラの内訳](scheduler.txt)

今回の停止条件により、製品差分、試作後のpgmem由来P1/P8・race・終了試験は発生しない。通常ベンチで確認したCPU差と未確定の原因を分けて扱う。原因調査を再開するなら、特定の満杯待ちから読み手・書き手が再実行されるまでをGo実行トレースで関連付けることが、残る仮説の検証になる。

## 再現手順

macOS arm64、Go 1.27.4、GOMAXPROCS=8、GOGC=100。リング候補a1ce4a7dを専用worktreeに置き、同じ階層にtemp/gotmpとこのevidenceを用意する。新規計測は空の出力先で行う。親be12aeb6のlinked.goを同一ツリーにoverlayしてOS対照を作る。両者のランタイム差分はlinked.goとリング実装。SQLサイズを指定する同一ベンチで、データ生成・接続の後から全要求の検算終了までを計測する。各サイズでOS・リング・OS再測定の全6順列を使う。SQLは固定サイズを埋め込んだREPEATと要求ごとの接頭辞を用いる。

```sh
python3 -B evidence/recipe/build.py os ring os-diag ring-diag
python3 -B evidence/recipe/guard.py . 900 python3 -B evidence/recipe/run.py perf
python3 -B evidence/recipe/guard.py . 300 python3 -B evidence/recipe/run.py diag
python3 -B evidence/recipe/guard.py . 600 python3 -B evidence/recipe/run.py profile
python3 -B evidence/recipe/guard.py . 900 python3 -B evidence/recipe/wire_sizes.py
python3 -B evidence/recipe/reduce.py
go tool pprof -top -unit=ms -nodecount=30 -base evidence/os.pprof evidence/ring.pprof
```
