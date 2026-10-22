"""Bind a future C capture without invoking it. Costs/schedule stay independently issued."""
from pathlib import Path
import sys
import controller as C

RUNTIME = '55552ad4fe57e99827ab8eb016044d0486017877'


def bind(task_root, payload_path, payload, interpreter, strace, tapectl):
    root = Path(task_root).resolve(strict=True)
    if payload['source'] != RUNTIME or payload['task_root'] != str(root):
        raise ValueError('unissued source/task binding')
    # Preserve the retained514 exact strace selection and original native argv.
    argv = payload['argv']
    if argv[:10] != [str(strace), '-f', '-qq', '-yy', '-s', '512', '-e',
                      'trace=openat,lseek,write,pwrite64,fsync,fdatasync', '-o', payload['syscall_path']]:
        raise ValueError('changed syscall capture predicate')
    if len(argv) < 12 or argv[10] != str(tapectl):
        raise ValueError('native command identity missing')
    if any(not k.startswith('TAPECTL_') for k in payload['environment']):
        raise ValueError('unbound environment')
    wrapper = Path(__file__).with_name('crash_child.py').resolve()
    for p in (Path(payload_path), Path(payload['domain_dir']), Path(payload['syscall_path']),
              Path(tapectl), wrapper, Path(__file__), *map(Path, payload['owned_paths'])):
        if not p.resolve().is_relative_to(root):
            raise ValueError('source/build/work/raw/temp/archive must share census root')
    C.immutable(payload_path, payload)
    py = str(Path(interpreter).resolve())
    root_argv = [py, '-B', str(wrapper), '--input', str(payload_path),
                 '--sha', C.sha(Path(payload_path).read_bytes())]
    inputs = {str(p):C.sha(Path(p).read_bytes()) for p in
              (py, wrapper, Path(__file__), strace, tapectl, *payload['inputs'])}
    rules = []
    for role, command, parents in [('adapter', root_argv, []), ('strace', argv, ['adapter']),
                                    ('tapectl', argv[10:], ['strace'])]:
        rules.append(dict(role=role, argv=command, parents=parents, max_live=1,
                          exe_sha256=C.sha(Path(command[0]).read_bytes()), inputs=inputs))
    return root_argv, rules
