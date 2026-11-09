# #131/#134 — native glueの所有分離

2026-11-10。**承認された5ファイルの分離を完了。準備後の全sourceは分離前と一致した。**
次に検討する上流変更を自前コードから区別できるようになったが、MariaDB内部依存や総更新費用が減ったという判定ではない。hostへの状態移設、TIME修正の除去、製品採用は今回の変更に含まない。

実装source_commit：`a6ccc0713d7c8875a70707e525c51a8283981695`。
比較元：`fee63426c77937306eb8eea887aeb22a792616f5`。
入力：13.2.0/native-text、MariaDB source_commit `c9f28ba0afec6d29e4688255dce8caaf7e91233d`。
[機械可読結果](comparison.json)は実装commitを固定する。後続の記録commitを実行候補へ読み替えない。

## 変更と検証

- 旧native overlayから追加5ファイルの全hunkを分離し、最終本文を`guest/native/`へ移した。残る既存ファイル15個のpatch区画は元とbyte単位で一致する。旧13.0.2入力は歴史的比較用としてそのまま残す。
- 13.2 descriptorに`native_glue`と配置stageを追加。上流diffの前後hashと、独立glueのsource/hashを別々に検査する。配置先が存在する場合は同じbytesでも上書きせず失敗する。
- 全input/配置先を検査してから書込み、symlink、path逸脱、patchとの対象重複、内容改変、古いreceiptを拒否。receiptには5ファイルの最終hashを記録する。
- 256 focused tests / 65 subtests、変更Python構文、公開source検査6,895ファイル、diff検査PASS。新しい負例を両selected workflowに追加した。CI自体は提出していない。
- 分離前・分離後の実際の準備処理を同じhash検証済みarchiveで各1回実行。全32,835項目の内容・mode・symlink先が一致し、全体hashは両方`8d5c563674b23573e20297ab9534c227b4c21925f29a33cf26485c7e1b13aa70`。`modified_files`も一致。
- 12.3.3/13.0.2 descriptors、canonical `guest/source.patch`、stable入力、既存binding、installerの照合条件は変更なし。全guestの再build・runtime実行・CIは0。

最初のunit実行では、synthetic producer fixtureがsourceに存在しない既存ファイルまで記録して失敗した。fixtureをsynthetic本体と実際に配置したglueに合わせて修正し、全256件を再実行した。production側のpostimage検査は弱めていない。歴史的receipt JSONも書き換えていない。

## 境界と費用

今回は自前glueの所有・入力検査を一度整理した費用。今後の版登録では共通の5ファイルを参照し、上流変更との衝突調査を分けられる。controllerのqueue/timerやprepared内部の保存/復元は同じ場所に残り、版更新時の意味上のレビューは必要。
独立glueの登録・配置検査は追加の保守対象でもある。変更行数を削減率にせず、総工数改善は引き続き未確定とする。人の作業時間を計測していないため推定人時や節約率は記載しない。

**入力identityは変わった。** 旧producerのreceiptを現入力に渡すと`selected preparation input identity mismatch`で拒否することを確認した。既存public installerのhost/producer選択一致も維持している。そのため、このbranchで古いCI handoffをそのままinstallすることはできない。source一致を理由にreceiptを再ラベルしたり、許可リストを拡げたりしていない。
次の既定producer/公開受入れcohortで入力とbindingを揃える。今回の所有分離だけのために追加buildは行わない。既存CIのPASSは元candidateの証拠として残る。

残件：#132の設定・実fault/join・元oracle・wheel両OS受入れ、通常CI配置、#128総費用、consumer/性能・最終監査。#138は停止/未免除。この限定完了で#65/#131/#134を閉じない。

## 再現

過去のローカル作業場所は入力ではない。上記2つのcommitから、それぞれ`experiment/`で始まる別branchの一時checkoutを作る。各checkoutで次を実行する（`OUTPUT`は異なる空の場所、`CACHE`は共有してよい）。

```sh
python3 scripts/git_identity.py inspect HEAD
python3 scripts/prepare_guest.py --engine 13.2.0 --profile native-text \
  --work-dir "$OUTPUT" --archive-cache "$CACHE"
```

比較には既存`tests/compare_selected_preparation.py`の`inventory`を使う。candidate checkoutから、準備結果2つを引数で指定する。

```sh
python3 - "$BEFORE/source" "$AFTER/source" <<'PY'
from pathlib import Path
import runpy, sys
inventory = runpy.run_path('tests/compare_selected_preparation.py')['inventory']
before, before_hash = inventory(Path(sys.argv[1]))
after, after_hash = inventory(Path(sys.argv[2]))
different = [p for p in sorted(before.keys() | after.keys())
             if before.get(p) != after.get(p)]
print(len(before), len(after), before_hash, after_hash, different)
assert not different
PY
```

実施時は所有上限6GiB、空き下限12GiB、各準備15分上限で実行した。保持するのはcommit、比較hash、差分一覧とこの手順。展開source・archive・venv・一時checkoutは検証終了後に削除する。
