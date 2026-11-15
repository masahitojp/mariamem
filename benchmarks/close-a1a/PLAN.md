# Close plus A1a finite comparison

Base ead4101e2b40983c818ed843899e17a6a9196a7a; product #203-205.
Only A1a directory allocation removal from 4aa460d6001dc981423cef91e5f63f25e0ab48bb is applied. Legacy cleanup fields/helpers remain for allocation-only isolation, not final product cleanup. No A2/B changes.
Baseline uses a Go overlay restoring only mariamem.go from the base. Same compiler, harness and cached generated packages. Identity checked before builds; baseline overlay source pinned. Candidate focused root/mariamemtest/host tests precede measurement.
480 children, P/cap 1/1,1/2,2/2,2/4, sync and stop modes. Each cell/mode: baseline A/A and baseline/A1a A/B, six pairs. 16 warmups +192 main =208 processes/99,840 children. Within A/A identical binary/path/args/env. Randomized job order seed119, alternating pair order, adjacent pair members,150ms pause. No adaptive repeats/exclusions.
Primary batch wall includes final cleanup and Snapshot.Close. Existing actual guest SQL, isolation, lease and mapping restoration checks mandatory. Report paired wall/CPU/RSS and A/A variation without subtracting noise. Shared Mac only; no adoption/merge or API change claimed. Preserve evidence then clean owned scratch. Guard12GiB budget/free12GiB, timeout5400s.
