#define _POSIX_C_SOURCE 200809L
#include <stdint.h>
#include <stddef.h>
#include <limits.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>
#include <errno.h>
#include <signal.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>

#define MAX_BACKLOG 1024
#define MAX_BODY_BYTES (10 * 1024 * 1024)

static int safe_write_all(int fd, const char *buf, size_t len) {
    if (fd < 0 || buf == NULL) return -1;
    size_t remaining = len;
    const char *p = buf;
    while (remaining > 0) {
        ssize_t w = write(fd, p, remaining);
        if (w < 0) {
            if (errno == EINTR) continue;
            if (errno == EAGAIN || errno == EWOULDBLOCK) {
                return -1;
            }
            return -1;
        }
        remaining -= (size_t)w;
        p += w;
    }
    return 0;
}

int64_t create_server(int64_t port64, int64_t backlog64) {
    signal(SIGPIPE, SIG_IGN);

    if (port64 <= 0 || port64 > 65535) {
        fprintf(stderr, "create_server: invalid port %lld\n", (long long)port64);
        return -1;
    }
    if (backlog64 <= 0) backlog64 = 1;
    if (backlog64 > MAX_BACKLOG) backlog64 = MAX_BACKLOG;

    int port = (int)port64;
    int backlog = (int)backlog64;

    int s = socket(AF_INET, SOCK_STREAM, 0);
    if (s < 0) {
        perror("create_server: socket");
        return -1;
    }

    int opt = 1;
    if (setsockopt(s, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt)) < 0) {
        perror("create_server: setsockopt");
        close(s);
        return -1;
    }

    struct sockaddr_in addr;
    memset(&addr, 0, sizeof(addr));
    addr.sin_family = AF_INET;
    addr.sin_port = htons((uint16_t)port);
    addr.sin_addr.s_addr = htonl(INADDR_ANY);

    if (bind(s, (struct sockaddr*)&addr, sizeof(addr)) < 0) {
        perror("create_server: bind");
        close(s);
        return -1;
    }

    if (listen(s, backlog) < 0) {
        perror("create_server: listen");
        close(s);
        return -1;
    }

    return (int64_t)s;
}

int64_t accept_client(int64_t listen_fd64) {
    if (listen_fd64 < 0 || listen_fd64 > INT_MAX) {
        fprintf(stderr, "accept_client: invalid listen fd %lld\n", (long long)listen_fd64);
        return -1;
    }
    int listen_fd = (int)listen_fd64;

    struct sockaddr_in cli;
    socklen_t len = sizeof(cli);
    int c = accept(listen_fd, (struct sockaddr*)&cli, &len);
    if (c < 0) {
        return -1;
    }
    return (int64_t)c;
}

int64_t send_response(int64_t client_fd64, const char* body) {
    if (client_fd64 < 0 || client_fd64 > INT_MAX) {
        fprintf(stderr, "send_response: invalid fd %lld\n", (long long)client_fd64);
        return -1;
    }
    if (body == NULL) {
        fprintf(stderr, "send_response: body is NULL\n");
        return -1;
    }
    int client_fd = (int)client_fd64;

    size_t body_len = strnlen(body, (size_t)MAX_BODY_BYTES + 1);
    if (body_len == 0 && body[0] == '\0') {
    } else if (body_len > (size_t)MAX_BODY_BYTES) {
        fprintf(stderr, "send_response: body too large (%zu bytes) max %d\n", body_len, MAX_BODY_BYTES);
        return -1;
    }

    char header[512];
    int hdr_n = snprintf(header, sizeof(header),
        "HTTP/1.1 200 OK\r\n"
        "Content-Type: text/html; charset=utf-8\r\n"
        "Content-Length: %zu\r\n"
        "Connection: close\r\n"
        "\r\n",
        body_len);

    if (hdr_n < 0 || hdr_n >= (int)sizeof(header)) {
        fprintf(stderr, "send_response: header formatting failed\n");
        return -1;
    }

    if (safe_write_all(client_fd, header, (size_t)hdr_n) != 0) {
        return -1;
    }
    if (body_len > 0) {
        if (safe_write_all(client_fd, body, body_len) != 0) {
            return -1;
        }
    }
    return 0;
}

int64_t close_fd(int64_t fd64) {
    if (fd64 < 0 || fd64 > INT_MAX) {
        fprintf(stderr, "close_fd: invalid fd %lld\n", (long long)fd64);
        return -1;
    }
    int fd = (int)fd64;
    if (close(fd) < 0) {
        perror("close_fd");
        return -1;
    }
    return 0;
}