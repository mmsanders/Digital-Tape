/*
 * safety.c — the §5 policy (pure) and the §2 path forms.
 * Normative: docs/WP14-CLI-CONTRACT.md §2 and §5.
 */

#include "safety.h"

#include <ctype.h>
#include <string.h>

enum refusal safety_policy(const struct device_facts *f, int provision, int erase_matches)
{
    int i;
    if (!f->whole_device)                     { return REFUSE_NOT_WHOLE_DEVICE; }
    if (!f->removable && !f->sd_bus)          { return REFUSE_NOT_REMOVABLE; }
    if (f->bytes > SAFETY_TOO_LARGE)          { return REFUSE_TOO_LARGE; }
    if (f->holds_os)                          { return REFUSE_SYSTEM_DISK; }
    if (f->n_mounted < 0 || f->n_mounted > SAFETY_MAX_MOUNTS) { return REFUSE_FOREIGN_MOUNT; }
    for (i = 0; i < f->n_mounted; i++) {
        if (!safety_mount_is_own_p1(f, i))    { return REFUSE_FOREIGN_MOUNT; }
    }
    if (provision && !erase_matches)          { return REFUSE_ERASE_NOT_CONFIRMED; }
    return REFUSE_NONE;
}

int safety_mount_is_own_p1(const struct device_facts *f, int i)
{
    return f->layout_ok && f->mounted[i].partition == 1;
}

const char *refusal_id(enum refusal r)
{
    switch (r) {
    case REFUSE_NOT_WHOLE_DEVICE:    return "REFUSE_NOT_WHOLE_DEVICE";
    case REFUSE_NOT_REMOVABLE:       return "REFUSE_NOT_REMOVABLE";
    case REFUSE_TOO_LARGE:           return "REFUSE_TOO_LARGE";
    case REFUSE_SYSTEM_DISK:         return "REFUSE_SYSTEM_DISK";
    case REFUSE_FOREIGN_MOUNT:       return "REFUSE_FOREIGN_MOUNT";
    case REFUSE_ERASE_NOT_CONFIRMED: return "REFUSE_ERASE_NOT_CONFIRMED";
    case REFUSE_NONE:                break;
    }
    return "REFUSE_NONE";
}

const char *refusal_sentence(enum refusal r)
{
    switch (r) {
    case REFUSE_NOT_WHOLE_DEVICE:
        return "This is not a whole disk. Name the whole card, not a partition or volume.";
    case REFUSE_NOT_REMOVABLE:
        return "This disk is not removable, so it is not a memory card.";
    case REFUSE_TOO_LARGE:
        return "This disk is larger than 128 GiB, so it is not a Digital Tape card.";
    case REFUSE_SYSTEM_DISK:
        return "This disk holds the running system, a boot volume or swap.";
    case REFUSE_FOREIGN_MOUNT:
        return "A volume on this disk is in use. Eject it in the operating system first.";
    case REFUSE_ERASE_NOT_CONFIRMED:
        return "Provisioning erases the card. Repeat the device path after --erase to confirm.";
    case REFUSE_NONE:
        break;
    }
    return "";
}

/* ------------------------------------------------------------- path forms */

static int all_digits(const char *s)
{
    if (*s == '\0') { return 0; }
    for (; *s; s++) { if (!isdigit((unsigned char)*s)) { return 0; } }
    return 1;
}

#if defined(_WIN32)

static int ci_prefix(const char *s, const char *p)
{
    for (; *p; s++, p++) {
        if (tolower((unsigned char)*s) != tolower((unsigned char)*p)) { return 0; }
    }
    return 1;
}

int path_is_device_form(const char *path)
{
    size_t n = strlen(path);
    if (ci_prefix(path, "\\\\.\\") || ci_prefix(path, "\\\\?\\") || ci_prefix(path, "//./")) { return 1; }
    /* A bare drive letter, "E:" or "E:\", names a volume. */
    if ((n == 2 || (n == 3 && (path[2] == '\\' || path[2] == '/')))
        && isalpha((unsigned char)path[0]) && path[1] == ':') { return 1; }
    return 0;
}

int path_is_whole_form(const char *path)
{
    return ci_prefix(path, "\\\\.\\PhysicalDrive") && all_digits(path + 17);
}

#else /* POSIX */

int path_is_device_form(const char *path)
{
    return strncmp(path, "/dev/", 5) == 0;
}

int path_is_whole_form(const char *path)
{
#if defined(__APPLE__)
    const char *p = path;
    if (strncmp(p, "/dev/", 5) != 0) { return 0; }
    p += 5;
    if (*p == 'r') { p++; }
    return strncmp(p, "disk", 4) == 0 && all_digits(p + 4);
#else
    const char *p = path;
    if (strncmp(p, "/dev/sd", 7) == 0) {
        p += 7;
        if (*p == '\0') { return 0; }
        for (; *p; p++) { if (*p < 'a' || *p > 'z') { return 0; } }
        return 1;
    }
    if (strncmp(p, "/dev/mmcblk", 11) == 0) { return all_digits(p + 11); }
    return 0;
#endif
}

#endif
