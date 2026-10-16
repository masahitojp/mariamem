# Adopted main: Product Verification and Human Review

2026-10-17。**依頼した限定性能確認はCOMPLETE。** 公開済みv0.5.0のsource
`44100ec676c8c9064f32f3a01bd9a990d487bb61`と、最終Qualification済みの採用構成
`c97e55fc065f6ee7b560325077726da53e5d95d7`をmacOS arm64で比較した。
元の262実行と、悪化ケースに絞った追加12実行が完了。実装変更はない。

## Human Review

**今の判断は、この性能のトレードオフを受け入れ、現採用構成のまま次のリリース準備へ
進むか。私は進むことを推薦する。** 準備を再利用する4テストのLight／10 MiBでは、
Fork全体が約13〜36%短縮した。Pythonの準備→Snapshot→複数の独立した子→全Closeも、
小規模27.3%、中規模7.9%、100 MiB・子16個2.9%短縮。Snapshotは約半分になり、
メモリの利益も大きい。既存SQL・transaction・隔離・回収oracleは274実行で通過した。

**最も強い反論は、100 MiBを毎回用意するGo Freshで遅い結果が残ること。**
最初は+29.0%、同条件の追加3対では中央値+1.9%、元の試行を含む全4試行では+7.2%。
CPUも全4試行の中央値で+6.3%増えた。この不利益をばらつきだけとは説明できない。
それでも、主目的のmigration／fixture再利用と資源削減の利益を優先し、今回さらに修正を
追加することは推薦しない。Go Freshの一律高速化は主張せず、大量投入の時間を最優先する
用途では、この比較をそのまま確認できるようにする。

## Evidence and remaining conditions

- [全表・区間・入力・生データ](../../benchmarks/main-product-verification.md)。Fresh／Fork、Go／Python、通常／資源試行を分離。元の悪化も除外せず保存した。
- [100 MiB Goの追加確認](../../benchmarks/main-product-verification.md#adverse-100-mib-go-case-and-bounded-repeat)：Forkの全4試行は中央値−9.7%。Freshの遅さは主にデータ投入とSQLで、約1秒の起動待ちとは区別できる。実装の費用と実行条件の寄与は未分離。
- [以前遅かった小規模workflow](../../benchmarks/main-product-verification.md#previously-slow-small-workflow)：新しい30回ずつの反復で候補は全体1秒超0件。通常・資源の最大は591／617ms。原因解明やtail不在の証明ではなく、限定反復で利益が維持された結果。元の1540ms試行は保存したまま、一般的な不確実性だけで再調査を必須化しない。
- [memory／allocation／回収](../../benchmarks/main-product-verification.md#go-memory-and-reclamation)：Go 10 MiB ForkのRSS中央値664→177 MiB、累積allocation670→117 MiB。Go mapping作成・解放240個が一致。RSSとheap、累積確保量を区別した。
- macOSでの性能判断。Ubuntuの速度は未計測で、PASSに数えない。両OSの機能・配布物・独立生成の[最終Qualification](main-storage-qualification.md)は別の既存証拠である。

この判断で採用済みのAPI／所有／共有host crash domainを変更しない。追加hash削減、
一般共有メモリの保証拡張、接続数調整を新しい必須残件にも加えない。
同一条件で大規模Freshの持続的な大幅悪化や通常利用のSQL／隔離の失敗が新たに再現した場合は、
その具体的な境界を修正対象として再判断する。今回、その修正実装や広い原因調査は行っていない。

推薦は次工程への移行であり、公開承認ではない。main merge、版の選択、タグ、Release／PyPI公開は
今回実行していない。Human Review後に版と公開が明示された場合は、変更した最終sourceに対する
既存release workflow／exact-source guardへ渡す。
