# 子Fork起動・Closeの費用帰属

## 調査範囲と終了条件

Humanが承認した残件#2は、子Fork起動と子Closeを計測し、時間を使う処理を特定すること。
最適化・契約変更・接続数調整・100MiB Go Fresh再調査・リリースは含めない。
基点はmain `df90c096a269d448a50ac44ac92f88e47619d58e`、実guestはv0.5.2と同じidentity。
既存Ubuntu246実行は再実行せず、集計済み区間と今回の内訳を区別する。

最初にmacOS arm64で、同じSQL oracleを使い、次を分ける。

- Fork: 所有基準の取得、host準備、DBファイルの接続、linear memory生成、guest起動、ready応答、wire listener。
- Close: SQL pool切断・WaitDisconnected、listener/session停止、guest shutdown、worker join、linear memory解放、descriptor/prepared handle解放、一時ディレクトリ削除。
- 既存Goのchild_closeにはdisconnectが含まれ、既存Pythonは別区間。比較前に揃える。

通常・観測ありを交互に比較し、観測費用を隠さない。CPU profileは別試行とし、
100Hz samplingの分解能を超えて個別の短いCloseの割合を断定しない。
生成Go・guestは変更せず、実験branchの手書きadapter/hostに時刻観測だけを加える。

有限campaign: Go Light/10MiB/100MiB直列4子と10MiB4並列を各3対、
Python sharedhost small/mediumを各3対・100MiBを1対、Lightのfork/close CPU profileを各24子。
機能oracle/identity/cleanup失敗、区間未取得、容量超過なら停止して未完了を記録する。
上限はbuild込み60分、各command300秒。必要な追加確認は同じ区間の具体的不足に限定する。
Ubuntuへの内訳の一般化はしない。native未実行ならSKIPとする。

終了時は各区間の実測、支配的な処理とCPU/待ちの根拠、未特定残差、観測限界、
次の判断を報告する。時間上限到達を調査完了にはしない。
