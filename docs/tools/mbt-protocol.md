# Model-Based Testing Protocol

`merc-mbt` performs black-box conformance testing of a running system under
test (SUT) against an mCRL2 linear process specification (LPS), using the
**IOCO** (input-output conformance) relation. To stay independent of any
particular SUT, the tool never talks to a system directly. Instead it
speaks a small, SUT-agnostic protocol to a separate **adapter**: a thin
piece of software, specific to the system under test, that translates
between the model's abstract actions and the SUT's concrete inputs and
outputs. Anyone can write an adapter for their own system and reuse the
same MBT tool and the same conformance checking logic.

This page describes the protocol's roles, lifecycle and testing semantics
at a conceptual level. It deliberately leaves out the wire format — the
exact JSON message shapes are an implementation detail of the two existing
implementations ([`merc-mbt`](https://github.com/mlaveaux/merc-mbt), in
Rust, and an experimental `mcrl2mbt` tool in the mCRL2 toolset itself) and
are specified there for anyone implementing a new adapter or a third
implementation of the tool side.

## Roles

The two sides of the protocol have distinct responsibilities:

- The **MBT tool** loads the LPS and interprets it symbolically. It tracks
  the set of model states consistent with everything observed so far, and,
  on request, reports which inputs and outputs that state set currently
  allows. It also checks every reported observation against the model and
  flags a mismatch as a conformance failure.
- The **adapter** owns the system under test. It decides which input to
  stimulate the SUT with (out of whatever the tool currently reports as
  enabled), observes the SUT's outputs and translates them back into model
  actions, and detects quiescence — the SUT going silent — with its own
  timer. It also owns the session's configuration and decides when a test
  run ends.

Putting state tracking and conformance checking in the tool, and SUT
control in the adapter, means a new system under test only ever needs a
new adapter; the model-side logic is written once.

## Conformance and quiescence

IOCO testing continuously checks one thing: every output the SUT produces
must be an output the model would also allow in its current (possibly
non-deterministic) state. The protocol treats **quiescence** — observable
silence from the SUT — as a first-class event of equal standing to any
other output, since "the system stays silent" is itself something a model
can forbid or allow at a given point.

Because an LPS state set can be non-deterministic, the tool never commits
to a single concrete state. It maintains the full set of states consistent
with the trace observed so far, narrowing it as observations come in and
widening it again whenever a model-internal step could plausibly have
happened without being observable from outside.

## Session lifecycle

A session is a single, synchronous conversation over one connection, with
the adapter listening and the tool connecting out to it:

1. Both sides exchange an introductory handshake. The adapter's side of it
   is authoritative for the session's configuration — how deep the tool
   should look ahead through unobservable model-internal steps, how much
   reordering tolerance to allow, and the heartbeat cadence used to detect
   a stalled peer.
2. The session is then driven by the adapter: it asks the tool what is
   currently possible, picks a stimulus or waits for the SUT to respond,
   and reports back whatever it observes. The tool answers every such
   query and acknowledges every observation it can reconcile with the
   model.
3. The adapter can rewind the tool back to the model's initial state at
   any point, to start a fresh test run without reconnecting.
4. Either side ends the session with a graceful close; the adapter is the
   usual initiator, since it is the one that decides when a run is
   finished or when to abort after a conformance failure.

## The core testing loop

Within a session, the exchange follows a simple cycle: the adapter asks
the tool which inputs and outputs are currently enabled, chooses one of
the enabled inputs to stimulate the SUT with (or waits to see what the SUT
itself does), and reports the outcome back as an input, an output, or
quiescence. The tool updates its internal state set in response and tells
the adapter whether that outcome was consistent with the model.

An input the adapter reports is special: since the adapter itself is the
one driving it, an input that the model doesn't currently allow means the
*adapter* made a mistake, not the SUT — this is reported distinctly from
an actual conformance failure. An unexpected output or a missing one where
output was required, by contrast, points at the SUT itself.

## Why the model's view is approximate

Two deliberate approximations keep the tool practical on real models and
real systems:

- **Bounded lookahead through internal steps.** An LPS can take an
  unbounded number of model-internal steps between two observable actions.
  Exploring all of them exhaustively isn't generally possible, so the tool
  only looks ahead a configurable number of steps when deciding what is
  currently enabled. A model that needs more lookahead than configured can
  make a reachable output look temporarily unreachable; this is a tuning
  knob the adapter negotiates as part of the session, not a hidden
  limitation. A tool implementation may additionally cap how large its own
  internal state set is allowed to grow, as a local safety valve against a
  model whose reachable set turns out to be unbounded — but that cap, unlike
  the lookahead depth, is not something the protocol itself negotiates.
- **Tolerance for reordering.** A real adapter sitting between the tool
  and the SUT can observe and report an input before it has finished
  reporting a causally-earlier output, especially if the adapter itself
  has any concurrency. Rather than fail a test run on every such reordering,
  an output that doesn't match the model's current expectation is held
  briefly and re-checked as further observations arrive, only failing the
  run if it is still unmatched once a configured window has passed. This
  tolerance is itself configurable down to zero — strict IOCO with no
  reordering allowed — and every use of it is surfaced to the adapter, so
  an adapter that wants strict behaviour regardless can simply abort the
  moment the tolerance is used at all.

## Writing a new adapter

An adapter is usually the only new code a project has to write to start
model-based testing a system: a small translation layer between the
model's action vocabulary and whatever interface the SUT exposes (a
network protocol, a hardware bus, a CLI, ...), plus a quiescence timer and
a policy for picking which enabled input to try next. Everything about
state tracking, non-determinism and conformance checking is handled by the
MBT tool and shared across every adapter written against it.
