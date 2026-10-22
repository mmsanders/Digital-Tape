# Software525 changed correction1 scope

Issued independent correction7b4d09591753ad78841bb8da772fc2abc9d5772b,
findings tree and byte hashes in IMPORT.json, imported8db5f9e before changed
logic. Original38 outcomes/422 members/source remain immutable at0a056262;
the original experiment is not replayed. This is the first changed Software
correction return, no independent acceptance or C execution permission.

## Task and phase mechanics

`Task` owns one CPU origin and one conservative build/supervision charge. CPU
is integer ceiling nanoseconds of supervisor plus reaped children. Active group
CPU includes each live process's self ticks and waited-child ticks. Once a child
is reaped by its parent, its former live row disappears and its aggregate charge
passes to that parent; final root wait4/RUSAGE_CHILDREN replaces live charging.
No live charge is added again after root reaping. Scan races can conservatively
double count; this is not a hard monitor overshoot guarantee.

Task allocated highwater never resets. Phase entry records a fresh full-root
baseline and CPU baseline, plus separate phase highwater. A phase name cannot
restart; prior phase must close with actual task/phase/completion checks before
handoff. Task origin/build charge persist across build/positive/row. Before each
Popen: authenticate source/executable/argv graph, scan the entire owned root,
fsync immutable gate, enforce inclusive task/phase next+completion bounds, then
recheck actual allocation immediately before launch. No global slack overrides
phase exhaustion. Monitor/postrun/handoff apply the same phase/task limits and
estimate-stop policy; first failure makes the task permanently terminal.

All source/build/work/private/restored images/raw/temp/retained/archive paths must
be under the single owned root. Census includes directories, hidden paths, inode,
device, hardlink per-path overcount and actual allocated blocks; neither ZIP size
nor sparse/dedup equivalence is assumed as headroom. Source/interpreter/tools
outside the root are identity-pinned read-only dependencies; generated/copied
source and all task material count. Completion reserve covers receipt growth,
final scans, hashing/archive; C270 must justify actual numerical reservations.
No deletion routine exists.

## Bound crash graph

`crash_binding.bind` produces exact argv/rules for Python crash_child → strace →
tapectl, one live instance per role and explicit parent edges. Source runtime
55552ad4fe57e99827ab8eb016044d0486017877 remains fixed. Original514 strace
argv `-f -qq -yy -s 512 -e trace=openat,lseek,write,pwrite64,fsync,fdatasync -o`
and unchanged native args/env/cwd/input bytes are preserved, including full
syscall output and every original cold/model/state/PCM predicate owned by the
caller. The wrapper validates external payload/source input hashes, captures
original binary stdout/stderr, argv/PIDs/exit, and waits/reaps strace before exit.
It inherits the controller's owned group: the old adapter's nested setsid and
fixed4-second limits are replaced by the externally frozen task/phase limits.
That process-control change is explicit; it is not an oracle/predicate change.
No old native record or missing final accounting is reconstructed.

The exposed integration point is `Task.invoke(*bind(...), reservations...)` via
its explicit argv/rules parameters; the caller must use this for EVERY build,
native/cold invocation and closure/finalization phase. The frozen runtime source
and output predicates are not copied/reimplemented by this controller. No live
C schedule, positive or fault is called by this return. C270 owns checking the
actual complete caller routing, tool bytes, lifecycle/model/cost premises and
issuing a final executable schedule. A standalone adapter return cannot clear C.

This is a cooperating, source-bound wait-for-child graph contract. No arbitrary
orphan/double-fork/setsid/daemon/foreign tree theorem. Unsupported observed argv,
parent edge, count or surviving group member stops; escaped/unobserved descendant
accounting remains unsupported. Exact tool source must establish no group escape,
extra child, or exit-before-reap before any future Product invocation. Current
return demonstrates the same three-role shape with Python surrogates, and the
actual changed crash wrapper with surrogate tracer/leaf; it does not execute or
qualify strace/tapectl. No hard CPU/storage peak/kill-latency bound follows from
10ms polling, filesystem scans, syscalls or SIGKILL.

## Real measurement failure finalizer

Fallible initial/running/final census and CPU measurements all enter one finalizer.
If launched, root is killed/reaped on failure; original stdout/stderr remain open
through reaping, then retained. Failed final measurements stay null with original
exception/stage; no guessed allocation/CPU. ACCOUNTING-STOP.json is immutable
INCOMPLETE STOP; Task adds immutable STOP.json/raw hashes/RESULT.json. Missing
root before launch produces STOP without a child. Subsequent invoke refuses
before creating a command directory or touching the spy. Storage itself becoming
unwritable can prevent any receipt; this is not a durable power-loss theorem.

## Changed harmless controls, frozen here before one execution

Ten distinct scenarios: three successive phase handoffs with task charge retained;
actual changed crash wrapper with surrogate tracer/leaf; genuine census failure
before Popen; genuine final census failure after binary raw and child reap;
genuine running census failure; unsupported extra process argv; phase storage
exhaustion with task slack; total CPU headroom rejection; zero next-byte estimate
overrun; source-identity rejection. Every failed scenario attempts the same next
entry point and verifies unchanged launch spy. Full source/build/work/temp/archive/
retained file allocations outside each raw command directory are demonstrated.
These are changed mechanics controls, not the original38 or Product costs.

Run on existing Ubuntu CI Python only, once through PR529 synchronize workflow;
no runtime/compiler installation/repair, native observer/device/token calls.
Whole focused experiment cap512MiB/7200CPU includes all failed roots, copied
source, raw/temp/archive and120CPU conservative supervision reserve. Final
census after archive includes65536-byte receipt allowance. Normal seven required
checks stay enabled; actual correction acceptance remains Verification268's.
