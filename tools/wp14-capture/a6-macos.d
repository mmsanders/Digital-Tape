/*
 * a6-macos.d — record every open/pread/pwrite/flush/close the SHIPPED tapectl
 * makes, from the kernel's syscall boundary. Software #425; recipe in
 * docs/WP14-NATIVE-CAPTURE.md. Injects nothing into tapectl and changes no call.
 *
 *   sudo dtrace -q -s a6-macos.d -o a6-verify.trace -c './tapectl verify /dev/diskN'
 *
 * -c makes dtrace start tapectl itself, so $target is exactly tapectl's PID and
 * no call can happen before tracing starts. Use -c ONLY for read-only verify:
 * dtrace kills a process it started if dtrace is stopped first.
 *
 * Output: one "A6 key=value ..." line per call, read by a6check.py --format dtrace.
 * Errors and drops that dtrace itself reports go to its stderr; keep that too.
 */

#pragma D option quiet
#pragma D option zdefs
#pragma D option bufsize=8m
#pragma D option switchrate=50hz

dtrace:::BEGIN
{
	printf("A6 trace tool=dtrace target=%d\n", $target);
}

syscall::open:entry, syscall::open_nocancel:entry
/pid == $target/
{
	self->opath = copyinstr(arg0);
	self->oflags = arg1;
	self->opening = 1;
}

syscall::openat:entry, syscall::openat_nocancel:entry
/pid == $target/
{
	self->opath = copyinstr(arg1);
	self->oflags = arg2;
	self->opening = 1;
}

syscall::open:return, syscall::open_nocancel:return,
syscall::openat:return, syscall::openat_nocancel:return
/pid == $target && self->opening/
{
	printf("A6 pid=%d op=open ret=%d errno=%d flags=0x%x path=%s\n",
	    pid, (int)arg0, errno, (int)self->oflags, self->opath);
	self->opening = 0;
}

syscall::pread:entry, syscall::pread_nocancel:entry,
syscall::pwrite:entry, syscall::pwrite_nocancel:entry
/pid == $target/
{
	self->fd = arg0;
	self->len = arg2;
	self->off = (int64_t)arg3;
	self->t0 = timestamp;
	self->io = 1;
}

syscall::pread:return, syscall::pread_nocancel:return
/pid == $target && self->io/
{
	printf("A6 pid=%d op=read fd=%d off=%d len=%d ret=%d errno=%d ns=%d\n",
	    pid, (int)self->fd, self->off, (int64_t)self->len, (int64_t)arg0, errno,
	    timestamp - self->t0);
	self->io = 0;
}

syscall::pwrite:return, syscall::pwrite_nocancel:return
/pid == $target && self->io/
{
	printf("A6 pid=%d op=write fd=%d off=%d len=%d ret=%d errno=%d ns=%d\n",
	    pid, (int)self->fd, self->off, (int64_t)self->len, (int64_t)arg0, errno,
	    timestamp - self->t0);
	self->io = 0;
}

/* F_FULLFSYNC is fcntl command 51. */
syscall::fcntl:entry, syscall::fcntl_nocancel:entry
/pid == $target && arg1 == 51/
{
	self->fd = arg0;
	self->t0 = timestamp;
	self->fl = 1;
}

syscall::fcntl:return, syscall::fcntl_nocancel:return
/pid == $target && self->fl/
{
	printf("A6 pid=%d op=flush how=F_FULLFSYNC fd=%d ret=%d errno=%d ns=%d\n",
	    pid, (int)self->fd, (int)arg0, errno, timestamp - self->t0);
	self->fl = 0;
}

/* DKIOCSYNCHRONIZECACHE is _IO('d', 22) = 0x20006416. */
syscall::ioctl:entry
/pid == $target && (uint32_t)arg1 == 0x20006416/
{
	self->fd = arg0;
	self->t0 = timestamp;
	self->sc = 1;
}

syscall::ioctl:return
/pid == $target && self->sc/
{
	printf("A6 pid=%d op=flush how=DKIOCSYNCHRONIZECACHE fd=%d ret=%d errno=%d ns=%d\n",
	    pid, (int)self->fd, (int)arg0, errno, timestamp - self->t0);
	self->sc = 0;
}

syscall::close:entry, syscall::close_nocancel:entry
/pid == $target/
{
	printf("A6 pid=%d op=close fd=%d\n", pid, (int)arg0);
}

/* tapectl's own exit status: dtrace -c reports dtrace's, not the child's. */
syscall::exit:entry
/pid == $target/
{
	printf("A6 pid=%d op=exit status=%d\n", pid, (int)arg0);
}
