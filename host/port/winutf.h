/*
 * winutf.h — UTF-8 <-> UTF-16 for the Windows port and probe.
 */
#ifndef HOST_WINUTF_H
#define HOST_WINUTF_H
#if defined(_WIN32)
#include <windows.h>

/* 0 on success. */
static inline int utf8_to_wide(const char *s, wchar_t *out, int cap)
{
    return MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, s, -1, out, cap) > 0 ? 0 : -1;
}

static inline void wide_to_utf8(const wchar_t *s, char *out, int cap)
{
    if (WideCharToMultiByte(CP_UTF8, 0, s, -1, out, cap, NULL, NULL) <= 0 && cap > 0) { out[0] = '\0'; }
}
#endif
#endif
