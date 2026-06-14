"""
scraper_eldia.py — Cine TRADICIONAL (comercial) para MoVeTe
Fuente: guía de cines de El Día (La Plata).

Estrategia de URL (en cascada, fiel al principio "si se rompe, lo arreglamos"):
  1. Buscar en la sección espectáculos el link cuyo slug contenga
     'guia-de-cines-espectaculos_' y agarrar el más reciente.
  2. Si falla, devolver lista vacía (la web sale igual, sin esta sección).

Salida: lista de complejos, cada uno con sus películas y horarios.
  [
    {
      "cine": "CINEMA SAN MARTÍN",
      "direccion": "7 Nº 923 - Te. 483-9947",
      "peliculas": [
        {"titulo": "Mortal Kombat 2", "idioma": "cast.", "formato": "",
         "horarios": ["14:00", "20:50"]},
        ...
      ]
    },
    ...
  ]
"""

import re
import sys
import requests
from bs4 import BeautifulSoup

SECCION_URL = "https://www.eldia.com/seccion/espectaculos"
BASE = "https://www.eldia.com"
SLUG = "guia-de-cines-espectaculos_"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}


def encontrar_url_guia():
    """Pata 1: busca el link de la guía vigente en la sección espectáculos."""
    try:
        r = requests.get(SECCION_URL, headers=HEADERS, timeout=20)
        r.raise_for_status()
    except Exception as e:
        print(f"[eldia] No pude abrir la sección espectáculos: {e}", file=sys.stderr)
        return None

    soup = BeautifulSoup(r.text, "html.parser")
    for a in soup.find_all("a", href=True):
        if SLUG in a["href"]:
            href = a["href"]
            if href.startswith("/"):
                href = BASE + href
            return href
    print("[eldia] No encontré link a la guía de cines en la sección.", file=sys.stderr)
    return None


# Línea de cine: TODO EN MAYÚSCULAS, con dirección entre paréntesis.
# Ej: "CINEMA SAN MARTÍN (7 Nº 923 - Te. 483-9947)"
RE_CINE = re.compile(r"^([A-ZÁÉÍÓÚÑ0-9][A-ZÁÉÍÓÚÑ0-9 .'\-]{3,})\s*\((.+?)\)\s*$")

# Línea de película: "Título (idioma) (formato opcional).- 14, 20:50"
# El ".-" separa título de horarios.
RE_PELI = re.compile(r"^(.*?)\.-\s*(.+)$")
RE_PAREN = re.compile(r"\(([^)]+)\)")

# Idiomas conocidos para distinguirlos del formato
IDIOMAS = {"cast.", "cast", "subt.", "subt", "castellano", "subtitulada"}


def _normalizar_hora(h):
    """'14' -> '14:00', '20:50' -> '20:50'."""
    h = h.strip()
    if not h:
        return None
    if ":" in h:
        partes = h.split(":")
        hh = partes[0].zfill(2)
        mm = partes[1].zfill(2)[:2]
        return f"{hh}:{mm}"
    if h.isdigit():
        return f"{h.zfill(2)}:00"
    return None


def _parsear_pelicula(linea):
    m = RE_PELI.match(linea)
    if not m:
        return None
    cabeza = m.group(1).strip()   # "Título (cast.) (3D)"
    cola = m.group(2).strip()     # "14, 20:50"

    # Extraer todo lo que esté entre paréntesis (idioma y/o formato)
    parentesis = RE_PAREN.findall(cabeza)
    titulo = RE_PAREN.sub("", cabeza).strip(" .-")

    idioma = ""
    formato = ""
    for p in parentesis:
        pl = p.strip().lower()
        if pl in IDIOMAS:
            idioma = p.strip()
        else:
            formato = p.strip()  # 3D, 4D, ATMOS, etc.

    # Horarios separados por coma
    horarios = []
    for tok in cola.split(","):
        hh = _normalizar_hora(tok)
        if hh:
            horarios.append(hh)

    if not titulo or not horarios:
        return None

    return {
        "titulo": titulo,
        "idioma": idioma,
        "formato": formato,
        "horarios": horarios,
    }


def parsear_cartelera(texto_plano):
    """Recibe el texto de la guía (líneas) y arma la estructura de complejos."""
    cines = []
    actual = None

    for raw in texto_plano.split("\n"):
        linea = re.sub(r"\s+", " ", raw).strip()
        if not linea:
            continue

        m_cine = RE_CINE.match(linea)
        if m_cine:
            # nuevo complejo
            if actual and actual["peliculas"]:
                cines.append(actual)
            actual = {
                "cine": m_cine.group(1).strip().title(),
                "direccion": m_cine.group(2).strip(),
                "peliculas": [],
            }
            continue

        if actual is not None:
            peli = _parsear_pelicula(linea)
            if peli:
                actual["peliculas"].append(peli)

    if actual and actual["peliculas"]:
        cines.append(actual)

    return cines


def _extraer_texto_guia(html):
    """Saca el cuerpo de la nota como texto plano por líneas."""
    soup = BeautifulSoup(html, "html.parser")
    # El cuerpo de la nota suele estar en <article> o en el contenedor principal.
    cont = soup.find("article") or soup.find("main") or soup.body
    if not cont:
        return ""
    # Insertamos saltos: cada <br> y cada <p> es una línea lógica
    for br in cont.find_all("br"):
        br.replace_with("\n")
    lineas = []
    for el in cont.find_all(["p", "div", "span", "li"]):
        t = el.get_text(" ", strip=True)
        if t:
            lineas.append(t)
    if not lineas:
        lineas = [cont.get_text("\n", strip=True)]
    return "\n".join(lineas)


def scrapear_cine_tradicional(url=None):
    if url is None:
        url = encontrar_url_guia()
    if not url:
        return []

    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        r.raise_for_status()
    except Exception as e:
        print(f"[eldia] No pude abrir la guía: {e}", file=sys.stderr)
        return []

    texto = _extraer_texto_guia(r.text)
    cines = parsear_cartelera(texto)
    print(f"[eldia] Complejos: {len(cines)} | "
          f"Películas: {sum(len(c['peliculas']) for c in cines)}",
          file=sys.stderr)
    return cines


if __name__ == "__main__":
    import json
    data = scrapear_cine_tradicional()
    print(json.dumps(data, ensure_ascii=False, indent=2))
