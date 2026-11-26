------------------------------ MODULE Snapshot ------------------------------
EXTENDS TLC

CONSTANTS Scenario, Policy, Schedule, Interrupt

VARIABLES wire, call, outcome, accepted, consumed
vars == <<wire, call, outcome, accepted, consumed>>

\* The client's OK receipt and the host writer's return are separate events.
Init ==
  /\ wire = "awaiting-client"
  /\ call = "not-called"
  /\ outcome = "none"
  /\ accepted = FALSE
  /\ consumed = FALSE

ReceiveReply ==
  /\ wire = "awaiting-client"
  /\ wire' = IF Scenario = "update" THEN "ok-read" ELSE "unread"
  /\ UNCHANGED <<call, outcome, accepted, consumed>>

Invoke ==
  /\ call = "not-called"
  /\ wire # "awaiting-client"
  /\ call' = "checking-ack"
  /\ UNCHANGED <<wire, outcome, accepted, consumed>>

RecordWrite ==
  /\ wire = "ok-read"
  /\ wire' = "ack-pending"
  /\ UNCHANGED <<call, outcome, accepted, consumed>>

SendAck ==
  /\ wire = "ack-pending"
  /\ Schedule # "ack-stall"
  /\ wire' = "ack-sent"
  /\ UNCHANGED <<call, outcome, accepted, consumed>>

GuestIdle ==
  /\ wire = "ack-sent"
  /\ wire' = "idle"
  /\ UNCHANGED <<call, outcome, accepted, consumed>>

SendFence ==
  /\ call = "checking-ack"
  /\ wire # "ack-pending"
  /\ call' = "fence-sent"
  /\ UNCHANGED <<wire, outcome, accepted, consumed>>

GuestAccept ==
  /\ call = "fence-sent"
  /\ wire = "idle"
  /\ Schedule # "fence-stall"
  /\ call' = "accepted"
  /\ accepted' = TRUE
  /\ consumed' = TRUE
  /\ UNCHANGED <<wire, outcome>>

GuestReject ==
  /\ call = "fence-sent"
  /\ wire # "idle"
  /\ call' = "settling"
  /\ UNCHANGED <<wire, outcome, accepted, consumed>>

Retry ==
  /\ call = "settling"
  /\ wire \in {"ack-pending", "ack-sent", "idle"}
  /\ call' = "checking-ack"
  /\ UNCHANGED <<wire, outcome, accepted, consumed>>

\* Collapse a budget to its expiration event. "timely" assumes that a
\* write already read by the client finishes bookkeeping before expiration.
\* "late-write" permits expiration before bookkeeping, without modeling ms.
ReturnBusy ==
  /\ call = "settling"
  /\ \/ /\ Policy = "old"
        /\ wire \in {"ok-read", "unread"}
     \/ /\ Policy = "bounded"
        /\ \/ wire = "unread"
           \/ /\ wire = "ok-read"
              /\ Schedule = "late-write"
  /\ call' = "returned"
  /\ outcome' = "busy"
  /\ UNCHANGED <<wire, accepted, consumed>>

\* In the unread scenario the caller cannot resume reading during Snapshot.
DrainRows ==
  /\ wire = "unread"
  /\ call = "returned"
  /\ outcome = "busy"
  /\ wire' = "idle"
  /\ UNCHANGED <<call, outcome, accepted, consumed>>

AcceptReply ==
  /\ call = "accepted"
  /\ call' = "returned"
  /\ outcome' = "ok"
  /\ UNCHANGED <<wire, accepted, consumed>>

CancelBeforeSend ==
  /\ Interrupt = "cancel-before-send"
  /\ call = "checking-ack"
  /\ wire = "ack-pending"
  /\ call' = "returned"
  /\ outcome' = "canceled"
  /\ UNCHANGED <<wire, accepted, consumed>>

LoseFenceReply ==
  /\ Interrupt \in {"cancel-fence", "disconnect-fence"}
  /\ call \in {"fence-sent", "accepted"}
  /\ call' = "returned"
  /\ consumed' = TRUE
  /\ outcome' = IF Interrupt = "cancel-fence" THEN "canceled" ELSE "disconnected"
  /\ UNCHANGED <<wire, accepted>>

Next ==
  \/ ReceiveReply \/ Invoke \/ RecordWrite \/ SendAck \/ GuestIdle
  \/ SendFence \/ GuestAccept \/ GuestReject \/ Retry \/ ReturnBusy
  \/ DrainRows \/ AcceptReply \/ CancelBeforeSend \/ LoseFenceReply

\* Fair scheduling advances enabled work. It cannot unstall a channel.
Spec == Init /\ [][Next]_vars
  /\ WF_vars(ReceiveReply) /\ WF_vars(Invoke) /\ WF_vars(RecordWrite)
  /\ WF_vars(SendAck) /\ WF_vars(GuestIdle) /\ WF_vars(SendFence)
  /\ WF_vars(GuestAccept) /\ WF_vars(GuestReject) /\ WF_vars(Retry)
  /\ WF_vars(ReturnBusy) /\ WF_vars(DrainRows) /\ WF_vars(AcceptReply)
  /\ WF_vars(CancelBeforeSend) /\ WF_vars(LoseFenceReply)

NoFalseBusy == Scenario # "update" \/ outcome # "busy"
Ownership ==
  /\ accepted => consumed
  /\ outcome = "busy" => ~consumed
  /\ outcome = "ok" => accepted
  /\ (outcome = "canceled" /\ Interrupt = "cancel-before-send") => ~consumed
  /\ (outcome \in {"canceled", "disconnected"} /\
      Interrupt \in {"cancel-fence", "disconnect-fence"}) => consumed

Returns == (call # "not-called") ~> (call = "returned")
Succeeds == (call # "not-called") ~> (outcome = "ok")
UnreadReturns == (wire = "unread" /\ call # "not-called") ~> (outcome = "busy")
RowsCanDrain == (outcome = "busy") ~> (wire = "idle")
=============================================================================
