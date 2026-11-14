# 共有panic: 2実関数に限定した生成pass試作

結論: 実際の小関数/巨大SQL関数でも共有panicを生成できた。小関数の逆アセンブル領域は約13.3%縮小、巨大関数は約4.9%増加。全1010 MemoryEA callを除去し、各関数のpanicを1箇所にできた。巨大関数も縮むという前回合成例の結果は実関数では再現しなかった。2関数の実guest上でのSQL速度/正しさ、製品全体サイズは未検証。

source_commit e5eeaca70d74b16cc34fd16ad4ac3b133529cbd1、Go1.26.10/macOS arm64。baseline runtimeは同guest77b2ab49。純Go ASTの後処理pass prototypeで、上流converterへ組み込んだものではない。元生成Goをparserで読み、Fn13460(close_thread_table、p3)とFn15594(update_single_table、p1)だけを変換。製品helper/guest/SQLの編集なし。

| 対象 | baseline領域bytes | 候補領域bytes | MemoryEA call | 候補panic |
|---|---:|---:|---|---:|
| Fn13460 |6864|5952|157→0|1|
| Fn15594 |42768|44848|853→0|1|

bytesはgo tool objdumpの当該symbol内4byte word数から計算した逆アセンブル領域（literal/paddingを含み得る）。archive全体サイズや配布binaryサイズではない。補助nmは当該toolchainに存在せず、この測定には使っていない。Go1.27.4の旧機械語値とは比較しない。

## 変換の範囲と保証

各アクセスのaddrを一度uint64へ評価、offsetを加えたeaを一時変数に置く。ea+widthとその位置でのatomic MemSize.Loadを比較し、異常時は関数末尾の共通labelへgoto。正常時は元のunsafe dereferenceへeaを渡す。元bodyを内側blockに置き、外側labelへ飛ぶことでGoの宣言越え制約を回避した。bounds値を関数入口へ移動していない。

生成時にaddrのuint32正規化またはuint32範囲定数、offset<=uint32max、width1/2/4/8を検証。これによりこの経路のea+widthはuint64 overflowしない。既存の任意uint64 MemoryEA契約は変更しない。offset overflow/未対応width/未知のaddr呼出/label衝突は拒否するnegative確認に成功。decoderの一般保証を推測して省略していない。

単一MemoryEAの単一assignmentだけを受理。呼出は型変換、unsafe.Add、検証した純粋なUi32/I64_extend_i32_u/I64_rotlのみ許可。未対応構文や残留MemoryEAは失敗にする。任意式を安全にloweringできる一般passではない。対象外の宣言はAST整形でp1の150/p3の611件が同一と確認。実関数では部分store順序を維持する構造だが、実SQL実行の独立検査は次段階。

## 実行検査

同じpassで8アクセスのfixtureを変換。495ケースでbaseline/candidateの戻り値、panic値、メモリ全byteを比較し成功。論理bounds0..16、負addr/端点/幅跨ぎ、最大offsetのnonwrap、grow後のアクセス、unused loadのtrap、先行store保持と後続OOB store阻止を含む。全backing16byteより大きい実アクセスは境界検査で停止する。実guestの2関数はコンパイルと逆アセンブル比較までで、これらfixtureの成功をSQL/worker受入れとしない。Linux実行/比較なし。

初期passは未知のpure cast/shiftを保守的に拒否。定義確認後に限定許可。定数eaがint推論されたため最初の候補compileはFAIL、uint64明示で修正して2対象とも成功。helperは失敗後large-generated-source未登録で自動cleanupを止めたため、再現記録を追加し後続は個別timeoutで実行。最後のvalidator強化後も生成ファイルhash不変を確認。fixture再実行はsandbox cache拒否を経て承認済み再実行PASS。初期失敗ログの一部は再実行により上書きされており、全attemptログ保存とは主張しない。

## 推奨

この限定passを実guestで実行して2関数のSQL結果/worker trapと費用を確認する価値はある。巨大関数のcall除去とpanic共有を低い領域増加で実現したことが理由。一方、全体サイズ抑制・速度は未確立なので、全生成関数へ適用したり現候補へ直ちに置き換えたりしない。次に進む場合も2関数に限定したruntime対照を先に行い、失敗または利益なしなら拡大しない。

再現: 固定sourceのworkspaceをprepareし、Go1.26.10でlower.goをbuild。p3/p3_pure.go→temp/p3.go Fn13460、p1/p1_pure.go→temp/p1.go Fn15594。overlayは元2pathをtempへ対応。compile-initial.pyで両armの2archiveをbuild/objdump（compile.pyは修正後candidateのみの再試行）。verify_untouched.goで対象外宣言比較。fixture.tar.gzのgo.mod replaceをworktreeへ置換しgo test。各build1200秒、workspace8GiB/最低空き8GiB。初回helper以降の専用監視は継続していない。製品への統合/releaseなし。
