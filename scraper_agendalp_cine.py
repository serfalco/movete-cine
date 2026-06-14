"""
scraper_agendalp_cine.py — Cine ALTERNATIVO para MoVeTe
Fuente: AgendaLP (agendalaplata.ar), filtrando las tarjetas con etiqueta "Cine".

Importante (descubierto en diagnóstico):
  - El parámetro ?filtro=cine NO filtra del lado servidor (lo hace JS en el
    navegador). El servidor devuelve TODAS las categorías igual. Por eso
    filtramos nosotros por la etiqueta de cada tarjeta.
  - La página carga por fecha: un fetch por día.
  - Cada función es un EVENTO PUNTUAL (a diferencia del cine tradicional que es
    cartelera). Salida: lista de funciones con título, hora, espacio, fecha.

Salida:
  [
    {"titulo": "El escuerzo (2023) Dir. Augusto Sinay",
     "hora": "18:00", "espacio": "Cine Club Proyecciones Terrestres",
     "fecha": "2026-06-14"},
    ...
  ]
"""

import re
import sys
from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup

BASE = "https://agendalaplata.ar/genda/"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}

# Etiquetas que consideramos "cine" en AgendaLP
ETIQUETA_CINE = "cine"

# Ruido a descartar dentro de las tarjetas
RUIDO = {"cartelera", "cómo llegar", "como llegar", "alerta",
         "¿con quién irías?", "con quien irias", "invitalo/a", "invitalo"}

RE_HORA = re.compile(r"(\d{1,2}):(\d{2})\s*hs")


def _limpiar(t):
    return re.sub(r"\s+", " ", t or "").strip()


def _scrapear_dia(fecha_str):
    """Devuelve las funciones de cine de un día (YYYY-MM-DD)."""
    url = f"{BASE}?fecha={fecha_str}&filtro=cine"
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        r.raise_for_status()
    except Exception as e:
        print(f"[agendalp-cine] {fecha_str}: error {e}", file=sys.stderr)
        return []

    soup = BeautifulSoup(r.text, "html.parser")

    # La página es una línea de tiempo de tarjetas. Recorremos el texto en
    # bloques: cada tarjeta empieza con su etiqueta de categoría (Cine, Teatro,
    # Música, Museo...) seguida del título, la hora y el espacio.
    # Trabajamos sobre el texto plano por robustez (la estructura DOM varía).
    texto = soup.get_text("\n", strip=True)
    lineas = [_limpiar(l) for l in texto.split("\n") if _limpiar(l)]

    funciones = []
    categorias_validas = {"cine", "teatro", "música", "musica", "infantil",
                          "museo", "feria", "exposición", "exposicion",
                          "visita", "recreativo", "actividad"}

    i = 0
    n = len(lineas)
    while i < n:
        etiqueta = lineas[i].lower()
        # ¿esta línea es una etiqueta de categoría sola?
        es_etiqueta = etiqueta in categorias_validas or \
            all(p in categorias_validas for p in etiqueta.split())

        if es_etiqueta and etiqueta.split()[0] == ETIQUETA_CINE:
            # Las siguientes líneas son: título / "HH:MM hs | Espacio" / ...
            titulo = lineas[i + 1] if i + 1 < n else ""
            hora = ""
            espacio = ""
            # Buscamos en las próximas líneas la que tenga "HH:MM hs | Espacio"
            for j in range(i + 1, min(i + 6, n)):
                m = RE_HORA.search(lineas[j])
                if m and "|" in lineas[j]:
                    hora = f"{m.group(1).zfill(2)}:{m.group(2)}"
                    espacio = lineas[j].split("|", 1)[1].strip()
                    break
            # Una tarjeta REAL siempre tiene hora + espacio. Si no los tiene,
            # es el menú de categorías del encabezado (Cine/Teatro/Música...),
            # no una función: lo descartamos.
            es_tarjeta_real = bool(hora and espacio)
            if es_tarjeta_real and titulo and titulo.lower() not in RUIDO:
                funciones.append({
                    "titulo": titulo,
                    "hora": hora,
                    "espacio": espacio,
                    "fecha": fecha_str,
                })
                i += 2
                continue
        i += 1

    return funciones


def scrapear_cine_alternativo(desde=None, dias=7):
    """Scrapea 'dias' días a partir de 'desde' (datetime). Default: hoy + 7."""
    if desde is None:
        desde = datetime.now()

    todas = []
    vistos = set()
    for d in range(dias):
        fecha = (desde + timedelta(days=d)).strftime("%Y-%m-%d")
        for f in _scrapear_dia(fecha):
            clave = (f["titulo"].lower(), f["fecha"], f["hora"], f["espacio"].lower())
            if clave not in vistos:
                vistos.add(clave)
                todas.append(f)

    print(f"[agendalp-cine] Funciones de cine alternativo: {len(todas)}",
          file=sys.stderr)
    return todas


if __name__ == "__main__":
    import json
    data = scrapear_cine_alternativo()
    print(json.dumps(data, ensure_ascii=False, indent=2))
