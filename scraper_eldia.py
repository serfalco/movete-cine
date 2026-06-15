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
    """Parsea la cartelera. Acepta tanto texto con saltos de línea (cuerpo)
    como texto corrido de una sola tirada (meta description de El Día).

    Estrategia: trabajar sobre texto corrido. Primero ubicar cada complejo
    (NOMBRE + '(...dirección/teléfono...)'), luego dentro de cada complejo
    extraer las películas con el patrón 'Título (idioma)(formato).- horarios'.
    """
    # Normalizar entidades y espacios
    t = texto_plano.replace("&amp;", "&").replace("&ordm;", "º").replace("&deg;", "º")
    t = re.sub(r"\s+", " ", t).strip()

    # 1) Encontrar los complejos. Un complejo arranca con un nombre y abre
    #    paréntesis con dirección que contiene 'Te.' o 'Nº' (teléfono/altura).
    #    Capturamos el nombre (letras antes del paréntesis) y la dirección.
    re_complejo = re.compile(
        r"([A-Za-zÁÉÍÓÚÑáéíóúñ][A-Za-zÁÉÍÓÚÑáéíóúñ .'\-]*?)"
        r"\(([^)]*(?:Te\.|N[º°]|Tel)[^)]*)\)"
    )

    matches = list(re_complejo.finditer(t))
    if not matches:
        return []

    cines = []
    for idx, m in enumerate(matches):
        nombre = m.group(1).strip(" .-").title()
        direccion = re.sub(r"\s+", " ", m.group(2)).strip()
        # El bloque de películas va desde el fin de este match hasta el
        # comienzo del próximo complejo (o el final del texto).
        ini = m.end()
        fin = matches[idx + 1].start() if idx + 1 < len(matches) else len(t)
        bloque = t[ini:fin]

        peliculas = _parsear_peliculas_bloque(bloque)
        if peliculas:
            cines.append({
                "cine": nombre,
                "direccion": direccion,
                "peliculas": peliculas,
            })

    return cines


# Una película: "Título (idioma)(formato opcional).- horarios"
# Los horarios son números/HH:MM separados por coma, hasta el próximo título.


def _parsear_peliculas_bloque(bloque):
    """Extrae películas de un bloque de texto corrido.

    Formato: 'Título (idioma)(formato).- h, h, h Título2 (idioma).- h ...'
    Estrategia robusta: separar por el marcador '.-'. Cada '.-' está precedido
    por (Título + paréntesis) y seguido por los horarios. El texto entre el fin
    de unos horarios y el próximo '.-' es el título siguiente.
    """
    pelis = []
    # Posiciones de cada '.-'
    marcadores = [mm.start() for mm in re.finditer(r"\.-", bloque)]
    if not marcadores:
        return pelis

    cursor = 0  # inicio del título actual
    for k, pos in enumerate(marcadores):
        cabeza = bloque[cursor:pos]  # "Título (idioma)(formato)"
        # horarios: desde pos+2 hasta donde empiece el próximo título.
        resto = bloque[pos + 2:]
        m_h = re.match(r"\s*(\d{1,2}(?::\d{2})?(?:\s*,\s*\d{1,2}(?::\d{2})?)*)", resto)
        if not m_h:
            cursor = pos + 2
            continue
        horarios_str = m_h.group(1)
        fin_horarios = pos + 2 + m_h.end()

        # idioma/formato de la cabeza
        parens = RE_PAREN.findall(cabeza)
        titulo = RE_PAREN.sub("", cabeza).strip(" .-·\u00a0")
        idioma = ""
        formato = ""
        for p in parens:
            pl = p.strip().lower()
            if pl in IDIOMAS:
                idioma = p.strip()
            else:
                formato = p.strip()

        horarios = []
        for tok in horarios_str.split(","):
            hh = _normalizar_hora(tok)
            if hh:
                horarios.append(hh)

        if titulo and horarios:
            pelis.append({
                "titulo": titulo,
                "idioma": idioma,
                "formato": formato,
                "horarios": horarios,
            })

        cursor = fin_horarios  # el próximo título empieza acá

    return pelis


def _extraer_texto_guia(html):
    """Extrae el texto corrido de la cartelera.

    La cartelera de El Día es PÚBLICA y está COMPLETA en el cuerpo del
    artículo (no hay muro de pago). El <meta description> solo trae un
    resumen recortado (~1 cine), así que ya NO es la fuente principal.

    Estrategia (de más completo a menos):
      1. Cuerpo del artículo: <article> o el <div> de la nota.
         Es donde está la cartelera entera (todos los cines).
      2. Fallback: meta description (og/twitter). Red de seguridad por si
         algún día cambia la estructura del cuerpo; trae poco pero algo.

    Devuelve texto corrido (el parser lo entiende de una sola tirada).
    """
    soup = BeautifulSoup(html, "html.parser")

    # 1) Cuerpo del artículo (fuente principal: cartelera completa)
    cont = soup.find("article") or soup.find(
        "div", class_=re.compile("nota|article|cuerpo|content", re.I)
    )
    if cont:
        for br in cont.find_all("br"):
            br.replace_with(" ")
        cuerpo = cont.get_text(" ", strip=True)
        # Solo lo damos por válido si realmente trae cartelera (marcador ".-")
        if ".-" in cuerpo:
            return cuerpo

    # 2) Fallback: meta description (resumen recortado, pero mejor que nada)
    candidatos = []
    for attrs in [{"name": "description"},
                  {"property": "og:description"},
                  {"name": "twitter:description"}]:
        tag = soup.find("meta", attrs=attrs)
        if tag and tag.get("content"):
            candidatos.append(tag["content"])

    fuente = ""
    for c in candidatos:
        if ".-" in c and len(c) > len(fuente):
            fuente = c

    return fuente


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
