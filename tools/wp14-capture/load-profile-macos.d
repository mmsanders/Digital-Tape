/*
 * load-profile-macos.d — OPTIONAL per-call latency summary for a tapectl load
 * that is happening anyway. Software #425; see docs/WP14-NATIVE-CAPTURE.md §4.
 * Not executed in #425; no load is requested to obtain it.
 *
 * Start in a SECOND Terminal before the load; it attaches to no process and
 * never starts or stops tapectl. Press Ctrl-C after the load has returned:
 *
 *   sudo dtrace -q -s load-profile-macos.d -o load-profile.txt
 *
 * Never use -c or -p with a load: dtrace may kill a process it started.
 * Prints, per call type, count, total and a power-of-two latency histogram (ns).
 */

#pragma D option quiet
#pragma D option zdefs

dtrace:::BEGIN
{
	printf("A6 profile tool=dtrace execname=tapectl\n");
}

syscall::pwrite:entry, syscall::pwrite_nocancel:entry
/execname == "tapectl"/
{
	self->w = timestamp;
}

syscall::pwrite:return, syscall::pwrite_nocancel:return
/self->w/
{
	@n["write"] = count();
	@t["write"] = sum(timestamp - self->w);
	@q["write"] = quantize(timestamp - self->w);
	self->w = 0;
}

syscall::fcntl:entry, syscall::fcntl_nocancel:entry
/execname == "tapectl" && arg1 == 51/
{
	self->f = timestamp;
}

syscall::ioctl:entry
/execname == "tapectl" && (uint32_t)arg1 == 0x20006416/
{
	self->f = timestamp;
}

syscall::fcntl:return, syscall::fcntl_nocancel:return, syscall::ioctl:return
/self->f/
{
	@n["flush"] = count();
	@t["flush"] = sum(timestamp - self->f);
	@q["flush"] = quantize(timestamp - self->f);
	self->f = 0;
}

proc:::exit
/execname == "tapectl"/
{
	printf("A6 pid=%d op=exit\n", pid);
}

dtrace:::END
{
	printa("A6 count %s %@d\n", @n);
	printa("A6 total_ns %s %@d\n", @t);
	printa(@q);
}
