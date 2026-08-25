"""Orquestador del sistema de cine de MoVeTe.

Genera la cartelera semanal jueves→miércoles y escribe:

- /index.html portada vigente de Cine
- /YYYY-MM-DD/index.html edición archivada

Ejemplo local:

python main.py --output ../Movete-info/cine
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import tmdb
import generar_ficha
from generar_html import generar
from scraper_agendalp_cine import scrapear_cine_alternativo
from scraper_eldia import scrapear_cine_tradicional


ALIAS_PATH = "alias.json"
SITIO = "https://movete.info"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Genera cartelera de cine para MoVeTe")
    parser.add_argument(
        "--output",
        default=os.environ.get("MOVETE_CINE_OUT", "../Movete-info/cine"),
        help="Carpeta de salida. Default: ../Movete-info/cine",
    )
    return parser.parse_args()


def _cargar_json(path: str | Path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def _guardar_json(path: str | Path, data) -> None:
    destino = Path(path)
    try:
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError as e:
        print(f"[main] No pude guardar respaldo {destino}: {e}", file=sys.stderr)


def _alternativo_en_rango(funciones: list[dict], jueves: datetime) -> list[dict]:
    fin = (jueves + timedelta(days=6)).date()
    inicio = jueves.date()
    resultado = []
    for funcion in funciones:
        try:
            fecha = datetime.strptime(funcion.get("fecha", ""), "%Y-%m-%d").date()
        except (TypeError, ValueError):
            continue
        if inicio <= fecha <= fin:
            resultado.append(funcion)
    return resultado


def enriquecer_con_tmdb(tradicional: list[dict], cache_path: Path):
    """Adjunta a cada película un campo 'tmdb' con datos de TMDb o None."""

    if not tmdb.disponible():
        print("[main] Sin TMDB_API_KEY: se usa placeholder en todos los pósters.", file=sys.stderr)
        return tradicional, []

    cache = _cargar_json(cache_path, {})
    alias = _cargar_json(ALIAS_PATH, {})
    no_encontrados = []
    nuevos = 0
    encontrados = 0

    for cine in tradicional:
        for peli in cine.get("peliculas", []):
            titulo = peli.get("titulo", "")
            clave = tmdb.limpiar_titulo(titulo)

            cache_actualizado = clave in cache and (
                cache[clave] is None or "backdrop" in cache[clave]
            )

            if cache_actualizado:
                peli["tmdb"] = cache[clave]
                if cache[clave]:
                    encontrados += 1
                continue

            info = tmdb.buscar_pelicula(titulo, alias=alias)
            cache[clave] = info
            peli["tmdb"] = info
            nuevos += 1

            if info is None:
                no_encontrados.append(clave)
            else:
                encontrados += 1

    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(
            json.dumps(cache, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
    except OSError as e:
        print(f"[main] No pude guardar caché de pósters: {e}", file=sys.stderr)

    print(
        f"[main] TMDb: {nuevos} títulos nuevos buscados, {encontrados} con datos, {len(no_encontrados)} sin match.",
        file=sys.stderr,
    )

    return tradicional, no_encontrados


def _escribir_si_cambia(destino: Path, contenido: str) -> bool:
    """Escribe sólo si el contenido cambió (mantiene los commits chicos)."""
    try:
        if destino.exists() and destino.read_text(encoding="utf-8") == contenido:
            return False
    except OSError:
        pass
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(contenido, encoding="utf-8")
    return True


def _meta_de_ficha(rich: dict, slug: str, en_cartelera: bool) -> dict:
    return {
        "slug": slug,
        "titulo": rich.get("titulo", ""),
        "anio": rich.get("anio", ""),
        "poster": rich.get("poster"),
        "generos": rich.get("generos", []),
        "en_cartelera": en_cartelera,
    }


def _escribir_sitemap_pelis(out: Path, metas: list[dict], jueves: datetime) -> None:
    lastmod = jueves.strftime("%Y-%m-%d")
    locs = [f"{SITIO}/cine/pelis/"] + [f"{SITIO}/cine/pelis/{m['slug']}/" for m in metas]
    filas = "\n".join(
        f"  <url><loc>{loc}</loc><lastmod>{lastmod}</lastmod></url>" for loc in locs
    )
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{filas}\n"
        "</urlset>\n"
    )
    _escribir_si_cambia(out / "sitemap-pelis.xml", xml)


def generar_fichas(tradicional: list[dict], out: Path, jueves: datetime, cache_path: Path) -> None:
    """Genera una ficha por película (más la home /cine/pelis/ y su sitemap).

    Usa un caché por tmdb_id: la data rica de TMDb se pide una sola vez por peli.
    Reescribe únicamente las fichas que cambiaron. Todo defensivo: si algo falla,
    la cartelera semanal ya quedó publicada igual.
    """

    if not tmdb.disponible():
        print("[fichas] Sin TMDB_API_KEY: no se generan fichas.", file=sys.stderr)
        return

    cache = _cargar_json(cache_path, {})
    if not isinstance(cache, dict):
        cache = {}
    semana = jueves.strftime("%Y-%m-%d")

    # 1) Películas de esta semana: data rica (de caché o recién pedida).
    vistos: dict[str, dict] = {}
    for cine in tradicional:
        for peli in cine.get("peliculas", []):
            info = peli.get("tmdb") or {}
            tid = info.get("tmdb_id")
            if not tid:
                continue
            clave = str(tid)
            if clave in vistos:
                continue
            rich = (cache.get(clave) or {}).get("tmdb")
            if not rich:
                rich = tmdb.ficha_pelicula(int(tid))
            if not rich:
                continue
            vistos[clave] = rich
            cache[clave] = {"tmdb": rich, "ultima_semana": semana}

    # 2) Renderizar cada ficha conocida (esta semana + archivo).
    pelis_dir = out / "pelis"
    metas: list[dict] = []
    escritas = 0
    for clave, item in cache.items():
        rich = (item or {}).get("tmdb")
        if not rich:
            continue
        en_cartelera = clave in vistos
        try:
            tid_int = int(clave)
        except (TypeError, ValueError):
            tid_int = None
        presencia = (
            generar_ficha.construir_presencia(tradicional, tid_int, rich.get("titulo", ""))
            if en_cartelera
            else []
        )
        slug = generar_ficha.slug_pelicula(rich.get("titulo", ""), rich.get("anio", ""))
        html = generar_ficha.render_ficha(rich, presencia, jueves, jueves.year)
        if _escribir_si_cambia(pelis_dir / slug / "index.html", html):
            escritas += 1
        metas.append(_meta_de_ficha(rich, slug, en_cartelera))

    # 3) Home de la sección + sitemap.
    metas.sort(key=lambda m: (not m["en_cartelera"], -_anio_int(m["anio"]), m["titulo"].lower()))
    indice = generar_ficha.render_indice(metas, jueves, jueves.year)
    _escribir_si_cambia(pelis_dir / "index.html", indice)
    _escribir_sitemap_pelis(out, metas, jueves)

    _guardar_json(cache_path, cache)
    print(
        f"[fichas] {len(vistos)} en cartelera, {len(metas)} fichas totales, {escritas} reescritas.",
        file=sys.stderr,
    )


def _anio_int(anio: str) -> int:
    try:
        return int(anio)
    except (TypeError, ValueError):
        return 0


def jueves_de_esta_semana(hoy: datetime | None = None) -> datetime:
    if hoy is None:
        hoy = datetime.now()
    delta = (hoy.weekday() - 3) % 7
    return (hoy - timedelta(days=delta)).replace(hour=0, minute=0, second=0, microsecond=0)


def main() -> None:
    args = parse_args()
    out = Path(args.output)
    jueves = jueves_de_esta_semana()
    slug = jueves.strftime("%Y-%m-%d")

    print(f"== MoVeTe Cine == semana del {jueves.date()}", file=sys.stderr)

    try:
        tradicional = scrapear_cine_tradicional()
    except Exception as e:
        print(f"[main] Pata tradicional falló: {e}", file=sys.stderr)
        tradicional = []

    try:
        alternativo = scrapear_cine_alternativo(desde=jueves, dias=7)
    except Exception as e:
        print(f"[main] Pata alternativa falló: {e}", file=sys.stderr)
        alternativo = []

    alternativo_cache = out / "alternativo.json"
    if alternativo:
        _guardar_json(alternativo_cache, alternativo)
    else:
        alternativo = _alternativo_en_rango(
            _cargar_json(alternativo_cache, []),
            jueves,
        )
        if alternativo:
            print(
                f"[main] AgendaLP vacía: se usan {len(alternativo)} funciones del último respaldo válido.",
                file=sys.stderr,
            )

    if not tradicional and not alternativo:
        print("[main] Ambas fuentes vacías. No se genera página.", file=sys.stderr)
        sys.exit(1)

    cache_path = out / "peliculas.json"
    tradicional, no_encontrados = enriquecer_con_tmdb(tradicional, cache_path)

    # Dos renders del mismo contenido con canonical distinto: la portada es la
    # cartelera vigente, la edicion fechada es una URL permanente que se indexa
    # sola. Antes las dos apuntaban a /cine/ y el archivo quedaba invisible.
    html_portada = generar(tradicional, alternativo, jueves)
    html_edicion = generar(tradicional, alternativo, jueves,
                           page_url=f"{SITIO}/cine/{slug}/")

    slug_dir = out / slug
    slug_dir.mkdir(parents=True, exist_ok=True)

    (slug_dir / "index.html").write_text(html_edicion, encoding="utf-8")
    (out / "index.html").write_text(html_portada, encoding="utf-8")

    print(f"[main] Generado: {slug_dir / 'index.html'}", file=sys.stderr)

    # Fichas por película (defensivo: nunca debe tumbar la cartelera).
    try:
        generar_fichas(tradicional, out, jueves, out / "fichas.json")
    except Exception as e:
        print(f"[main] Generación de fichas falló (la cartelera igual quedó): {e}", file=sys.stderr)

    if no_encontrados:
        print("[main] --- Sin afiche/datos (revisá alias.json) ---", file=sys.stderr)
        for titulo in no_encontrados:
            print(f"[main] · {titulo}", file=sys.stderr)

    print(slug_dir / "index.html")


if __name__ == "__main__":
    main()
