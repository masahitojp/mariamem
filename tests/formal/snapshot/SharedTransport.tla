----------------------------- MODULE SharedTransport -----------------------------
CONSTANT WaitForClientInHostReader

VARIABLES slow, peer, capture
vars == <<slow, peer, capture>>

Init ==
    /\ slow = "unread"
    /\ peer = "first-output"
    /\ capture = "not-called"

\* A Go reader that enqueues OUTPUT can keep draining the guest stream.
\* The mutant waits for the first client's socket write inside that reader.
HostCanRead == ~WaitForClientInHostReader \/ slow = "drained"

DeliverFirstPeerSQL ==
    /\ peer = "first-output"
    /\ HostCanRead
    /\ peer' = "first-ack-pending"
    /\ UNCHANGED <<slow, capture>>

AckFirstPeerSQL ==
    /\ peer = "first-ack-pending"
    /\ peer' = "first-idle"
    /\ UNCHANGED <<slow, capture>>

RetireFirstPeer ==
    /\ peer = "first-idle"
    /\ peer' = "replacement-output"
    /\ UNCHANGED <<slow, capture>>

DeliverReplacementSQL ==
    /\ peer = "replacement-output"
    /\ HostCanRead
    /\ peer' = "replacement-ack-pending"
    /\ UNCHANGED <<slow, capture>>

AckReplacementSQL ==
    /\ peer = "replacement-ack-pending"
    /\ peer' = "replacement-idle"
    /\ UNCHANGED <<slow, capture>>

\* The slow worker already holds the full unacknowledged output window.
\* Snapshot's caller will only resume reading after Snapshot returns.
SendFence ==
    /\ capture = "not-called"
    /\ capture' = "awaiting-reply"
    /\ UNCHANGED <<slow, peer>>

RejectFence ==
    /\ capture = "awaiting-reply"
    /\ capture' = "busy-queued"
    /\ UNCHANGED <<slow, peer>>

ReceiveBusy ==
    /\ capture = "busy-queued"
    /\ HostCanRead
    /\ capture' = "busy"
    /\ UNCHANGED <<slow, peer>>

DrainSlowClient ==
    /\ capture = "busy"
    /\ peer = "replacement-idle"
    /\ slow = "unread"
    /\ slow' = "drained"
    /\ UNCHANGED <<peer, capture>>

Next ==
    \/ DeliverFirstPeerSQL \/ AckFirstPeerSQL \/ RetireFirstPeer
    \/ DeliverReplacementSQL \/ AckReplacementSQL
    \/ SendFence \/ RejectFence \/ ReceiveBusy \/ DrainSlowClient

Spec ==
    /\ Init /\ [][Next]_vars
    /\ WF_vars(DeliverFirstPeerSQL) /\ WF_vars(AckFirstPeerSQL)
    /\ WF_vars(RetireFirstPeer) /\ WF_vars(DeliverReplacementSQL)
    /\ WF_vars(AckReplacementSQL)
    /\ WF_vars(SendFence) /\ WF_vars(RejectFence)
    /\ WF_vars(ReceiveBusy) /\ WF_vars(DrainSlowClient)

CaptureReturns == <> (capture = "busy")
PeerReturns == <> (peer = "replacement-idle")
=============================================================================
