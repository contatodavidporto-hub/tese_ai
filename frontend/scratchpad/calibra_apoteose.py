"""
Onda 0 (Fundacao) - missao APOTEOSE, 2026-07-13.

calibra_tokens.py (do worktree wt-imersivo/precedente) so cobre a recalibracao
de --ink-tertiary/--border-field contra o pico da luz fria ambiente; nao
modela os DOIS emissores NOVOS desta missao:

  1. `.ticker-luz` (specular dourado que segue o ponteiro em cards da Banca,
     masthead h2 de /tese, TickerCombobox input, tickers do /historico) —
     composita --valor-brilho/--accent-valor em alfa `--ticker-luz-alfa`
     sobre bg-card / bg-elevated (o pico, cursor parado exatamente em cima).
  2. Halo do Box CVM (peca de honra, D5) — composita --accent-valor em alfa
     `--cvm-halo-alfa` sobre --warn-bg (aviso-fundo), onde vive o texto do
     disclaimer (--warn-text/--warn-border).

Mesmo metodo do precedente (calibra_tokens.py, 2026-07-12): compositing
sequencial src-over em sRGB GAMA (nao linear) - identico ao navegador
pintando `background: rgb(fg / alfa)` sobre bg; luminancia relativa WCAG.
"""
import argparse


def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))


def srgb_to_linear(c):
    c = c / 255.0
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def relative_luminance(rgb):
    r, g, b = rgb
    return 0.2126 * srgb_to_linear(r) + 0.7152 * srgb_to_linear(g) + 0.0722 * srgb_to_linear(b)


def contrast_ratio(rgb1, rgb2):
    l1, l2 = relative_luminance(rgb1), relative_luminance(rgb2)
    l1, l2 = max(l1, l2), min(l1, l2)
    return (l1 + 0.05) / (l2 + 0.05)


def alpha_composite(fg_rgb, alpha, bg_rgb):
    return tuple(fg_rgb[i] * alpha + bg_rgb[i] * (1 - alpha) for i in range(3))


def compor(bg_hex, camadas):
    """camadas = [(hex, alfa), ...] da mais funda a mais rasa."""
    out = hex_to_rgb(bg_hex)
    for cor_hex, alfa in camadas:
        if alfa > 0:
            out = alpha_composite(hex_to_rgb(cor_hex), alfa, out)
    return out


# ---------------------------------------------------------------------------
# Tokens atuais (globals.css, Onda 0 pos-emenda MATERIA VIVA)
# ---------------------------------------------------------------------------
TOK = {
    "CLARO": {
        "bg_page": "#f6f6f3",
        "bg_card": "#fdfdfb",
        "bg_elevated": "#ffffff",
        "valor_brilho": "#f0dfae",
        "accent_valor": "#8a6415",
        "ink_tertiary": "#4c4f56",  # 2a passada Onda 3 (jah recalibrado)
        "ink_secondary": "#4a4f58",
        "ink_primary": "#16181d",
        "border_field": "#6a6963",  # 2a passada Onda 3
        "warn_bg": "#fbf0d9",
        "warn_text": "#7a5200",
        "warn_border": "#a3781a",
    },
    "ESCURO": {
        "bg_page": "#101216",
        "bg_card": "#16181d",
        "bg_elevated": "#1d2027",
        "valor_brilho": "#f7ecc9",
        "accent_valor": "#d9b354",
        "ink_tertiary": "#a5a49e",
        "ink_secondary": "#b5b3ac",
        "ink_primary": "#ebe9e4",
        "border_field": "#7e8691",
        "warn_bg": "#2a2214",
        "warn_text": "#e6c172",
        "warn_border": "#957634",
    },
}


def cenario_ticker_luz(alfa_claro, alfa_escuro):
    print("=" * 78)
    print(f"CENARIO 1 — .ticker-luz especular (--valor-brilho @ alfa) sobre bg-card/elevated")
    print(f"  alfa candidato: claro={alfa_claro}  escuro={alfa_escuro}")
    print("=" * 78)
    reprova = False
    for tema, alfa in (("CLARO", alfa_claro), ("ESCURO", alfa_escuro)):
        t = TOK[tema]
        for bg_nome in ("bg_card", "bg_elevated"):
            bg = t[bg_nome]
            pico = compor(bg, [(t["valor_brilho"], alfa)])
            pico_hex = "#" + "".join(f"{round(c):02x}" for c in pico)
            print(f"\n  -- {tema} sobre {bg_nome} ({bg}) -> pico {pico_hex} --")
            for nome_tok, minimo in (
                ("ink_tertiary", 4.5),
                ("ink_secondary", 4.5),
                ("border_field", 3.0),
                ("ink_primary", 4.5),
            ):
                r = contrast_ratio(hex_to_rgb(t[nome_tok]), pico)
                flag = "OK  " if r >= minimo else "FALHA"
                if r < minimo:
                    reprova = True
                print(f"    {flag} {nome_tok:14s} ({t[nome_tok]}) -> {r:.3f}:1  (min {minimo})")
    print(f"\n  VEREDITO cenario 1: {'REPROVOU (recuo)' if reprova else 'PASSOU (todos os pares)'}")
    return not reprova


def cenario_cvm_halo(alfa_claro):
    print("\n" + "=" * 78)
    print(f"CENARIO 2 — halo do Box CVM (--accent-valor @ alfa) sobre --warn-bg (claro; dark = keyline, sem halo)")
    print(f"  alfa candidato claro: {alfa_claro}")
    print("=" * 78)
    reprova = False
    t = TOK["CLARO"]
    pico = compor(t["warn_bg"], [(t["accent_valor"], alfa_claro)])
    pico_hex = "#" + "".join(f"{round(c):02x}" for c in pico)
    print(f"\n  -- CLARO sobre warn_bg ({t['warn_bg']}) -> pico {pico_hex} --")
    for nome_tok, minimo in (("warn_text", 4.5), ("warn_border", 3.0)):
        r = contrast_ratio(hex_to_rgb(t[nome_tok]), pico)
        flag = "OK  " if r >= minimo else "FALHA"
        if r < minimo:
            reprova = True
        print(f"    {flag} {nome_tok:14s} ({t[nome_tok]}) -> {r:.3f}:1  (min {minimo})")
    print(f"\n  VEREDITO cenario 2: {'REPROVOU (recuo)' if reprova else 'PASSOU'}")
    return not reprova


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ticker-alfa-claro", type=float, default=0.08)
    ap.add_argument("--ticker-alfa-escuro", type=float, default=0.10)
    ap.add_argument("--cvm-halo-alfa-claro", type=float, default=0.08)
    args = ap.parse_args()

    ok1 = cenario_ticker_luz(args.ticker_alfa_claro, args.ticker_alfa_escuro)
    ok2 = cenario_cvm_halo(args.cvm_halo_alfa_claro)

    print("\n" + "#" * 78)
    print(f"# RESUMO: cenario1(ticker-luz)={'PASS' if ok1 else 'RECUO'}  cenario2(cvm-halo)={'PASS' if ok2 else 'RECUO'}")
    print("#" * 78)


if __name__ == "__main__":
    main()
