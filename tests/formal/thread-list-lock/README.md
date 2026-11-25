# Thread-list lock lost wakeup

This model records a possible order of operations for [mariamem #246](https://github.com/masahitojp/mariamem/issues/246). It has one unlocker and one waiter. The unlock store and the moment it becomes visible to the waiter are separate events.

| Model event | Runtime operation |
| --- | --- |
| StoreUnlock and PublishUnlock | The non-recursive `__tl_unlock` path stores zero to the thread-list lock. |
| RegisterWaiter | `__wait` increments the waiter count. This registration precedes the parking operation. |
| CompareAndPark | `AtomicWait32At` checks the expected lock value and parks under the wait-queue mutex. |
| CheckWaiters and Notify | The unlocker reads the waiter count and calls the wake primitive when the count is positive. |

With `Fence = FALSE`, TLC finds an unlocker that sees zero waiters, followed by a waiter that registers and parks on the old lock value before the unlock becomes visible. With `Fence = TRUE`, the model assumes the post-store fence makes the unlock visible before the waiter-count read. TLC checks that the waiter can progress under weak fairness.

The visibility rule is an explicit abstraction. The model has no competing owner, multiple waiters or spurious wakeups. Validate the optimizer change against the WASM instructions, generated Go and actual ARM64 guest. See the issue for the optimizer and runtime results.

## Run

Use the [official TLC v1.8.0 jar](https://github.com/tlaplus/tlaplus/releases/tag/v1.8.0) with Java 11 or later. The tested jar SHA-256 is `fdffef247f563ef6edbfd44958d2a82db79e7564e07cb673262d896353fa6713`.

```sh
sh tests/formal/thread-list-lock/check.sh /absolute/path/to/tla2tools.jar
```

The script succeeds when the unfenced run reports the expected invariant violation and the fenced run passes both the invariant and progress property.
