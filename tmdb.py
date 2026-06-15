"""
tmdb.py — Enriquecimiento de películas con datos de The Movie Database (TMDb).

Por cada título de la cartelera intenta encontrar la película en TMDb y
devolver un paquete con: póster, sinopsis (es-AR), año, duración y géneros.

REGLA DE ORO (punto 2 del diseño): esto NUNCA debe romper la generación de
la página. Si no hay API key, si TMDb falla o si no hay match, la función
devuelve None y el HTML cae al placeholder. La guía sale igual.

Estrategia de matching (4 capas):
  1. Limpiar el título antes de buscar (sacar ruido de idioma/formato,
     normalizar mayúsculas y acentos).
  2. Buscar bien en TMDb: language=es-AR, region=AR, y elegir el candidato
     por SIMILITUD de título, no por orden de resultados.
  3. Diccionario de alias (alias.json): títulos que El Día traduce y que en
     TMDb están con otro nombre (normalmente inglés).
  4. El que no matchea queda registrado para el reporte de no-encontrados.

El caché (peliculas.json) lo maneja main.py; acá solo se busca.
"""

import os
import re
import sys
import json
import time
import unicodedata
from difflib import SequenceMatcher

import requests

API_KEY = os.environ.get("TMDB_API_KEY", "").strip()
BASE = "https://api.themoviedb.org/3"
IMG_BASE = "https://image.tmdb.org/t/p"
POSTER_SIZE = "w500"      # buen balance calidad/peso para la guía
TIMEOUT = 12

HEADERS = {"User-Agent": "MoVeTe/1.0 (agenda cultural La Plata)"}

# Umbral de similitud para aceptar un match (0..1). Por debajo, se descarta.
UMBRAL_SIMILITUD = 0.60


# ---------------------------------------------------------------------------
# Capa 1: limpieza de título
# ---------------------------------------------------------------------------

# Ruido que a veces queda pegado al título de El Día
_RE_PARENTESIS = re.compile(r"\([^)]*\)")
_RE_ESPACIOS = re.compile(r"\s+")


def limpiar_titulo(titulo):
    """Saca paréntesis (idioma/formato), normaliza espacios y mayúsculas raras."""
    t = _RE_PARENTESIS.sub("", titulo)        # quita "(cast.)", "(4D)", etc.
    t = t.replace(".-", " ")
    t = _RE_ESPACIOS.sub(" ", t).strip(" .-·\u00a0")
    return t


def _normalizar(s):
    """minúsculas, sin acentos, sin puntuación: para COMPARAR, no para mostrar."""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower()
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    s = _RE_ESPACIOS.sub(" ", s).strip()
    return s


def _similitud(a, b):
    return SequenceMatcher(None, _normalizar(a), _normalizar(b)).ratio()


def _titulo_sin_subtitulo(titulo):
    """'Scary Movie: Terror...' -> 'Scary Movie' (reintento si falla la búsqueda)."""
    if ":" in titulo:
        cabeza = titulo.split(":", 1)[0].strip()
        if len(cabeza) >= 3:
            return cabeza
    return None


# ---------------------------------------------------------------------------
# Capa 2 + 3: búsqueda en TMDb (con alias)
# ---------------------------------------------------------------------------

def _buscar_en_tmdb(query, year=None):
    """Una llamada a /search/movie. Devuelve lista de resultados (o [])."""
    if not API_KEY:
        return []
    params = {
        "api_key": API_KEY,
        "query": query,
        "language": "es-AR",
        "region": "AR",
        "include_adult": "false",
    }
    if year:
        params["year"] = year
    try:
        r = requests.get(f"{BASE}/search/movie", params=params,
                         headers=HEADERS, timeout=TIMEOUT)
        if r.status_code != 200:
            print(f"[tmdb] search '{query}': HTTP {r.status_code}", file=sys.stderr)
            return []
        return r.json().get("results", []) or []
    except requests.RequestException as e:
        print(f"[tmdb] search '{query}': {e}", file=sys.stderr)
        return []


def _elegir_candidato(query, resultados):
    """Capa 2: elige el resultado más parecido por título, no el primero."""
    mejor, mejor_score = None, 0.0
    for res in resultados:
        # comparamos contra el título mostrado y el original
        cands = [res.get("title", ""), res.get("original_title", "")]
        score = max((_similitud(query, c) for c in cands if c), default=0.0)
        if score > mejor_score:
            mejor, mejor_score = res, score
    if mejor and mejor_score >= UMBRAL_SIMILITUD:
        return mejor
    return None


def _detalle_pelicula(movie_id):
    """Segunda llamada para traer duración y géneros (no vienen en search)."""
    if not API_KEY:
        return {}
    try:
        r = requests.get(f"{BASE}/movie/{movie_id}",
                         params={"api_key": API_KEY, "language": "es-AR"},
                         headers=HEADERS, timeout=TIMEOUT)
        if r.status_code != 200:
            return {}
        return r.json()
    except requests.RequestException:
        return {}


def buscar_pelicula(titulo, alias=None):
    """
    Devuelve un dict con los datos enriquecidos o None si no hay match.
    'alias' es el diccionario {titulo_original: titulo_a_buscar} (capa 3).

    NUNCA lanza excepción: ante cualquier problema, devuelve None.
    """
    try:
        limpio = limpiar_titulo(titulo)

        # Capa 3: si hay alias para este título, buscamos por el alias.
        consulta = limpio
        if alias:
            # match por título limpio o por el original tal cual vino
            consulta = alias.get(limpio) or alias.get(titulo) or limpio

        # Capa 2: búsqueda principal
        resultados = _buscar_en_tmdb(consulta)
        candidato = _elegir_candidato(consulta, resultados)

        # Reintento: sin subtítulo después de ":"
        if not candidato:
            corto = _titulo_sin_subtitulo(consulta)
            if corto:
                resultados = _buscar_en_tmdb(corto)
                candidato = _elegir_candidato(corto, resultados)

        if not candidato:
            return None

        # Datos base (de search)
        poster_path = candidato.get("poster_path")
        overview = (candidato.get("overview") or "").strip()
        release = candidato.get("release_date") or ""
        anio = release[:4] if len(release) >= 4 else ""

        # Detalle (duración + géneros)
        det = _detalle_pelicula(candidato["id"])
        runtime = det.get("runtime") or 0
        generos = [g["name"] for g in det.get("genres", [])][:2]

        # Si la sinopsis es-AR vino vacía, la dejamos vacía (no caemos a inglés)
        return {
            "poster": f"{IMG_BASE}/{POSTER_SIZE}{poster_path}" if poster_path else "",
            "sinopsis": overview,
            "anio": anio,
            "duracion": int(runtime) if runtime else 0,
            "generos": generos,
            "tmdb_id": candidato["id"],
            "match": candidato.get("title", ""),  # para auditar el reporte
        }
    except Exception as e:
        # Blindaje total: nada de esto puede romper la generación.
        print(f"[tmdb] error inesperado con '{titulo}': {e}", file=sys.stderr)
        return None


def disponible():
    """True si hay API key cargada. Para que main.py informe en el log."""
    return bool(API_KEY)
