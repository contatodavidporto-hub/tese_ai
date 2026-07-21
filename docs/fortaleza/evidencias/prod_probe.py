"""
Sondagem NÃO-DESTRUTIVA de produção (nossos ativos): TLS + headers de segurança + presença de rate-limit.
Regras de engajamento: só GET/HEAD read-only, nosso domínio, para ao primeiro sinal de impacto.
"""
import ssl
import socket
import json
import time
import sys

try:
    import httpx
except Exception as e:
    print("HTTPX_MISSING", e)
    sys.exit(2)

FRONT = "https://tese-ai.vercel.app"
# rotas estáticas/baratas, read-only
ROTAS = ["/", "/como-funciona", "/historico", "/glossario", "/sobre", "/cobertura"]

SEC_HEADERS = [
    "content-security-policy",
    "strict-transport-security",
    "x-frame-options",
    "x-content-type-options",
    "referrer-policy",
    "permissions-policy",
    "cross-origin-opener-policy",
    "cross-origin-resource-policy",
    "cross-origin-embedder-policy",
    "x-xss-protection",
    "cache-control",
    "x-powered-by",
    "server",
    "x-vercel-id",
    "x-ratelimit-limit",
    "x-ratelimit-remaining",
    "retry-after",
]


def tls_info(host, port=443):
    ctx = ssl.create_default_context()
    for attempt in range(4):
        try:
            with socket.create_connection((host, port), timeout=15) as sock:
                with ctx.wrap_socket(sock, server_hostname=host) as ss:
                    cert = ss.getpeercert()
                    return {
                        "tls_version": ss.version(),
                        "cipher": ss.cipher(),
                        "cert_subject": dict(x[0] for x in cert.get("subject", [])),
                        "cert_issuer": dict(x[0] for x in cert.get("issuer", [])),
                        "cert_notAfter": cert.get("notAfter"),
                        "cert_san_count": len(cert.get("subjectAltName", [])),
                    }
        except Exception as e:
            if attempt == 3:
                return {"error": f"{type(e).__name__}: {e}"}
            time.sleep(2)


def probe():
    out = {"tls": {}, "rotas": {}, "notas": []}
    host = FRONT.replace("https://", "").split("/")[0]
    out["tls"] = tls_info(host)

    headers_ua = {"User-Agent": "fortaleza-audit-probe/1.0 (authorized self-scan)"}
    with httpx.Client(http2=False, timeout=20, headers=headers_ua, follow_redirects=False) as client:
        for rota in ROTAS:
            url = FRONT + rota
            rec = None
            for attempt in range(4):
                try:
                    r = client.get(url)
                    hdrs = {k.lower(): v for k, v in r.headers.items()}
                    rec = {
                        "status": r.status_code,
                        "http_version": r.http_version,
                        "sec_headers": {h: hdrs.get(h) for h in SEC_HEADERS if h in hdrs},
                        "missing": [h for h in SEC_HEADERS[:11] if h not in hdrs],
                        "body_bytes": len(r.content),
                    }
                    break
                except Exception as e:
                    if attempt == 3:
                        rec = {"error": f"{type(e).__name__}: {e}"}
                    else:
                        time.sleep(2)
            out["rotas"][rota] = rec
            time.sleep(0.5)  # gentileza: não martelar
    return out


if __name__ == "__main__":
    print(json.dumps(probe(), indent=2, ensure_ascii=False, default=str))
