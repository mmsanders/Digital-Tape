/*
 * Verifier-owned WP-13 tape_instance_size probe.
 * Software may only supply the public header path and linked product engine.
 */
#ifndef TAPE_PUBLIC_HEADER
#define TAPE_PUBLIC_HEADER "tape.h"
#endif
#include TAPE_PUBLIC_HEADER
#include <stdio.h>

int main(void)
{
    printf("%zu\n", tape_instance_size());
    return 0;
}
