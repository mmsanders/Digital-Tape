"""Linux task/phase adapter. Cooperating, pinned, wait-for-child launch graphs only."""
import os
from pathlib import Path
import signal
import subprocess
import time
import controller as C


def processes(group, rules):
    """Charge live self+waited-child ticks, never sum a reaped child twice."""
    ticks = os.sysconf('SC_CLK_TCK')
    rows = []
    for p in Path('/proc').iterdir():
        if not p.name.isdigit():
            continue
        try:
            raw = (p/'stat').read_text()
            f = raw[raw.rfind(')')+2:].split()
            if int(f[2]) != group:
                continue
            argv = (p/'cmdline').read_bytes().split(b'\0')[:-1]
            argv = [os.fsdecode(x) for x in argv]
            # A zombie has no cmdline; its charge still belongs to its live parent.
            role = None
            if f[0] != 'Z':
                for rule in rules:
                    if argv == rule['argv'] and C.sha(Path(rule['argv'][0]).read_bytes()) == rule['exe_sha256']:
                        role = rule['role']
                        break
                if role is None:
                    raise RuntimeError('unsupported process identity: '+repr(argv))
            ns = (sum(int(f[i]) for i in (11, 12, 13, 14))*1000000000+ticks-1)//ticks
            rows.append(dict(pid=int(p.name), parent=int(f[1]), state=f[0], role=role,
                             argv=argv, cpu_with_waited_children_ns=ns))
        except (FileNotFoundError, ProcessLookupError):
            continue
    bypid = {r['pid']:r for r in rows}
    counts = {}
    for r in rows:
        if r['state'] == 'Z':
            continue
        rule = next(x for x in rules if x['role'] == r['role'])
        counts[r['role']] = counts.get(r['role'], 0)+1
        if counts[r['role']] > rule['max_live']:
            raise RuntimeError('process cardinality exceeded')
        if r['pid'] != group:
            parent = bypid.get(r['parent'])
            if parent is None or parent['role'] not in rule['parents']:
                raise RuntimeError('unsupported parent edge')
    return dict(rows=rows, cpu_ns=sum(r['cpu_with_waited_children_ns'] for r in rows),
                ticks_per_second=ticks)


def supervise(session, argv, output, timeout, cpu_cap_ns, bytes_cap,
              root=None, rules=None, sensor=None, final_gate=None):
    """Every fallible sensor, including BEFORE/FINAL, enters the same finalizer."""
    session.require_next()
    sensor = sensor or (lambda root, stage: C.census(root))
    output = Path(output)
    root = Path(root) if root is not None else output
    if rules is None:
        rules = [dict(role='direct', argv=argv, exe_sha256=C.sha(Path(argv[0]).read_bytes()),
                      max_live=1, parents=[])]
    start = time.monotonic_ns()
    before = final = usage = proc = start_cpu = final_cpu = None
    monitors = []
    errors = []
    reason = None
    reaped = False
    launch_gate = None
    try:
        before = sensor(root, 'before')
        start_cpu = C.own_completed_cpu()
        # Task owns the original origins: this fresh measurement must not start
        # another task/phase clock. Include prior gate fsync/hash/census work.
        if final_gate is not None:
            launch_gate = final_gate(before, start_cpu)
            C.immutable(output/'FINAL-GATE.json', launch_gate)
            if launch_gate['decision'] != 'ALLOW':
                raise RuntimeError(launch_gate['decision'])
            cpu_cap_ns = launch_gate['cpu_cap_ns']
            bytes_cap = launch_gate['bytes_cap']
            start_cpu = launch_gate['invocation_cpu_origin_ns']
        if before['allocated_bytes'] > bytes_cap or cpu_cap_ns < 0:
            raise RuntimeError('pre-launch actual task/phase exhaustion')
        with (output/'stdout.bin').open('xb') as stdout, (output/'stderr.bin').open('xb') as stderr:
            proc = subprocess.Popen(argv, stdout=stdout, stderr=stderr, start_new_session=True)
            C.immutable(output/'LAUNCH.json', dict(argv=argv, pid=proc.pid, parent=os.getpid(),
                        start_ns=start, nonce=session.nonce, process_group=proc.pid))
            while True:
                got, status, measured = os.wait4(proc.pid, os.WNOHANG)
                if got:
                    usage = measured
                    reaped = True
                    proc.returncode = os.waitstatus_to_exitcode(status)
                    # Cooperating wrappers MUST wait for every descendant before exit.
                    if C.live_tree(proc.pid)['processes']:
                        raise RuntimeError('descendant remained after root exit')
                    break
                live = processes(proc.pid, rules)
                scan = sensor(root, 'monitor')
                now = time.monotonic_ns()
                monitors.append(dict(time_ns=now, live=live, allocated=scan['allocated_bytes']))
                if now-start > int(timeout*1000000000):
                    reason = 'timeout'
                elif C.own_completed_cpu()-start_cpu+live['cpu_ns'] > cpu_cap_ns:
                    reason = 'cpu-overrun'
                elif scan['allocated_bytes'] > bytes_cap:
                    reason = 'storage-overrun'
                if reason:
                    raise RuntimeError(reason)
                time.sleep(.01)
    except BaseException as e:
        errors.append(dict(stage='before-or-running', exception=repr(e)))
        reason = reason or 'measurement-or-launch-failure'
    finally:
        if proc is not None and (not reaped or errors):
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            except BaseException as e:
                errors.append(dict(stage='kill', exception=repr(e)))
            if not reaped:
                try:
                    _, status, usage = os.wait4(proc.pid, 0)
                    proc.returncode = os.waitstatus_to_exitcode(status)
                    reaped = True
                except BaseException as e:
                    errors.append(dict(stage='reap', exception=repr(e)))
        try:
            final = sensor(root, 'final')
        except BaseException as e:
            errors.append(dict(stage='final-census', exception=repr(e)))
        try:
            final_cpu = C.own_completed_cpu()
        except BaseException as e:
            errors.append(dict(stage='final-cpu', exception=repr(e)))
        complete = not errors and usage is not None and final is not None and final_cpu is not None
        if not complete or reason or (proc is not None and proc.returncode != 0):
            session.stopped = True
        result = dict(pid=proc.pid if proc else None, argv=argv, start_ns=start,
                      end_ns=time.monotonic_ns(), wall_ns=time.monotonic_ns()-start,
                      child_cpu_ns=C.ru_ns(usage) if usage is not None else None,
                      completed_scope_cpu_ns=final_cpu,
                      parent_cpu_delta_ns=(final_cpu-start_cpu-C.ru_ns(usage))
                          if final_cpu is not None and start_cpu is not None and usage is not None else None,
                      exit=proc.returncode if proc else None, reason=reason,
                      monitor=monitors, allocation_before=before, allocation_after=final,
                      accounting_complete=complete, errors=errors, child_reaped=reaped,
                      poll_ns=10000000, hard_overshoot_guarantee=False,
                      termination='SIGKILL owned cooperating process group; wait4 root',
                      scope=str(root), rules=rules)
        result['final_gate'] = launch_gate
        if not complete:
            C.immutable(output/'ACCOUNTING-STOP.json', dict(status='INCOMPLETE STOP',
                        terminal=True, no_further_command=True, measurement=result))
    return result


class Task:
    """One task CPU origin/build charge and retained allocation highwater, across phases."""
    def __init__(self, root, nonce, task_cpu_ns, task_bytes, build_reserve_ns,
                 completion_cpu_ns, completion_bytes, sensor=None):
        self.root = Path(root).resolve(strict=True)
        self.session = C.Session(nonce)
        self.sensor = sensor or (lambda root, stage: C.census(root))
        self.cpu_origin = C.own_completed_cpu()
        self.build = build_reserve_ns
        self.limits = (task_cpu_ns, task_bytes)
        self.completion = (completion_cpu_ns, completion_bytes)
        self.high = 0
        self.phase = None
        self.index = 0
        self.phases = []

    def begin(self, name, cpu_ns, allocated_bytes):
        self.session.require_next()
        if name in self.phases:
            raise RuntimeError('phase cannot restart')
        if self.phase is not None and not self.phase['closed']:
            raise RuntimeError('close prior phase before handoff')
        try:
            scan = self.sensor(self.root, 'phase')
            cpu = C.own_completed_cpu()-self.cpu_origin
            self.high = max(self.high, scan['allocated_bytes'])
            self.phase = dict(name=name, cpu_origin=cpu, allocation_origin=scan['allocated_bytes'],
                              high=0, cpu_limit=cpu_ns, bytes_limit=allocated_bytes, closed=False)
            self.phases.append(name)
            C.immutable(self.root/('PHASE-'+name+'.json'), dict(phase=self.phase, task_high=self.high,
                        task_cpu_origin=self.cpu_origin, build_charged_once_ns=self.build, scan=scan))
        except BaseException as e:
            self.session.stopped = True
            C.immutable(self.root/('PHASE-STOP-'+str(len(self.phases))+'.json'),
                        dict(status='INCOMPLETE STOP', exception=repr(e), no_further_command=True))
            raise

    def _snapshot(self, stage):
        scan = self.sensor(self.root, stage)
        cpu = C.own_completed_cpu()-self.cpu_origin
        self._retain_allocation(scan['allocated_bytes'])
        return scan, cpu

    def _retain_allocation(self, allocated):
        # Missing scans are never synthesized. Complete samples cannot decrease
        # either highwater, even if temporary files disappear before POST.
        if type(allocated) is not int or allocated < 0:
            raise RuntimeError('invalid complete allocation sample')
        self.high = max(self.high, allocated)
        self.phase['high'] = max(self.phase['high'], max(0, allocated-self.phase['allocation_origin']))

    def _retain_supervision(self, result):
        for key in ('allocation_before', 'allocation_after'):
            if result[key] is not None:
                self._retain_allocation(result[key]['allocated_bytes'])
        for row in result['monitor']:
            self._retain_allocation(row['allocated'])

    def invoke(self, argv, next_cpu_ns, next_bytes, rules, timeout=1):
        self.session.require_next()
        self.index += 1
        out = self.root/'raw'/('%04d'%self.index)
        out.mkdir(parents=True, exist_ok=False)
        result = None
        try:
            if self.phase is None or self.phase['closed']:
                raise RuntimeError('no active phase')
            # Authenticate all executable/script inputs before launch. Exact argv allowlist.
            if not any(r['argv'] == argv for r in rules):
                raise RuntimeError('root argv absent from bound graph')
            for rule in rules:
                for path, digest in rule['inputs'].items():
                    if C.sha(Path(path).read_bytes()) != digest:
                        raise RuntimeError('graph source identity mismatch')
            scan, cpu = self._snapshot('gate')
            req = dict(task_cpu_ns=cpu, phase_cpu_ns=cpu-self.phase['cpu_origin'],
                       active_child_cpu_ns=0, build_reserve_ns=self.build,
                       task_allocated_bytes=self.high, phase_allocated_bytes=self.phase['high'],
                       next_cpu_ns=next_cpu_ns, next_bytes=next_bytes,
                       completion_cpu_ns=self.completion[0], completion_bytes=self.completion[1],
                       task_limit_ns=self.limits[0], task_limit_bytes=self.limits[1],
                       phase_limit_ns=self.phase['cpu_limit'], phase_limit_bytes=self.phase['bytes_limit'],
                       cpu_baseline_ns=self.phase['cpu_origin'], current_cpu_ns=cpu,
                       sequence=self.index, expected_sequence=self.index,
                       nonce=self.session.nonce, expected_nonce=self.session.nonce, measurement_ok=True)
            decision = C.decide(req)
            C.immutable(out/'GATE.json', dict(request=req, decision=decision, scan=scan,
                        rules=rules, argv=argv, time_ns=time.monotonic_ns(), phase=self.phase['name']))
            if decision != 'ALLOW':
                raise RuntimeError(decision)
            def final_gate(before, absolute_cpu):
                fresh_cpu = absolute_cpu-self.cpu_origin
                self._retain_allocation(before['allocated_bytes'])
                fresh = dict(req, task_cpu_ns=fresh_cpu,
                             phase_cpu_ns=fresh_cpu-self.phase['cpu_origin'],
                             current_cpu_ns=fresh_cpu, task_allocated_bytes=self.high,
                             phase_allocated_bytes=self.phase['high'])
                return dict(request=fresh, decision=C.decide(fresh), scan=before,
                            invocation_cpu_origin_ns=self.cpu_origin+cpu,
                            cpu_cap_ns=next_cpu_ns,
                            bytes_cap=min(self.limits[1]-self.completion[1],
                                scan['allocated_bytes']+next_bytes,
                                self.phase['allocation_origin']+self.phase['bytes_limit']-self.completion[1]),
                            phase=self.phase['name'], original_gate_cpu_ns=cpu,
                            final_sample_cpu_ns=fresh_cpu,
                            last_sample_to_launch_unbounded=True)
            result = supervise(self.session, argv, out, timeout,
                               min(next_cpu_ns, self.limits[0]-cpu-self.build-self.completion[0],
                                   self.phase['cpu_limit']-(cpu-self.phase['cpu_origin'])-self.completion[0]),
                               min(self.limits[1]-self.completion[1], scan['allocated_bytes']+next_bytes,
                                   self.phase['allocation_origin']+self.phase['bytes_limit']-self.completion[1]),
                               root=self.root, rules=rules, sensor=self.sensor, final_gate=final_gate)
            # Retain every complete observed peak even on terminal/incomplete
            # supervision, before any subsequent boundary or phase handoff.
            self._retain_supervision(result)
            if not result['accounting_complete'] or self.session.stopped:
                raise RuntimeError('terminal supervision result')
            after, total_cpu = self._snapshot('post')
            # Estimate and phase overruns are terminal even with task-wide slack.
            if (total_cpu-cpu > next_cpu_ns or after['allocated_bytes']-scan['allocated_bytes'] > next_bytes
                    or total_cpu+self.build+self.completion[0] > self.limits[0]
                    or total_cpu-self.phase['cpu_origin']+self.completion[0] > self.phase['cpu_limit']
                    or self.high+self.completion[1] > self.limits[1]
                    or self.phase['high']+self.completion[1] > self.phase['bytes_limit']):
                raise RuntimeError('post-invocation estimate/phase/task overrun')
            C.immutable(out/'POST.json', dict(scan=after, task_cpu_ns=total_cpu,
                        task_high=self.high, phase=self.phase, build_charged_once_ns=self.build))
        except BaseException as e:
            self.session.stopped = True
            raw = {p.name:dict(bytes=p.stat().st_size, sha256=C.sha(p.read_bytes()))
                   for p in out.glob('*.bin')}
            C.immutable(out/'STOP.json', dict(status='INCOMPLETE STOP' if result is None or not result['accounting_complete'] else 'TERMINAL STOP',
                        exception=repr(e), measurement=result, raw=raw, no_further_command=True))
        C.immutable(out/'RESULT.json', dict(measurement=result, terminal=self.session.stopped))
        return out

    def close(self):
        self.session.require_next()
        # A handoff cannot bury a failed final measurement or spend global slack.
        try:
            scan, cpu = self._snapshot('handoff')
            if (cpu-self.phase['cpu_origin']+self.completion[0] > self.phase['cpu_limit']
                    or self.phase['high']+self.completion[1] > self.phase['bytes_limit']
                    or cpu+self.build+self.completion[0] > self.limits[0]
                    or self.high+self.completion[1] > self.limits[1]):
                raise RuntimeError('handoff phase/task exhausted')
            C.immutable(self.root/('CLOSE-'+self.phase['name']+'.json'), dict(scan=scan,
                        task_cpu_ns=cpu, task_high=self.high, phase=self.phase, build_charge=self.build))
            self.phase['closed'] = True
        except BaseException as e:
            self.session.stopped = True
            C.immutable(self.root/('HANDOFF-STOP-'+str(self.index)+'.json'),
                        dict(status='INCOMPLETE STOP', exception=repr(e), no_further_command=True))
            raise
