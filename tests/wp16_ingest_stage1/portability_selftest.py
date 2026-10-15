"""Canonical package names across host path syntaxes; no candidate acceptance."""
from pathlib import PurePosixPath,PureWindowsPath
from check_pins import relative_name

def run():
    names=['README.md','authority/WP-16.md','extra-encoded/PROVENANCE.md']
    for cls,root in [(PurePosixPath,PurePosixPath('/package')),
                     (PureWindowsPath,PureWindowsPath('C:/package'))]:
        actual={relative_name(root/name,root) for name in names}
        assert actual==set(names)
        assert actual!={*names,'unindexed.txt'}
        assert actual!={names[0],names[1]}
    root=PureWindowsPath('C:/package')
    legacy={str((root/name).relative_to(root)) for name in names}
    assert legacy!=set(names),'legacy Windows separator fault escaped'
    print('Package path portability PASS: POSIX/Windows positives; legacy separator, omitted/extra member controls')

if __name__=='__main__':run()
