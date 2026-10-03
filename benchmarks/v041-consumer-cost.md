# v0.4.1 investigation: released generated-Go consumer cost

## Question and boundary

公開済み `v0.4.0` を普通の Go module dependency にしたとき、利用者が実際に払う
取得・compile・cache・binary の費用を測った。production runtime、generated source、
MariaDB build、配布方式は変更していない。

- 全 lane 共通 baseline: **`39537e9bb2fbbc28315e1ff672960ad734a9e399`** (`v0.4.0`)。
- branch: `experiment/v041-consumer-cost`。
- Apple M1 / 16 GiB、macOS 27.0.1 arm64、Go **1.26.8**。
- Go の通常 parallelism、CGO_ENABLED=1、GOWORK=off。
- 全取得・compile・測定は fan-out の共通 exclusive lock 内で順次実行した。
- cold は独立した空の **Go build cache**。OS page cache は flush していない。
- 少数の診断 trial。percentile、Linux 性能、最小 RAM の保証ではない。

外部 project `example.com/mariamem-consumer` は public
`github.com/masahitojp/mariamem@v0.4.0` を require する。`replace`、private proxy、
GOSUMDB 無効化、compiler workaround、`-p 1` は使わない。
`proxy.golang.org,direct` / `sum.golang.org` による通常取得で、Origin が上記 tag SHA
と一致した。consumer は Options{} / SELECT 1 / InnoDB CREATE・INSERT・UPDATE・
SELECT・DELETE / Close のみ。binary 実行 2 回と全 consumer test は成功した。

再現 runner: [spikes/consumer-cost/README.md](spikes/consumer-cost/README.md)、
[measure.py](spikes/consumer-cost/measure.py)。
小さな機械可読 evidence: [v041-consumer-cost.json](v041-consumer-cost.json)。
raw stdout/stderr/time、cache、binary は owned work root の
`consumer-measurement-1/` に保持し、Git には含めない。
raw `result.json` SHA-256:
`b9378518eec974685299ea08db6c19a73520e4a3d5c4ad022b4f53127972760a`。
各 log/binary checksum は小さな JSON に記録した。runner の最終変更は zip inventory / checksum
metadata の追加のみで、測定 command/cache boundary は変えていない。

## Module acquisition

module content sum:
`h1:XlvetHnwQjKnf9LRrN7BHIWXcIOYaANp6qd7rJ4EuL8=`。
public zip SHA-256:
`5c7df0e7065a0ac855f3ef36b2f4946369eabe62f54896730b8b7c6fdf01962b`。

| Item | MiB |
| --- | ---: |
| 実際の public module zip | 143.99 |
| 展開された module source / docs / evidence | 328.15 |
| generated-Go directory | 196.19 |
| encoded native images / obsolete provisioning directory | 111.87 |
| mariamem module cache: zip + 展開 + download records (logical) | 472.14 |
| 同 cache (`du -sk` allocated) | 473.43 |
| driver dependencies / sum records を含む全 module cache (logical) | 473.01 |
| 同全 cache (`du -sk` allocated) | 474.54 |

1 回の clean module acquisition は **17.46 s wall / 3.44 CPU-sec**。
依存取得・tidy は別に 1.67 s。network と展開・hash 検証を含む local observation であり、
一般的な download 時間の保証ではない。既に installed の Go SDK を使用し、module-cache
数値に Go toolchain を重複 download していない。

zip member の実測 compressed payload は generated directory **30.06 MiB**、
encoded images **111.17 MiB**、その他 **2.62 MiB**。
encoded images が zip 全体の **77.2%** を占める。
この directory に外部 consumer の import dependency はなく、ordinary Start にも使われない。
一方 Go module は build に使うファイルだけを取得する仕組みではないので、配布内の dead
image source も利用者は取得する。本 lane では削除も module 分割もしていない。

## Build / test / edit

`/usr/bin/time -l` の CPU は descendants を含む。reported maximum RSS は
**同時 compiler 群の合計 peak ではない**。2 trial の range を p95 と呼ばない。

| Boundary | Wall | CPU-sec | Reported max RSS |
| --- | ---: | ---: | ---: |
| 独立 cold `go build`, trial 1 | 96.26 s | 272.91 | 2.44 GiB |
| 独立 cold `go build`, trial 2 (clean CI-like repeat) | 99.85 s | 278.05 | 2.76 GiB |
| 独立 cold `go test ./...` | 133.50 s | 408.55 | 2.68 GiB |
| 即時 warm `go build`, 2 回 | 0.21–0.38 s | 0.41–0.44 | 34–36 MiB |
| warm `go test` (cached result) | 0.43 s | 0.50 | 37 MiB |
| warm `go test -count=1`, 2 回 | 1.27–3.51 s | 1.16–1.33 | 561–562 MiB |
| consumer-only change `go build` | 1.44 s | 2.26 | 718 MiB |
| consumer-only change `go test` (not cached) | 1.54 s | 1.33 | 559 MiB |

cold test は cold build の後の同じ cache ではなく、**別の空 cache**。
warm executed test は SQL / guest startup / shutdown / test binary preparation も含む。
consumer-only edit は main と test が実際に参照する marker を変更した。
cached test と実行された test は分離し、遅い warm trial も削除していない。

各 cold build 後の build cache は logical **518.39 MiB**、allocated **523.33 MiB**。
cold test 後は logical **530.45 MiB**、allocated **537.53 MiB**。
通常編集で毎回 generated dependency の cold compile を払う現象は観測しなかった。
独立 CI job に cache がない場合は約 **1.6 分の build / 2.2 分の test** が必要だった。
small-RAM CI の OOM 境界は未測定。今回の成功を 3 GiB あれば常に十分という保証にはしない。

## Final consumer binary

control は database/sql + 同じ MySQL driver をリンクした compile-only program。
違いは mariamem の依存と consumer の小さな Start/CRUD/Close 関数で、厳密な link-map 配賦ではない。

| Binary | Normal | `-ldflags='-s -w'` |
| --- | ---: | ---: |
| driver control | 6.82 MiB | 4.63 MiB |
| public mariamem consumer | 81.25 MiB | 54.47 MiB |
| approximate mariamem contribution | **74.43 MiB** | **49.84 MiB** |

196 MiB の generated source がそのまま executable に残るわけではない。
ただし stripped でも約 50 MiB 増えることは、test / application binary の実費である。
size optimization はしていない。

## Previous consumer evidenceとの比較

[前回の consumer report](direct-link-consumer-experience.md) は unpublished synthetic
file-proxy module で、encoded images / repository docs 等を意図的に除いた測定だった。
今回は公開 release module を checksum 検証付きで使ったため、取得サイズは直接同一境界ではない。

| Boundary | Previous synthetic fixture | Released v0.4.0 |
| --- | ---: | ---: |
| generated source | 196.16 MiB | 196.19 MiB |
| zip | 28.54 MiB | 143.99 MiB |
| cold build, Go1.26.8 | 109.34 s | 96.26 / 99.85 s |
| independently cold test | 128.97 s | 133.50 s |
| warm build | 0.19–0.42 s | 0.21–0.38 s |
| consumer edit build/test | 1.43 / 1.61 s | 1.44 / 1.54 s |
| stripped approximate contribution | 49.60 MiB | 49.84 MiB |

compile / cache / binary の大分類は以前の結果と一致する。
公開 module になって qualitatively 違うのは **取得物に unused encoded images が残る**点。
別 machine / toolchain / OS の性能や現在 pgmem の優劣は、この表から推論しない。
新たな pgmem campaign は実施していない。

## Product decision inputs

- generated source 196 MiB は、普通の cache 利用で毎回の開発作業を阻害するという証拠ではない。
- cold compile の 96–100 s、cold test の 134 s、数 GiB 級 process RSS、約 50 MiB の
  stripped binary 増分は現実の cost。cache を持たない多 job CI には予算が必要。
- module acquisition は 144 MiB、zip+展開約 472 MiB。generated dependency だけの問題と
  default に不要な image packaging の問題を分離できた。
- 最小の次の human decision は、Lane E の ownership audit と合わせて dead image source /
  provisioning artifact を release module から外す bounded cleanup を採用するかどうか。
  runtime redesign / module split / generated-source削減の必要性は実証していない。
- supported Go1.26.8 で public unchanged consumer は build/test/SQL 成功。Go1.27.0/1.27.1
  arm64 の既知 upstream compiler issue の workaround や新たな version matrix は行っていない。
- Linux build の時間・memory、CI minimum RAM、非協調 execution の回収はこの lane の未測定範囲。

検証: public consumer 2 cold builds、独立 cold test、warm/incremental executed tests、
runner syntax、zip inventory、`git diff --check`。runtime の変更がないため canonical benchmark /
全 dogfood の再実行は追加していない。

## Verdict

**`CONSUMER BUILD COST NEEDS POLISH`**

Go の warm/edit 体験は実用的。cold/CI/binary 費用は明示すべきで、特に normal runtime に
使われない images の取得負担は bounded packaging cleanup の検討に値する。
source size の見た目だけを理由に direct-link を否定する結果ではない。
