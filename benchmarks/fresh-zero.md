# Fresh-zero初期化：構築時の節約はreadyまでにほぼ消えた

2026-11-01、[Issue #64](https://github.com/masahitojp/mariamem/issues/64)。
**固定した小試作は完了。大きな保持メモリ削減策としての単独製品化は見送ることを推奨する。**
初期構築の明示clearを省くと直後のguest residentは約8.55MiB減ったが、DB readyでは
差が約0.19MiBに縮んだ。Fork全体のCPU改善も一貫しない。
最も強い反論は、壁時計のFork時間が5/5組で改善した点。小さなlatency改善候補として
価値は残るが、fresh-memory契約を生成器・hostに維持する追加責務まで今採用する根拠は弱い。
後日この初期化境界を変更する際の候補として保存し、今回は追加計測や製品実装へ広げない。

## 問いと変更

hostは新規のanonymous mappingを確保し、生成されたconstructorへ渡す。
そのメモリは最初からゼロなのに、`p7.Fn67` はdata segment配置後、offset15,244,864から
8,982,576bytes（8.566MiB）を明示的にゼロ化していた。
このclearを新規mappingの初回構築に限って省くと、CPU・RSS削減がreadyまで残るかを検証した。

実験はGo overlayだけを使用し、canonical guest patch / host / generated sourceは変更していない。
[overlay generator](freshzero/overlays.py)が次を行う。

- hostの新規mapping作成経路から、実験専用 `NewWithFreshZeroMemory` を呼ぶ。
- 汎用の `NewWithMemory` はfresh=false、新規専用はfresh=trueとして共通constructorへ渡す。
- Moduleに一時的なfreshフラグを設け、候補だけが該当する一つのclearをそのフラグで省略する。
  初期化の終了時にフラグを落とし、workerへ持ち越さない。
- baselineにも同じ入口・field・フラグ消費を加えるが、該当clearは従来どおり実行する。
  candidateとの差はこのclearの条件だけ。
- 両方にreserve/construct観測hookを加える。本計測ではhookを設定せず、内部の計時も行わない。

新規専用入口は「入力が本当にfresh」を自動判定しない。host所有者がその前提を満たす
限定経路であり、汎用・再利用・Snapshotメモリへ拡張する設計ではない。
baselineも同じ診断用構造を持つため、未変更release binaryとは呼ばない。
#63のbuffer pool整列や#56のmprotect batchingは一切混ぜていない。

## 結果

Apple M1 / 16GiB / macOS27.2 / Go1.27.3、CGO0・GOMAXPROCS8。
1,000行fixture、各processで四つの子を順にForkして保持する。並行Fork throughputではない。

診断pilotは各variant一つのprocess・4子。mincoreでページ内容を読まずにguest residentを
調べ、別processからpsでRSSを記録した。construct時間は観測用の停止より前に区切る。

| 診断pilot（4子の中央値） | 元のclear | fresh時だけ省略 |
|---|---:|---:|
| reserve直後のguest resident | 0MiB | 0MiB |
| construct直後のguest resident | 15.109MiB | 6.563MiB |
| construct wall | 1.775ms | 1.064ms |
| construct CPU | 1.903ms | 1.192ms |
| DB readyのguest resident | 75.391MiB | 75.203MiB |

構築時の節約8.547MiBの大半がreadyまでに消えた。後続初期化によるページ利用と整合するが、
全read/write追跡や対象範囲のページidentityを保存していないので、どの後続命令がどのページを
書いたかまで確定したわけではない。mincore residentはprocess RSSとも別の量である。

本計測は診断hookなし、5組のfresh-processを順序交互に実行。全40子を採用し除外・追加反復なし。
下表の時間は「processごとの4子平均」を5process間で中央値集計する。
RSSは各processのpost-GC baselineから4子保持までの増分の中央値。

| 本計測 | 元のclear | fresh時だけ省略 |
|---|---:|---:|
| Fork wall | 36.679ms | 35.286ms |
| Fork process CPU | 48.103ms | 49.207ms |
| 4子保持時のRSS増分 | 312.422MiB | 311.641MiB |

- paired wall: -5.13%, -3.10%, -1.29%, -4.15%, -0.62%。全5組で短く、中央値-3.10%。
- paired CPU: -5.62%, +0.11%, -1.06%, +1.06%, +5.13%。2組改善・3組増加、中央値+0.11%。
- paired RSS増分: 全5組で0.56–1.03MiB小さい。保持メモリの改善は1子あたり約0.2MiBの規模。

中央値の差とpaired percentageの中央値は異なる統計量。CPU退行を確定する証拠とも、
確実な速度改善率とも扱わない。Fork CPUは保持済みの子のbackground処理も含むprocess全体。
SQL・RSS checkpoint・prepare・Closeは本計測のFork区間外。非隔離のローカルMacで、
過去の別batchとの絶対時間比較やLinux/release toolchainへの一般化はしない。
診断pilotのFork時間は途中の観測停止を含むので性能比較に使わない。
rawのready timing=0は未計測のsentinelであり、summaryではnullとしている。

## 正しさと未検証

PASS:

- 両variantのconstructor selftest。fresh mappingと、clear対象全域を0xa5で埋めた汎用入力で
  全域のzeroを検査。generic dirty入力はclearが残る。初期data segment三つのSHA256一致、
  freshフラグの消費、mapping cleanupも検査した。selftestは別processで、本計測のページを触らない。
- 正常の診断pilot2、意図的なseed破損を検出するnegative2。
- 本計測10process・40子のpristine COUNT/SUMと独立更新。active mappings/RW/reserved bytesは
  全process終了時にゼロ、owned scratchも空。
- 分析4変異テスト（pair欠落、stage欠落、constructor control欠落、mapping leak）、
  compact checksumとsummary再計算。public-source checkもPASS。

未実施: Linux・race・一般的な再利用memory対応・generatorの正規変更・guest再生成・製品採用。
現在の初期化コードについての限定結果であり、将来data segmentが対象範囲へ重なっても
省略できるとは主張しない。採用するなら既知ゼロの由来とinitialization順序を機械的に
維持する必要がある。公開API、版、Qualification、releaseは変更しない。

## 正確な入力と再現

- product source_commit: `b3b3b46a8807482ad3f96725af86e031fe369b01`（v0.6.0）
- tag_object_sha: `b57183b08d48884840111e8b53daa500734337f0`
- measured harness source_commit: `b31475dc2589df645bc3a31a3a51c5c1db246168`
- build前に `git_identity.py` とclean HEADを検査。2binaryとも同じsource・vcs.modified=false。
  [inputs](freshzero/results/inputs.json)に元ファイル/overlay/binaryのhashを保持。
- worktree作成と最初の依存取得はsandboxのGit書込み/DNS制限で失敗し、権限付きで再実行。
  runtime試行の選別・再実行はない。

build/tempを削除した後にも、このreport refだけで検証できる。

```sh
python3 benchmarks/freshzero/analyze.py --check
python3 -m unittest discover -s benchmarks/freshzero -p 'test_analysis.py'
```

runtimeを再現する場合は、measured sourceをcheckoutしたdisposable workspaceを作る。
`experiment_workspace.py prepare` の `--min-free-gib 16 --budget-gib 8` を使い、owned worktreeから:

```sh
cp benchmarks/freshzero/run.py ../evidence/run.py
python3 ../evidence/run.py --phase build
python3 ../evidence/run.py --phase pilot
python3 ../evidence/run.py --phase measure
```

runnerはGo1.27.3/darwin-arm64を固定する。新runの分析にはreport refのanalyze.pyを用い、
`--collect <evidence> --results <new-output>` を指定する。既存input receiptは書き換えない。
`--check`は読み取り専用。時間値のbyte一致を要求しない。

[compact observations](freshzero/results/observations.json)、[summary](freshzero/results/summary.json)、
[checksums](freshzero/results/SHA256SUMS.json)を保存。rawは専用ref
`evidence/fresh-zero-20261101`、commit
[`50c1c120c22fcb71fc9ee7e0d5eb61adf39ae6bf`](https://github.com/masahitojp/mariamem/blob/50c1c120c22fcb71fc9ee7e0d5eb61adf39ae6bf/raw.tar.gz)
の `raw.tar.gz`（8,117bytes）。SHA256:
`def362445700bd26d4bac3eeaebb492a2f964ff3d1c1c2cd15cbcc3c3dd40ae4`。
39ファイル分の元JSON・checkpoint RSS・build/selftest log・runner・member checksumを含む。
rawやexploratory historyをmainへ一括mergeする提案ではない。
