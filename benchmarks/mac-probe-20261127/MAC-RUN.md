# 同一ソースのMac計測

現在はMac接続先待ち。Mac実測・OS差の判定は未完了。

対象はmariamem `e00b3ec41f9c5d4ca3f85db4ff73198dbf3613e9`、Go1.27.4、CGO0、GOMAXPROCS8、GOGC100、P1。harnessは同梱tar.gzの固定commit由来。意味検証1、warmup1、通常3、CPU profile1の6プロセスだけを実行する。結果は`evidence/`に出る。runnerはPython3.12以降（tarfile data filter）とGo自動toolchain取得、ネットワーク、localhost bindが必要。Macでは未実行。既存Ubuntuデータと同じSQL／接続／同期Close条件で、生成物とプロファイルの識別情報を保存する。

1. Macに計測対象コミットの**独立したクリーンなcheckout**を用意する。既存の作業変更は上書きしない。既存Gitに対象オブジェクトがあれば専用worktreeも使える。
2. `mac-probe.zip`を展開する。計測パッケージはcheckout外に置く。
3. 以下をcheckoutのルートで実行する。`/absolute/path/to/package`を展開先に置き換える。

```sh
python3 scripts/git_identity.py inspect HEAD
python3 scripts/experiment_workspace.py prepare pgmem-mac-20261127 \
  --branch experiment/pgmem-mac-20261127 --min-free-gib 8 --budget-gib 8
python3 scripts/experiment_workspace.py run --timeout 1500 pgmem-mac-20261127 -- \
  python3 /absolute/path/to/package/mac_probe.py \
  --repo "$PWD" \
  --workspace "$PWD/build/experiment-work/pgmem-mac-20261127/temp/probe"
```

HEADが対象コミットと異なる場合はrunnerが停止する。失敗時もrunnerが途中まで保存した`mac-results.json.gz`を確認する。実行中の別build・benchmark・profilerは避ける。

保持するのは`build/experiment-work/pgmem-mac-20261127/temp/probe/evidence/`のJSON.gz、summary、CPU profile、top/cum、MemoryEA逆アセンブル、ログとchecksums。最終比較のため、このディレクトリをUbuntu側へ渡す。バイナリ・展開ハーネス・コンパイルtempは保持不要。削除前に証跡をtemp外へコピーし、checksumと全6観測を確認する。repoのexperiment-workspace手順に沿ってcleanupを実行する。共有キャッシュは他作業の使用状況を確認して扱う。

CPUはwait4のuser+system、RSSはDarwinのbytesをKiBへ換算。process wallはPython外部起動から終了検出まで（10msポーリングで最大約10msの検出遅延があり得る）。CPU profile付きの時間は通常3回へ混ぜない。profile開始はm.Run内なのでTestMain初回準備全体・最終cleanup全体のCPU帰属には使わない。以前のM1とGitHub macOS runnerを同じマシンとは扱わない。
