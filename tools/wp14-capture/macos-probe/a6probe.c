/* a6probe — capability probe for fs_usage on macOS (Software #438). Not tapectl.
 * Issues one pread per "offset:length" argument on FILE and prints what each returned,
 * so a capture's O= and B= fields can be compared with known values. */
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

int main(int argc, char **argv)
{
    static char buf[4096];
    int fd, i;
    if (argc < 3) { fprintf(stderr, "usage: a6probe FILE OFFSET:LEN...\n"); return 2; }
    fd = open(argv[1], O_RDONLY);
    if (fd < 0) { perror("open"); return 1; }
    for (i = 2; i < argc; i++) {
        char *colon;
        unsigned long long off = strtoull(argv[i], &colon, 0);
        size_t len = (size_t)strtoul(colon + 1, NULL, 0);
        ssize_t n = pread(fd, buf, len > sizeof buf ? sizeof buf : len, (off_t)off);
        printf("pread off=0x%llx len=0x%zx -> %zd\n", off, len, n);
    }
    close(fd);
    return 0;
}
