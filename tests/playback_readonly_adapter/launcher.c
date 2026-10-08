/* Host-only executable entry; all public-call binding lives in adapter.py. */
#define _POSIX_C_SOURCE 200809L
#include <unistd.h>
#include <stdlib.h>
#include <stdio.h>
#ifndef ADAPTER_PATH
#error ADAPTER_PATH required
#endif
#ifndef LIBRARY_PATH
#error LIBRARY_PATH required
#endif
int main(void)
{
    if (setenv("TAPE_READ1_LIBRARY", LIBRARY_PATH, 1) != 0) { return 2; }
    execlp("python3", "python3", "-B", ADAPTER_PATH, (char *)NULL);
    perror("python3");
    return 2;
}
