------------------------------ MODULE ThreadList ------------------------------
CONSTANT Fence
VARIABLES unlock, visible, registered, waiter
vars == <<unlock, visible, registered, waiter>>

Init ==
    /\ unlock = "held"
    /\ visible = FALSE
    /\ registered = FALSE
    /\ waiter = "starting"

\* The non-recursive unlock stores zero. Visibility to the waiter is separate.
StoreUnlock ==
    /\ unlock = "held"
    /\ unlock' = "stored"
    /\ UNCHANGED <<visible, registered, waiter>>

PublishUnlock ==
    /\ unlock # "held"
    /\ ~visible
    /\ visible' = TRUE
    /\ UNCHANGED <<unlock, registered, waiter>>

RegisterWaiter ==
    /\ waiter = "starting"
    /\ waiter' = "registered"
    /\ registered' = TRUE
    /\ UNCHANGED <<unlock, visible>>

\* AtomicWait checks the expected value and parks under its queue mutex.
CompareAndPark ==
    /\ waiter = "registered"
    /\ waiter' = IF visible THEN "can-progress" ELSE "parked"
    /\ UNCHANGED <<unlock, visible, registered>>

\* Model only the post-store fence: the unlock is visible before this read.
CheckWaiters ==
    /\ unlock = "stored"
    /\ ~Fence \/ visible
    /\ unlock' = IF registered THEN "must-notify" ELSE "done"
    /\ UNCHANGED <<visible, registered, waiter>>

Notify ==
    /\ unlock = "must-notify"
    /\ unlock' = "done"
    /\ waiter' = IF waiter = "parked" THEN "can-progress" ELSE waiter
    /\ UNCHANGED <<visible, registered>>

Next ==
    \/ StoreUnlock \/ PublishUnlock \/ RegisterWaiter
    \/ CompareAndPark \/ CheckWaiters \/ Notify

Spec == Init /\ [][Next]_vars
    /\ WF_vars(StoreUnlock) /\ WF_vars(PublishUnlock)
    /\ WF_vars(RegisterWaiter) /\ WF_vars(CompareAndPark)
    /\ WF_vars(CheckWaiters) /\ WF_vars(Notify)

NoStrandedWaiter == ~(unlock = "done" /\ visible /\ waiter = "parked")
WaiterProgress == <> (waiter = "can-progress")
=============================================================================
