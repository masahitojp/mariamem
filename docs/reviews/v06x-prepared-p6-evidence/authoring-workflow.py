from pathlib import Path
import subprocess
root=Path.cwd()
old=subprocess.check_output(['git','show','5d729eff7bd64aa5de3d2b5464e728c3a52fb7ed:.github/workflows/prepared-product.yml'],text=True)
base=Path('.github/workflows/routine-canonical.yml').read_text().replace('Canonical routine candidate','Canonical prepared candidate').replace('experiment/routine-canonical-adoption','experiment/prepared-canonical').replace('canonical-routine','canonical-prepared').replace('build/routine-ci','build/prepared-ci').replace('needs: guest','needs: [guest, p5-native-control]').replace('timeout-minutes: 70','timeout-minutes: 120')
anchor='          python3 scripts/build_generated_guest.py > build/prepared-ci/guest-build.txt 2>&1'
base=base.replace(anchor,anchor+'''
          /root/.wasixcc/binaryen/bin/wasm-opt -O2 --enable-threads --enable-mutable-globals --enable-bulk-memory --enable-bulk-memory-opt --enable-exception-handling --enable-simd --enable-relaxed-simd --enable-extended-const --symbolmap=build/generated-release/function.map /work/artifact/mariamem-legacy-eh.wasm -o build/generated-release/mapped.wasm
          cp /work/artifact/mariamem-legacy-eh.wasm build/generated-release/linked.wasm
          python3 -c 'import hashlib,json;h=lambda p:hashlib.sha256(open(p,"rb").read()).hexdigest();assert h("build/generated-release/mapped.wasm")==json.load(open("release/generated-go-inputs.json"))["guest_sha256"]'
''')
start=old.index('  p5-native-control:');end=old.index('  development-runtime:',start);lines=old[start:end].splitlines();new=[]
for l in lines:
 if 'if: github.ref' in l or 'python tests/v06_prepared_p5_compare.py ' in l:continue
 new.append(l)
 if 'python tests/v06_prepared_consumer_edges.py --native-port' in l:
  new.append('          python tests/v06_prepared_p5_compare.py --actual build/prepared-p5-native/consumers.json --native tests/fixtures/prepared-p5-native-macos314.json --actual-environment build/prepared-p5-native/environment.json --native-cext-environment tests/fixtures/prepared-p5-native-macos314-environment.json --actual-edges build/prepared-p5-native/edges.json --native-edges tests/fixtures/prepared-p5-native-macos314-edges.json --accepted-disposition docs/decisions/prepared-consumer-exceptions.md --consumer-exit "$consumer_exit" --output build/prepared-p5-native/matching.json')
base=base.replace('  native:\n','\n'.join(new)+'\n  native:\n')
base=base.replace('      - name: Fixed consumers and source checks', '''      - uses: actions/download-artifact@37930b1c2abaa49bbe596cd826c3c89aef350131
        with:
          name: prepared-p5-native-${{ github.sha }}
          path: ${{ runner.temp }}/prepared-native-control
      - name: Fixed consumers and source checks''')
start=old.index('      - name: Real P1 wire lifecycle');end=old.index('      - uses: actions/download-artifact',start);matrix=old[start:end]
matrix=matrix.replace('          PYTHONPATH: ${{ runner.temp }}/prepared-p1-native/product/python','          PYTHONPATH: python').replace('"$RUNNER_TEMP/prepared-p1-native/mariamem-dev-host"','build/prepared-ci/mariamem-host').replace('build/prepared-p1','build/prepared-ci')
assert 'RUNNER_TEMP/prepared-p1-native' not in matrix
step='''      - name: Canonical installed binding for complete P1-P4 replay
        run: |
          python tests/check_prepared_p1_binding.py --runtime internal/generatedgo > build/prepared-ci/prepared-binding.txt 2>&1
          go build -p 1 -trimpath -o build/prepared-ci/mariamem-host ./cmd/mariamem-host
'''
comparison='''      - name: Exact P5 accepted-exception edges and fresh native reference
        env:
          PYTHONPATH: python
        run: |
          python scripts/check_prepared_consumers.py --host build/prepared-ci/mariamem-host --output build/prepared-ci/selected-consumers > build/prepared-ci/selected-consumers.txt 2>&1
          python tests/v06_prepared_p5_compare.py --actual build/prepared-ci/selected-consumers/consumers.json --native "$RUNNER_TEMP/prepared-native-control/consumers.json" --native-cext tests/fixtures/prepared-p5-native-macos314.json --actual-environment build/prepared-ci/selected-consumers/environment.json --native-cext-environment tests/fixtures/prepared-p5-native-macos314-environment.json --actual-edges build/prepared-ci/selected-consumers/edges.json --native-edges "$RUNNER_TEMP/prepared-native-control/edges.json" --native-cext-edges tests/fixtures/prepared-p5-native-macos314-edges.json --accepted-disposition docs/decisions/prepared-consumer-exceptions.md --consumer-exit 1 --output build/prepared-ci/fresh-native-matching.json
      - name: MariaDB official driver two-case regression
        env:
          PYTHONPATH: python
        run: |
          python tests/v06_install_mariadb_driver.py --output build/prepared-ci/mariadb-install.json > build/prepared-ci/mariadb-install.txt 2>&1
          python tests/v06_prepared_mariadb_probe.py --host build/prepared-ci/mariamem-host --reference "$RUNNER_TEMP/prepared-native-control/mariadb-driver.json" --output build/prepared-ci/mariadb-driver.json > build/prepared-ci/mariadb-driver.txt 2>&1
      - name: Reproduce retained-library symbols and guard failures
        run: |
          python scripts/audit_generated_licenses.py --guest build/generated-release/mariamem.wasm --linked build/generated-release/linked.wasm --function-map build/generated-release/function.map --host build/prepared-ci/mariamem-host --output build/prepared-ci/license-audit.json > build/prepared-ci/license-audit.txt 2>&1
          python scripts/check_prepared_build_guards.py --output build/prepared-ci/build-guard-mutations.json > build/prepared-ci/build-guard-mutations.txt 2>&1
'''
pos=base.index('      - uses: actions/upload-artifact',base.index('  native:'));base=base[:pos]+step+matrix+comparison+base[pos:]
base=base.replace('            build/prepared-ci/gorm','            build/prepared-ci/gorm\n            build/prepared-ci/selected-consumers/*.json')
Path('.github/workflows/prepared-canonical.yml').write_text(base)
