# Registered historical inputs for the pure resolver

These three fixtures are self-contained, opt-in test inputs. They do not select
a product engine or supply a runnable prepared source tree. No historical Git
object, external checkout or network access is needed to run the unit tests.

- 12.3.3 / legacy-full: source47121e1be0b399ba4e2270ce3e25c411ade0e2eb.
- 13.0.2 / legacy-full: producer32c799031f619164d3730b61a0bc9d7ae48dcd9b.
- 13.0.2 / native-text: producer4b3954a0faf42986459bc1ee68727be16d67bcbb.

Each expected JSON contains the original parsed guest/input.json and
release/inputs.lock.json plus original byte hashes. Descriptor files preserve
the guest input, factor the lock into one shared blob and an engine entry, and
explicitly list stages and patch/proof blobs. Content-addressed text blobs retain
exact repository bytes. The canonical source.patch is recorded even where the
13 route instead applies its explicit source overlay; this is not permission
to apply both. Historical prepared pins remain historical, including their old
TIME proof bookkeeping; resolution does not execute the corrected helper or
claim full source verification.

registry.json is the reviewed trust root. It pins descriptor bytes and semantic
input/lock/stage digests. Semantic JSON uses sorted keys, comma/colon separators,
UTF-8 without ASCII escaping, and one final newline. Original byte hashes must
not be replaced by these semantic digests in old receipts. A changed descriptor
requires a reviewed registry update; changing both is not an adversarial case
this registry can authenticate.

To add a registered engine/profile, supply a descriptor, exact referenced blobs
and independent expected inputs, then update the registry entry and review the
diff. No engine version constant in Python changes. Profiles/stage semantics and
source proof handling may still require code when upstream behaviour changes.

The content reader passed to resolve_inputs is supplied by the caller. Tests
preload these files into a bytes dictionary. A future filesystem adapter must
also enforce symlink containment and owned output isolation; this pure function
only checks portable relative path syntax and exact bytes.
