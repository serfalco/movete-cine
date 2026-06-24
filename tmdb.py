"""Cliente mínimo de TMDb para MoVeTe Cine."""

from __future__ import annotations

import os
import re
import sys
import time
import unicodedata
from typing import Any

import requests


API_KEY = os.environ.get("TMDB_API_KEY", "").strip()
BASE = "https://api.themoviedb.org/3"
IMG_BASE = "https://image.tmdb.org/t/p/w342"
LANG = "es-AR"
TIMEOUT = 20


def disponible() -> bool:
    return bool(API_KEY)


def limpiar_titulo(titulo: str) -> str:
    titulo = str(titulo or "").strip().lower()
    titulo = unicodedata.normalize("NFKD", titulo)
    titulo = "".join(c for c in titulo if not unicodedata.combining(c))
    titulo = re.sub(r"\([^)]*\)", " ", titulo)
    titulo = re.sub(r"\[[^]]*\]", " ", titulo)
    titulo = re.sub(r"\b(2d|3d|4d|imax|xd|subtitulada|subt|castellano|esp|latino)\b", " ", titulo)
    titulo = re.sub(r"[^a-z0-9ñ]+", " ", titulo)
    titulo = re.sub(r"\s+", " ", titulo).strip()
    return titulo


def _get(path: str, params: dict[str, Any] | None = None) -> dict[str, Any] | None:
    if not API_KEY:
        return None

    params = dict(params or {})
    params["api_key"] = API_KEY
    params.setdefault("language", LANG)

    try:
        r = requests.get(f"{BASE}{path}", params=params, timeout=TIMEOUT)
        if r.status_code == 401:
            print("[tmdb] API key inválida o no autorizada.", file=sys.stderr)
            return None
        if r.status_code == 429:
            time.sleep(1.5)
            r = requests.get(f"{BASE}{path}", params=params, timeout=TIMEOUT)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"[tmdb] Error GET {path}: {e}", file=sys.stderr)
        return None


def _poster_url(path: str | None) -> str | None:
    if not path:
        return None
    return f"{IMG_BASE}{path}"


def _detalle(movie_id: int) -> dict[str, Any] | None:
    return _get(
        f"/movie/{movie_id}",
        {
            "append_to_response": "credits,videos",
        },
    )


def _elegir_resultado(resultados: list[dict[str, Any]], clave: str) -> dict[str, Any] | None:
    if not resultados:
        return None

    for item in resultados:
        titulo = limpiar_titulo(item.get("title") or item.get("name") or "")
        original = limpiar_titulo(item.get("original_title") or "")
        if titulo == clave or original == clave:
            return item

    return resultados[0]


def _director(detalle: dict[str, Any]) -> str:
    for persona in detalle.get("credits", {}).get("crew", []):
        if persona.get("job") == "Director" and persona.get("name"):
            return persona["name"]
    return ""


def _elenco(detalle: dict[str, Any], limite: int = 3) -> list[str]:
    nombres = []
    for persona in detalle.get("credits", {}).get("cast", []):
        nombre = persona.get("name")
        if nombre:
            nombres.append(nombre)
        if len(nombres) >= limite:
            break
    return nombres


def _trailer(detalle: dict[str, Any]) -> str:
    videos = detalle.get("videos", {}).get("results", [])

    candidatos = []
    for video in videos:
        if video.get("site") != "YouTube":
            continue
        if video.get("type") not in {"Trailer", "Teaser"}:
            continue
        if not video.get("key"):
            continue
        candidatos.append(video)

    if not candidatos:
        return ""

    candidatos.sort(key=lambda v: (not bool(v.get("official")), v.get("type") != "Trailer"))
    return f"https://www.youtube.com/watch?v={candidatos[0]['key']}"


def _paises(detalle: dict[str, Any]) -> list[str]:
    paises = []
    for pais in detalle.get("production_countries", []):
        nombre = pais.get("name")
        if nombre:
            paises.append(nombre)
    return paises


def buscar_pelicula(titulo: str, alias: dict[str, str] | None = None) -> dict[str, Any] | None:
    if not API_KEY:
        return None

    alias = alias or {}
    clave = limpiar_titulo(titulo)
    query = alias.get(clave) or alias.get(titulo) or titulo

    data = _get(
        "/search/movie",
        {
            "query": query,
            "include_adult": "false",
            "region": "AR",
        },
    )

    if not data:
        return None

    resultado = _elegir_resultado(data.get("results", []), clave)
    if not resultado or not resultado.get("id"):
        return None

    detalle = _detalle(int(resultado["id"])) or {}

    poster = _poster_url(detalle.get("poster_path") or resultado.get("poster_path"))
    estreno = detalle.get("release_date") or resultado.get("release_date") or ""
    anio = estreno[:4] if estreno else ""

    generos = []
    for g in detalle.get("genres", []):
        nombre = g.get("name")
        if nombre:
            generos.append(nombre)

    return {
        "tmdb_id": resultado.get("id"),
        "titulo": detalle.get("title") or resultado.get("title") or titulo,
        "titulo_original": detalle.get("original_title") or resultado.get("original_title") or "",
        "poster": poster,
        "sinopsis": detalle.get("overview") or resultado.get("overview") or "",
        "anio": anio,
        "duracion": detalle.get("runtime"),
        "generos": generos,
        "score": resultado.get("vote_average"),
        "director": _director(detalle),
        "elenco": _elenco(detalle),
        "trailer": _trailer(detalle),
        "paises": _paises(detalle),
    }
