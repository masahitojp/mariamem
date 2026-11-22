## InnoDB起動とrollback segment復元の現行比較
3831bd3c固定。前回と同じ直列70ケースで通常・ホスト時計・ゲスト時計と関数計時を各4回、21 Fork/回。mysql_server_init、InnoDBプラグイン、srv_start、辞書、トランザクション一覧、rollback segment復元、Ariaを計時。各項の入れ子と回数を確認し、1 Fork 2.4 msの候補を選べるか判定。測定と判断で終了し、改善実装は別判断。
