---- MODULE SnapshotAdmission ----
EXTENDS Naturals, FiniteSets

(*
  Formal model for mariamem #255:
  Database.Snapshot admission and context cancellation while a leading Snapshot
  is in flight, interacting with concurrent Close().

  Design = "MutexHeld" (previous bug: db.mu held across backend SnapshotHeap/Keep;
                        waiting caller blocks on db.mu.Lock and cannot observe ctx.Done())
         | "SnapSlot"  (fix: db.mu protects dbState & snapInFlight/snapDone;
                        waiting caller checks ctx before waiting and selects on
                        snapDone vs ctx.Done() without holding db.mu;
                        Close() defers backend Close until snapDone closes).
*)

CONSTANTS Design

Callers == {1, 2}

VARIABLES
  dbState,        \* "open" | "consumed" | "closed"
  closing,        \* BOOLEAN: Close() has closed the backend or adopted consumed closeErr
  closePending,   \* BOOLEAN: Close() requested while snapInFlight # 0 (deferred until snap ends)
  snapInFlight,   \* 0 (none) or caller id in Callers
  backendActive,  \* 0 (none) or caller id currently inside backend SnapshotHeap/Keep
  owner,          \* 0 (none) or caller id that acquired snapshot ownership (consumed)
  pc,             \* [Callers -> {"idle", "waiting", "in_backend", "done_ok", "done_busy", "done_canceled", "done_closed"}]
  ctxCanceled     \* [Callers -> BOOLEAN]

vars == <<dbState, closing, closePending, snapInFlight, backendActive, owner, pc, ctxCanceled>>

TypeOK ==
  /\ dbState \in {"open", "consumed", "closed"}
  /\ closing \in BOOLEAN
  /\ closePending \in BOOLEAN
  /\ snapInFlight \in {0} \cup Callers
  /\ backendActive \in {0} \cup Callers
  /\ owner \in {0} \cup Callers
  /\ pc \in [Callers -> {"idle", "waiting", "in_backend", "done_ok", "done_busy", "done_canceled", "done_closed"}]
  /\ ctxCanceled \in [Callers -> BOOLEAN]

Init ==
  /\ dbState = "open"
  /\ closing = FALSE
  /\ closePending = FALSE
  /\ snapInFlight = 0
  /\ backendActive = 0
  /\ owner = 0
  /\ pc = [c \in Callers |-> "idle"]
  /\ ctxCanceled = [c \in Callers |-> FALSE]

CancelCtx(c) ==
  /\ pc[c] \in {"idle", "waiting"}
  /\ ~ctxCanceled[c]
  /\ ctxCanceled' = [ctxCanceled EXCEPT ![c] = TRUE]
  /\ UNCHANGED <<dbState, closing, closePending, snapInFlight, backendActive, owner, pc>>

StartOrEnter(c) ==
  /\ pc[c] = "idle"
  /\ IF snapInFlight = 0 THEN
       IF dbState # "open" \/ closePending THEN
         /\ pc' = [pc EXCEPT ![c] = "done_closed"]
         /\ UNCHANGED <<dbState, closing, closePending, snapInFlight, backendActive, owner, ctxCanceled>>
       ELSE IF ctxCanceled[c] THEN
         /\ pc' = [pc EXCEPT ![c] = "done_canceled"]
         /\ UNCHANGED <<dbState, closing, closePending, snapInFlight, backendActive, owner, ctxCanceled>>
       ELSE
         /\ snapInFlight' = c
         /\ backendActive' = c
         /\ pc' = [pc EXCEPT ![c] = "in_backend"]
         /\ UNCHANGED <<dbState, closing, closePending, owner, ctxCanceled>>
     ELSE
       IF Design = "SnapSlot" /\ (dbState # "open" \/ closePending) THEN
         /\ pc' = [pc EXCEPT ![c] = "done_closed"]
         /\ UNCHANGED <<dbState, closing, closePending, snapInFlight, backendActive, owner, ctxCanceled>>
       ELSE IF Design = "SnapSlot" /\ ctxCanceled[c] THEN
         /\ pc' = [pc EXCEPT ![c] = "done_canceled"]
         /\ UNCHANGED <<dbState, closing, closePending, snapInFlight, backendActive, owner, ctxCanceled>>
       ELSE
         /\ pc' = [pc EXCEPT ![c] = "waiting"]
         /\ UNCHANGED <<dbState, closing, closePending, snapInFlight, backendActive, owner, ctxCanceled>>

WaitCancel(c) ==
  /\ Design = "SnapSlot"
  /\ pc[c] = "waiting"
  /\ ctxCanceled[c]
  /\ pc' = [pc EXCEPT ![c] = "done_canceled"]
  /\ UNCHANGED <<dbState, closing, closePending, snapInFlight, backendActive, owner, ctxCanceled>>

WaitWake(c) ==
  /\ pc[c] = "waiting"
  /\ snapInFlight = 0
  /\ IF dbState # "open" \/ closePending THEN
       /\ pc' = [pc EXCEPT ![c] = "done_closed"]
       /\ UNCHANGED <<dbState, closing, closePending, snapInFlight, backendActive, owner, ctxCanceled>>
     ELSE IF ctxCanceled[c] THEN
       /\ pc' = [pc EXCEPT ![c] = "done_canceled"]
       /\ UNCHANGED <<dbState, closing, closePending, snapInFlight, backendActive, owner, ctxCanceled>>
     ELSE
       /\ snapInFlight' = c
       /\ backendActive' = c
       /\ pc' = [pc EXCEPT ![c] = "in_backend"]
       /\ UNCHANGED <<dbState, closing, closePending, owner, ctxCanceled>>

BackendFinishConsume(c) ==
  /\ pc[c] = "in_backend"
  /\ backendActive = c
  /\ snapInFlight = c
  /\ dbState' = "consumed"
  /\ owner' = c
  /\ snapInFlight' = 0
  /\ backendActive' = 0
  /\ pc' = [pc EXCEPT ![c] = "done_ok"]
  /\ UNCHANGED <<closing, closePending, ctxCanceled>>

BackendFinishBusy(c) ==
  /\ pc[c] = "in_backend"
  /\ backendActive = c
  /\ snapInFlight = c
  /\ snapInFlight' = 0
  /\ backendActive' = 0
  /\ pc' = [pc EXCEPT ![c] = "done_busy"]
  /\ UNCHANGED <<dbState, closing, closePending, owner, ctxCanceled>>

RequestClose ==
  /\ ~closing
  /\ ~closePending
  /\ IF snapInFlight = 0 THEN
       IF dbState = "open" THEN
         /\ closing' = TRUE
         /\ dbState' = "closed"
         /\ UNCHANGED <<closePending, snapInFlight, backendActive, owner, pc, ctxCanceled>>
       ELSE
         /\ closing' = TRUE
         /\ UNCHANGED <<dbState, closePending, snapInFlight, backendActive, owner, pc, ctxCanceled>>
     ELSE
       /\ closePending' = TRUE
       /\ UNCHANGED <<dbState, closing, snapInFlight, backendActive, owner, pc, ctxCanceled>>

CompleteDeferredClose ==
  /\ closePending
  /\ snapInFlight = 0
  /\ closePending' = FALSE
  /\ closing' = TRUE
  /\ dbState' = IF dbState = "open" THEN "closed" ELSE dbState
  /\ UNCHANGED <<snapInFlight, backendActive, owner, pc, ctxCanceled>>

Next ==
  \/ \E c \in Callers : CancelCtx(c)
  \/ \E c \in Callers : StartOrEnter(c)
  \/ \E c \in Callers : WaitCancel(c)
  \/ \E c \in Callers : WaitWake(c)
  \/ \E c \in Callers : BackendFinishConsume(c)
  \/ \E c \in Callers : BackendFinishBusy(c)
  \/ RequestClose
  \/ CompleteDeferredClose

\* Weak fairness on WaitCancel only (NOT on BackendFinish*, modeling a stalled leader).
Fairness ==
  \A c \in Callers : WF_vars(WaitCancel(c))

Spec == Init /\ [][Next]_vars /\ Fairness

SingleBackendCapture ==
  Cardinality({c \in Callers : pc[c] = "in_backend"}) <= 1

SingleOwner ==
  /\ Cardinality({c \in Callers : pc[c] = "done_ok"}) <= 1
  /\ (owner # 0) <=> (dbState = "consumed")

CanceledNeverOwns ==
  \A c \in Callers : pc[c] = "done_canceled" => owner # c

BusyPreservesOpenDB ==
  ((owner = 0) /\ ~closing) => (dbState = "open")

NoCloseDuringBackendCapture ==
  (backendActive # 0) => ~closing

CanceledWaiterProgress ==
  \A c \in Callers :
    (pc[c] = "waiting" /\ ctxCanceled[c]) ~> (pc[c] \in {"done_canceled", "done_closed"})

====
