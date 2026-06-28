"""
scraper_agendalp_cine.py — Cine ALTERNATIVO para MoVeTe
Fuente: AgendaLP (agendalaplata.ar).

IMPORTANTE: usa EXACTAMENTE el método que ya funciona desde GitHub Actions
en el scraper de eventos (URL limpia, sin ?filtro; User-Agent corto de Linux;
pausa entre días). El filtrado de cine lo hacemos nosotros por la etiqueta de
categoría que precede a cada evento, igual que el scraper de WP.

Cada función es un evento puntual: título, hora, espacio, fecha.
"""

import re
import sys
import time
from datetime import date, datetime, timedelta
import requests
from bs4 import BeautifulSoup

# Mismo método que el scraper que ya conecta desde GitHub:
HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Chrome/120.0"}
BASE = "https://agendalaplata.ar/genda/"

PATRON_EVENTO = re.compile(r"(\d{1,2}):(\d{2})\s*hs\s*\|[ \t]*([^\n]{0,100})")
PATRON_HORA = re.compile(r"^\d{1,2}:\d{2}\s*hs")

PALABRAS_UI = {"cartelera", "cómo llegar", "como llegar", "alerta",
               "invitalo/a", "¿con quién irías?", "con quien irias",
               "sucediendo ahora", "finalizadas", "línea de tiempo",
               "▼", "‹", "›", "06h", "12h", "18h", "24h"}


def _es_cine(cat_genda, titulo):
    """True si la etiqueta de categoría dice cine."""
    return "cine" in f"{cat_genda} {titulo}".lower().split("|")[0][:40] \
        if False else "cine" in cat_genda.lower()


def _parsear_dia(html, fecha_dia):
    funciones = []
    soup = BeautifulSoup(html, "html.parser")
    texto = soup.get_text("\n")
    texto = re.sub(r"(\d{1,2}:\d{2}\s*hs)\s*\|\s*", r"\1 | ", texto)

    for m in PATRON_EVENTO.finditer(texto):
        hora = f"{int(m.group(1)):02d}:{m.group(2)}"
        venue = m.group(3).strip()
        if PATRON_HORA.match(venue):
            venue = ""

        contexto_previo = texto[max(0, m.start() - 400):m.start()]
        previas = [l.strip() for l in contexto_previo.split("\n")
                   if l.strip()
                   and not PATRON_HORA.match(l.strip())
                   and l.strip().lower() not in PALABRAS_UI]
        if not previas:
            continue

        titulo = previas[-1]
        cat_genda = previas[-2] if len(previas) >= 2 else ""

        if len(titulo) < 3 or len(titulo) > 120:
            continue
        if titulo.lower() == venue.lower():
            continue
        if "????" in titulo:
            continue

        # Solo cine
        if "cine" not in cat_genda.lower():
            continue

        funciones.append({
            "titulo": titulo,
            "hora": hora,
            "espacio": venue or "La Plata",
            "fecha": fecha_dia.isoformat(),
        })
    return funciones


def scrapear_cine_alternativo(desde=None, dias=7):
    """Scrapea 'dias' días desde 'desde' (datetime/date). Default: hoy + 7."""
    if desde is None:
        desde = date.today()
    elif isinstance(desde, datetime):
        desde = desde.date()

    funciones = []
    vistos = set()
    fallos_consecutivos = 0
    for offset in range(dias):
        dia = desde + timedelta(days=offset)
        try:
            r = requests.get(BASE, params={"fecha": dia.isoformat()},
                             headers=HEADERS, timeout=25)
            if r.status_code != 200:
                print(f"  genda-cine/{dia}: HTTP {r.status_code}", file=sys.stderr)
                continue
            fallos_consecutivos = 0
            for f in _parsear_dia(r.text, dia):
                clave = (f["titulo"].lower(), f["fecha"], f["hora"],
                         f["espacio"].lower())
                if clave not in vistos:
                    vistos.add(clave)
                    funciones.append(f)
        except requests.RequestException as e:
            print(f"  genda-cine/{dia}: error {e}", file=sys.stderr)
            fallos_consecutivos += 1
            if fallos_consecutivos >= 2:
                print("  genda-cine: fuente inaccesible; se corta el intento diario", file=sys.stderr)
                break
        time.sleep(0.5)

    print(f"  genda-cine: {len(funciones)} funciones en {dias} días",
          file=sys.stderr)
    return funciones


if __name__ == "__main__":
    import json
    data = scrapear_cine_alternativo()
    print(json.dumps(data, ensure_ascii=False, indent=2))
