--------------------------- MODULE FailureCleanup ---------------------------
CONSTANTS ReturnBeforeJoin, GuestCanFinish
VARIABLES failed, returned, guestDone, owner
vars == <<failed, returned, guestDone, owner>>

Init ==
    /\ failed = FALSE
    /\ returned = FALSE
    /\ guestDone = FALSE
    /\ owner = "capture"

\* Both a lost fence reply and a failure after stop acceptance reach this
\* boundary once the host knows capture cannot succeed.
DetectFailure ==
    /\ ~failed
    /\ failed' = TRUE
    /\ UNCHANGED <<returned, guestDone, owner>>

FinishGuest ==
    /\ failed
    /\ GuestCanFinish
    /\ ~guestDone
    /\ guestDone' = TRUE
    /\ UNCHANGED <<failed, returned, owner>>

ReturnError ==
    /\ failed
    /\ ~returned
    /\ ReturnBeforeJoin \/ guestDone
    /\ returned' = TRUE
    /\ owner' = IF owner = "capture" THEN "retained" ELSE owner
    /\ UNCHANGED <<failed, guestDone>>

Dispose ==
    /\ failed
    /\ guestDone
    /\ owner # "released"
    /\ owner' = "released"
    /\ UNCHANGED <<failed, returned, guestDone>>

Next == DetectFailure \/ FinishGuest \/ ReturnError \/ Dispose
Spec == Init /\ [][Next]_vars
    /\ WF_vars(DetectFailure) /\ WF_vars(FinishGuest)
    /\ WF_vars(ReturnError) /\ WF_vars(Dispose)

Ownership ==
    /\ owner = "released" => guestDone
    /\ returned => failed /\ owner # "capture"

ReturnsOnFailure == failed ~> returned
DisposesAfterJoin == guestDone ~> (owner = "released")
=============================================================================
