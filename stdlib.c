// GPL2.0 license
#define _CRT_SECURE_NO_WARNINGS

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <inttypes.h>
#include <ctype.h>
#include <time.h>

#define BUF_ALLOC(size) (char*)malloc(size)

static char* safe_strdup(const char* s) {
    if (!s) return NULL;
    size_t len = strlen(s) + 1;
    char* copy = malloc(len);
    if (!copy) return NULL;
    memcpy(copy, s, len);
    return copy;
}

#define FORMAT_INT_FUNC(name, type, fmt, bufsize) \
    char* name(type val) { \
        char* buf = BUF_ALLOC(bufsize); \
        if (!buf) return NULL; \
        snprintf(buf, bufsize, fmt, val); \
        return buf; \
    }

uintptr_t Cmalloc(size_t size) {
    return (uintptr_t)malloc(size);
}

void Cfree(uintptr_t ptr) {
    free((void*)ptr);
}

FORMAT_INT_FUNC(i64tostr, int64_t, "%" PRId64, 32)
FORMAT_INT_FUNC(i32tostr, int32_t, "%" PRId32, 16)
FORMAT_INT_FUNC(i16tostr, int16_t, "%" PRId16, 8)
FORMAT_INT_FUNC(i8tostr,  int8_t,  "%" PRId8,  8)

char* ftostr(double f) {
    char* buf = BUF_ALLOC(64);
    if (!buf) return NULL;
    snprintf(buf, 64, "%f", f);
    return buf;
}

char* btostr(bool b) {
    return safe_strdup(b ? "true" : "false");
}

char* tostr(const char* s) {
    return safe_strdup(s);
}

void free_str(char* s) {
    free(s);
}

void print(const char* s) {
    if (s) fputs(s, stdout);
}

void println(const char* s) {
    if (s) puts(s);
}

void eprint(const char* s) {
    if (s) fputs(s, stderr);
}

static char* concat_and_free(char* a, char* b) {
    if (!a || !b) {
        free(a);
        free(b);
        return NULL;
    }

    size_t la = strlen(a);
    size_t lb = strlen(b);
    if (la > SIZE_MAX - lb - 1) {
        free(a);
        free(b);
        return NULL;
    }

    char* out = BUF_ALLOC(la + lb + 1);
    if (!out) {
        free(a);
        free(b);
        return NULL;
    }

    memcpy(out, a, la);
    memcpy(out + la, b, lb + 1);
    free(a);
    free(b);
    return out;
}

char* sb_create() {
    return safe_strdup("");
}

char* sb_append_str(char* builder, const char* s) {
    return concat_and_free(builder, safe_strdup(s));
}

char* f32tostr(float f) {
    char buf[64];
    int n = snprintf(buf, sizeof(buf), "%.9g", (double)f);
    if (n < 0) return NULL;

    char* dot = strchr(buf, '.');
    if (dot) {
    char* end = buf + strlen(buf) - 1;
    while (end > dot && *end == '0') *end-- = '\0';
    if (end == dot) *end = '\0';
    }

    return safe_strdup(buf);
}

char* sb_append_float32(char* builder, float f) {
    char* num = f32tostr(f);
    return concat_and_free(builder, num);
}

uint32_t hex_to_rgba(const char* hex) {
    if (hex == NULL) return 0;

    size_t len = strlen(hex);

    if (len != 6 && len != 8) {
        return 0x00000000;
    }

    uint32_t value = (uint32_t)strtoul(hex, NULL, 16);

    if (len == 6) {
        value = (value << 8) | 0xFF;
    }

    return value;
}

char* itostr(int64_t i) {
    return i64tostr(i);
}

char* sb_append_int(char* builder, int64_t x) {
    char* num = i64tostr(x);
    return concat_and_free(builder, num);
}

char* sb_append_float(char* builder, double f) {
    char* num = ftostr(f);
    return concat_and_free(builder, num);
}

char* sb_append_bool(char* builder, bool bb) {
    char* boo = btostr(bb);
    return concat_and_free(builder, boo);
}

char* sb_finish(char* builder) {
    return builder;
}

char* input(const char* prompt) {
    if (prompt) {
        fputs(prompt, stdout);
        fflush(stdout);
    }

    size_t cap = 128;
    size_t len = 0;
    char* buf = malloc(cap);
    if (!buf) return NULL;

    int ch;
    while ((ch = fgetc(stdin)) != EOF && ch != '\n') {
        if (len + 1 >= cap) {
            if (cap > SIZE_MAX / 2) {
                free(buf);
                return NULL;
            }
            cap *= 2;
            char* tmp = realloc(buf, cap);
            if (!tmp) {
                free(buf);
                return NULL;
            }
            buf = tmp;
        }
        buf[len++] = (char)ch;
    }

    buf[len] = '\0';
    return buf;
}

int64_t iinput(const char* prompt) {
    char* s = input(prompt);
    if (!s) return 0;
    int64_t val = strtoll(s, NULL, 10);
    free(s);
    return val;
}

double finput(const char* prompt) {
    char* s = input(prompt);
    if (!s) return 0.0;
    double val = strtod(s, NULL);
    free(s);
    return val;
}

bool binput(const char* prompt) {
    char* s = input(prompt);
    if (!s) return false;
    bool result = (strcmp(s, "true") == 0 || strcmp(s, "1") == 0);
    free(s);
    return result;
}

char* sinput(const char* prompt) {
    return input(prompt);
}

int ilength(int64_t x) {
    if (x == 0) return 1;
    int len = (x < 0) ? 1 : 0;
    int64_t temp_x = x;
    if (temp_x < 0) {
        if (temp_x == INT64_MIN) return 20;
        temp_x = -temp_x;
    }
    while (temp_x > 0) {
        len++;
        temp_x /= 10;
    }
    return len;
}

int flength(double f) {
    char buf[64];
    int len = snprintf(buf, sizeof(buf), "%f", f);
    if (len < 0) return 0;

    while (len > 0 && buf[len - 1] == '0') len--;
    if (len > 0 && buf[len - 1] == '.') len--;
    return len;
}

int64_t slength(const char* s) {
    return s ? (int64_t)strlen(s) : 0;
}

char* read_file(const char* path) {
    if (!path) return safe_strdup("");

    FILE* f = fopen(path, "rb");
    if (!f) return safe_strdup("");

    if (fseek(f, 0, SEEK_END) != 0) {
        fclose(f);
        return safe_strdup("");
    }

    long len_l = ftell(f);
    if (len_l < 0) {
        fclose(f);
        return safe_strdup("");
    }
    size_t len = (size_t)len_l;

    rewind(f);
    char* buf = BUF_ALLOC(len + 1);
    if (!buf) {
        fclose(f);
        return safe_strdup("");
    }

    size_t r = fread(buf, 1, len, f);
    buf[r] = '\0';
    fclose(f);
    return buf;
}

bool write_file(const char* path, const char* content) {
    if (!path || !content) return false;
    FILE* f = fopen(path, "wb");
    if (!f) return false;
    size_t len = strlen(content);
    bool success = fwrite(content, 1, len, f) == len;
    fclose(f);
    return success;
}

bool append_file(const char* path, const char* content) {
    if (!path || !content) return false;
    FILE* f = fopen(path, "ab");
    if (!f) return false;
    size_t len = strlen(content);
    bool success = fwrite(content, 1, len, f) == len;
    fclose(f);
    return success;
}

bool file_exists(const char* path) {
    FILE* f = fopen(path, "rb");
    if (f) {
        fclose(f);
        return true;
    }
    return false;
}

char* read_lines(const char* path) {
    return read_file(path);
}

bool streq(const char* a, const char* b) {
    if (!a || !b) return false;
    return strcmp(a, b) == 0;
}

double tofloat(int64_t x) {
    return (double)x;
}

int64_t toint(double x) {
    return (int64_t)x;
}

int64_t rtoint(double x) {
    return (int64_t)(x + (x >= 0 ? 0.5 : -0.5));
}

char* rmtrz(double val) {
    char buf[64];
    snprintf(buf, sizeof(buf), "%.15g", val);

    char* dot = strchr(buf, '.');
    if (dot) {
        char* end = buf + strlen(buf) - 1;
        while (end > dot && *end == '0') *end-- = '\0';
        if (end == dot) *end = '\0';
    }

    return safe_strdup(buf);
}

bool contains(const char* str, const char* substr) {
    if (!str || !substr) return false;
    return strstr(str, substr) != NULL;
}

int countcontain(const char* str, const char* substr) {
    if (!str || !substr || !*substr) return 0;

    int count = 0;
    const char* temp = str;

    while ((temp = strstr(temp, substr)) != NULL) {
        count++;
        temp += strlen(substr);
    }

    return count;
}

char* charat(int64_t idx, const char* s) {
    if (!s) return safe_strdup("NULL");
    size_t len = strlen(s);
    if (idx == -1)                    return safe_strdup("SOF");
    if (idx == (int64_t)len)          return safe_strdup("EOF");
    if (idx < 0 || (size_t)idx >= len) return safe_strdup("OOB");
    char c = s[(size_t)idx];
    if (c == '\n' || c == '\r')
        return safe_strdup("NL");
    char tmp[2] = { c, '\0' };
    return safe_strdup(tmp);
}

bool isalnum_at(int64_t idx, const char* s) {
    if (!s) return false;
    if (idx < 0) return false;
    size_t len = strlen(s);
    if ((size_t)idx >= len) return false;
    return isalnum((unsigned char)s[idx]) != 0;
}
bool isspace_at(int64_t idx, const char* s) {
    if (!s) return false;
    if (idx < 0) return false;
    size_t len = strlen(s);
    if ((size_t)idx >= len) return false;
    return isspace((unsigned char)s[idx]) != 0;
}
bool isalpha_at(int64_t idx, const char* s) {
    if (!s) return false;
    if (idx < 0) return false;
    size_t len = strlen(s);
    if ((size_t)idx >= len) return false;
    return isalpha((unsigned char)s[idx]) != 0;
}
bool isnum_at(int64_t idx, const char* s) {
    if (!s) return false;
    if (idx < 0) return false;
    size_t len = strlen(s);
    if ((size_t)idx >= len) return false;
    return isdigit((unsigned char)s[idx]) != 0;
}

char* tac(const char* s) {
    if (!s) return NULL;
    char* result = safe_strdup(s);
    if (!result) return NULL;

    for (char* p = result; *p; ++p) {
        *p = (char)toupper((unsigned char)*p);
    }

    return result;
}

char* tal(const char* s) {
    if (!s) return NULL;
    char* result = safe_strdup(s);
    if (!result) return NULL;

    for (char* p = result; *p; ++p) {
        *p = (char)tolower((unsigned char)*p);
    }

    return result;
}

const char* get_os() {
#if defined(_WIN32)
    return "windows";
#elif defined(__APPLE__)
    return "macos";
#elif defined(__linux__)
    return "linux";
#elif defined(__unix__)
    return "unix";
#else
    return "unknown";
#endif
}

int8_t   fcasti8(double d)  { return (int8_t)d; }
int16_t  fcasti16(double d) { return (int16_t)d; }
int32_t  fcasti32(double d) { return (int32_t)d; }
int64_t  fcasti64(double d) { return (int64_t)d; }
int64_t  fcasti(double d)   { return (int64_t)d; }

double i8castf(int8_t i)    { return (double)i; }
double i16castf(int16_t i)  { return (double)i; }
double i32castf(int32_t i)  { return (double)i; }
double i64castf(int64_t i)  { return (double)i; }
double icastf(int64_t i)    { return (double)i; }

typedef enum {
    TAG_INT = 1,
    TAG_FLOAT  = 2,
    TAG_BOOL   = 3,
    TAG_STRING = 4
} UnionTag;

typedef struct {
    int64_t tag;
    union {
        int64_t i;
        double   f;
        bool       b;
        const char *s;
    } value;
} ValueUnion;

int64_t Umake_int(int64_t x) {
    ValueUnion *v = malloc(sizeof *v);
    if (!v) return 0;
    v->tag     = TAG_INT;
    v->value.i   = x;
    return (int64_t)(uintptr_t)v;
}

int64_t Umake_float(double f) {
    ValueUnion *v = malloc(sizeof *v);
    if (!v) return 0;
    v->tag     = TAG_FLOAT;
    v->value.f   = f;
    return (int64_t)(uintptr_t)v;
}

int64_t Umake_bool(bool b) {
    ValueUnion *v = malloc(sizeof *v);
    if (!v) return 0;
    v->tag     = TAG_BOOL;
    v->value.b   = b;
    return (int64_t)(uintptr_t)v;
}

int64_t Umake_string(const char *s) {
    if (!s) return 0;
    ValueUnion *v = malloc(sizeof *v);
    if (!v) return 0;
    v->tag = TAG_STRING;
    v->value.s = safe_strdup(s);
    if (!v->value.s) {
        free(v);
        return 0;
    }
    return (int64_t)(uintptr_t)v;
}

int64_t Uget_tag(int64_t h) {
    ValueUnion *v = (ValueUnion*)(uintptr_t)h;
    return v ? v->tag : 0;
}

int64_t Uget_int(int64_t h) {
    ValueUnion *v = (ValueUnion*)(uintptr_t)h;
    return (v && v->tag == TAG_INT) ? v->value.i : 0;
}

double Uget_float(int64_t h) {
    ValueUnion *v = (ValueUnion*)(uintptr_t)h;
    return (v && v->tag == TAG_FLOAT) ? v->value.f : 0.0;
}

bool Uget_bool(int64_t h) {
    ValueUnion *v = (ValueUnion*)(uintptr_t)h;
    return (v && v->tag == TAG_BOOL) ? v->value.b : false;
}

char* Uget_string(int64_t h) {
    ValueUnion *v = (ValueUnion*)(uintptr_t)h;
    if (!v) return safe_strdup("(invalid)");
    if (v->tag == TAG_STRING && v->value.s) {
        return safe_strdup(v->value.s);
    }
    return safe_strdup("(invalid)");
}

void Ufree_union(int64_t h) {
    ValueUnion *v = (ValueUnion*)(uintptr_t)h;
    if (!v) return;
    if (v->tag == TAG_STRING && v->value.s) {
        free((void*)v->value.s);
    }
    free(v);
}

const char* get_os_max_bits() {
#if defined(_WIN64) || defined(__x86_64__) || defined(__ppc64__) || defined(__aarch64__)
    return "64";
#elif defined(_WIN32) || defined(__i386__) || defined(__arm__)
    return "32";
#else
    return sizeof(void*) == 8 ? "64" :
           sizeof(void*) == 4 ? "32" : "unknown";
#endif
}
