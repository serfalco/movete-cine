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
BACKDROP_BASE = "https://image.tmdb.org/t/p/w780"
HERO_BASE = "https://image.tmdb.org/t/p/w1280"
STILL_BASE = "https://image.tmdb.org/t/p/w780"
PROFILE_BASE = "https://image.tmdb.org/t/p/w185"
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


def _backdrop_url(path: str | None) -> str | None:
    if not path:
        return None
    return f"{BACKDROP_BASE}{path}"


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
    backdrop = _backdrop_url(detalle.get("backdrop_path") or resultado.get("backdrop_path"))
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
        "backdrop": backdrop,
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


# --------------------------------------------------------------------------
# Ficha enriquecida (una página por película). Data extra de TMDb.
# --------------------------------------------------------------------------

def _hero_url(path: str | None) -> str | None:
    return f"{HERO_BASE}{path}" if path else None


def _still_url(path: str | None) -> str | None:
    return f"{STILL_BASE}{path}" if path else None


def _profile_url(path: str | None) -> str | None:
    return f"{PROFILE_BASE}{path}" if path else None


def _iniciales(nombre: str) -> str:
    partes = [p for p in str(nombre or "").split() if p]
    if not partes:
        return "★"
    if len(partes) == 1:
        return partes[0][:2].upper()
    return (partes[0][0] + partes[-1][0]).upper()


def _crew_por_trabajo(detalle: dict[str, Any], trabajos: set[str], limite: int = 3) -> list[str]:
    nombres: list[str] = []
    for persona in detalle.get("credits", {}).get("crew", []):
        if persona.get("job") in trabajos and persona.get("name"):
            if persona["name"] not in nombres:
                nombres.append(persona["name"])
        if len(nombres) >= limite:
            break
    return nombres


def _elenco_detallado(detalle: dict[str, Any], limite: int = 8) -> list[dict[str, Any]]:
    gente = []
    for persona in detalle.get("credits", {}).get("cast", [])[:limite]:
        nombre = persona.get("name") or ""
        if not nombre:
            continue
        gente.append(
            {
                "nombre": nombre,
                "personaje": persona.get("character") or "",
                "foto": _profile_url(persona.get("profile_path")),
                "iniciales": _iniciales(nombre),
            }
        )
    return gente


def _galeria(detalle: dict[str, Any], limite: int = 6) -> list[str]:
    imgs = detalle.get("images", {}) or {}
    urls: list[str] = []
    for backdrop in imgs.get("backdrops", []):
        path = backdrop.get("file_path")
        if not path:
            continue
        url = _still_url(path)
        if url and url not in urls:
            urls.append(url)
        if len(urls) >= limite:
            break
    return urls


def _certificacion_ar(detalle: dict[str, Any]) -> str:
    datos = detalle.get("release_dates", {}).get("results", [])
    preferidos = {"AR": None, "US": None}
    for entrada in datos:
        pais = entrada.get("iso_3166_1")
        if pais not in preferidos:
            continue
        for release in entrada.get("release_dates", []):
            cert = (release.get("certification") or "").strip()
            if cert and preferidos[pais] is None:
                preferidos[pais] = cert
    return preferidos["AR"] or preferidos["US"] or ""


def _temas(detalle: dict[str, Any], limite: int = 8) -> list[str]:
    kws = detalle.get("keywords", {}).get("keywords", [])
    nombres = []
    for kw in kws:
        nombre = (kw.get("name") or "").strip()
        if nombre:
            nombres.append(nombre[:1].upper() + nombre[1:])
        if len(nombres) >= limite:
            break
    return nombres


def _trailer_y_teaser(detalle: dict[str, Any]) -> tuple[str, str]:
    videos = detalle.get("videos", {}).get("results", [])
    yt = [v for v in videos if v.get("site") == "YouTube" and v.get("key")]

    def primero(tipo: str) -> str:
        cands = [v for v in yt if v.get("type") == tipo]
        cands.sort(key=lambda v: not bool(v.get("official")))
        return f"https://www.youtube.com/watch?v={cands[0]['key']}" if cands else ""

    return primero("Trailer"), primero("Teaser")


def _similares(detalle: dict[str, Any], limite: int = 8) -> list[dict[str, Any]]:
    salida = []
    resultados = detalle.get("similar", {}).get("results", [])
    for item in resultados:
        if not item.get("poster_path"):
            continue
        fecha = item.get("release_date") or ""
        salida.append(
            {
                "tmdb_id": item.get("id"),
                "titulo": item.get("title") or item.get("original_title") or "",
                "anio": fecha[:4] if fecha else "",
                "poster": _poster_url(item.get("poster_path")),
                "score": item.get("vote_average"),
            }
        )
        if len(salida) >= limite:
            break
    return salida


def _coleccion(collection_id: int) -> dict[str, Any] | None:
    data = _get(f"/collection/{collection_id}")
    if not data:
        return None
    partes = []
    for parte in data.get("parts", []):
        fecha = parte.get("release_date") or ""
        partes.append(
            {
                "tmdb_id": parte.get("id"),
                "titulo": parte.get("title") or parte.get("original_title") or "",
                "anio": fecha[:4] if fecha else "",
                "poster": _poster_url(parte.get("poster_path")),
                "fecha": fecha,
            }
        )
    partes.sort(key=lambda p: p.get("fecha") or "9999")
    if not partes:
        return None
    return {"nombre": data.get("name") or "", "partes": partes}


def ficha_pelicula(movie_id: int) -> dict[str, Any] | None:
    """Trae toda la data rica de una peli para armar su ficha propia.

    Una sola llamada a TMDb (con append_to_response) + una opcional por la saga.
    Pensado para cachearse por tmdb_id: se pide una vez por película.
    """

    if not API_KEY or not movie_id:
        return None

    detalle = _get(
        f"/movie/{movie_id}",
        {
            "append_to_response": "credits,videos,images,keywords,similar,release_dates,external_ids",
            "include_image_language": "es,en,null",
        },
    )
    if not detalle:
        return None

    estreno = detalle.get("release_date") or ""
    generos = [g.get("name") for g in detalle.get("genres", []) if g.get("name")]
    idiomas = [l.get("name") or l.get("english_name") for l in detalle.get("spoken_languages", []) if (l.get("name") or l.get("english_name"))]
    productoras = [c.get("name") for c in detalle.get("production_companies", []) if c.get("name")]
    trailer, teaser = _trailer_y_teaser(detalle)

    coleccion = None
    bc = detalle.get("belongs_to_collection")
    if bc and bc.get("id"):
        try:
            coleccion = _coleccion(int(bc["id"]))
        except (TypeError, ValueError):
            coleccion = None

    return {
        "tmdb_id": detalle.get("id"),
        "titulo": detalle.get("title") or detalle.get("original_title") or "",
        "titulo_original": detalle.get("original_title") or "",
        "tagline": (detalle.get("tagline") or "").strip(),
        "anio": estreno[:4] if estreno else "",
        "estreno": estreno,
        "duracion": detalle.get("runtime"),
        "generos": generos,
        "score": detalle.get("vote_average"),
        "votos": detalle.get("vote_count"),
        "certificacion": _certificacion_ar(detalle),
        "sinopsis": detalle.get("overview") or "",
        "poster": _poster_url(detalle.get("poster_path")),
        "backdrop": _backdrop_url(detalle.get("backdrop_path")),
        "hero": _hero_url(detalle.get("backdrop_path")),
        "galeria": _galeria(detalle),
        "director": _director(detalle),
        "guionistas": _crew_por_trabajo(detalle, {"Screenplay", "Writer", "Author"}),
        "musica": ", ".join(_crew_por_trabajo(detalle, {"Original Music Composer", "Music"}, limite=2)),
        "elenco": _elenco_detallado(detalle),
        "paises": _paises(detalle),
        "idiomas": idiomas,
        "productoras": productoras,
        "temas": _temas(detalle),
        "trailer": trailer,
        "teaser": teaser,
        "imdb_id": detalle.get("external_ids", {}).get("imdb_id") or "",
        "homepage": (detalle.get("homepage") or "").strip(),
        "coleccion": coleccion,
        "similares": _similares(detalle),
    }
