"""Genera la ficha propia de cada película para MoVeTe.

Una página por peli en /cine/pelis/<slug>/ con:
- Dónde verla en La Plata esta semana (horarios reales; se degrada solo
  cuando la peli sale de cartelera).
- Galería, puntaje, tráiler/teaser, sinopsis, ficha técnica, elenco, temas,
  saga y similares (data de TMDb).
- Cruce a lo independiente (cine alternativo + teatro) y aviso identificado
  de Tres Empanadas. Filosofía MoVeTe: para Google lo grande, para el ojo
  humano lo chico.

El HTML usa /assets/css/movete.css (cabecera, pie, paleta) + /assets/css/ficha.css
(clases pf-, propias de la ficha, sin pisar nada del resto del sitio).
"""

from __future__ import annotations

import html
import json
from datetime import datetime, timedelta
from urllib.parse import quote_plus

SITIO = "https://movete.info"
PROMO_URL = "https://tresempanadas.com.ar/reservas"

MESES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]


def esc(valor: object) -> str:
    return html.escape(str(valor or ""), quote=True)


def slugify(valor: str) -> str:
    texto = (valor or "").lower()
    for origen, destino in {
        "á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u", "ü": "u", "ñ": "n",
    }.items():
        texto = texto.replace(origen, destino)
    limpio = []
    for char in texto:
        if char.isalnum():
            limpio.append(char)
        elif limpio and limpio[-1] != "-":
            limpio.append("-")
    return "".join(limpio).strip("-") or "pelicula"


def slug_pelicula(titulo: str, anio: str = "") -> str:
    base = slugify(titulo)
    anio = str(anio or "").strip()
    if anio and anio.isdigit():
        return f"{base}-{anio}"
    return base


def _nombre_sala(cine: str) -> str:
    nombre = str(cine or "").strip()
    for prefijo in ("Cinema ", "Cine "):
        if nombre.lower().startswith(prefijo.lower()):
            return nombre[len(prefijo):].strip()
    return nombre or "La Plata"


def _fecha_texto(iso: str) -> str:
    try:
        d = datetime.strptime(iso, "%Y-%m-%d")
        return f"{d.day} de {MESES[d.month - 1]} de {d.year}"
    except (TypeError, ValueError):
        return ""


def rango_texto(jueves: datetime) -> str:
    fin = jueves + timedelta(days=6)
    if jueves.month == fin.month:
        return f"{jueves.day} al {fin.day} de {MESES[fin.month - 1]}"
    return f"{jueves.day} de {MESES[jueves.month - 1]} al {fin.day} de {MESES[fin.month - 1]}"


# --------------------------------------------------------------------------
# Presencia local: en qué salas y horarios está la peli esta semana.
# --------------------------------------------------------------------------

def _mismo_titulo(a: str, b: str) -> bool:
    return slugify(a) == slugify(b) and bool(slugify(a))


def construir_presencia(cines_tradicional: list[dict], tmdb_id, titulo: str) -> list[dict]:
    """Devuelve las salas (con horarios) que dan esta peli esta semana."""
    salas = []
    for cine in cines_tradicional or []:
        for peli in cine.get("peliculas", []):
            info = peli.get("tmdb") or {}
            coincide = False
            if tmdb_id and info.get("tmdb_id") and info["tmdb_id"] == tmdb_id:
                coincide = True
            elif _mismo_titulo(peli.get("titulo", ""), titulo):
                coincide = True
            if not coincide:
                continue

            direccion = str(cine.get("direccion", "")).strip()
            badges = []
            if peli.get("idioma"):
                idi = "Subtitulada" if str(peli["idioma"]).lower().startswith("subt") else "Castellano"
                badges.append(idi)
            if peli.get("formato"):
                badges.append(str(peli["formato"]))

            salas.append(
                {
                    "sala": _nombre_sala(cine.get("cine", "")),
                    "direccion": direccion,
                    "maps": f"https://www.google.com/maps/search/?api=1&query={quote_plus(direccion)}" if direccion else "",
                    "horarios": [str(h) for h in peli.get("horarios", []) if str(h).strip()],
                    "badges": badges,
                }
            )
    return salas


# --------------------------------------------------------------------------
# Bloques de la ficha
# --------------------------------------------------------------------------

def _hero_style(ficha: dict) -> str:
    hero = ficha.get("hero") or ficha.get("backdrop")
    velo = "linear-gradient(180deg,rgba(14,13,16,.32) 0%,rgba(14,13,16,.93) 82%)"
    base = "radial-gradient(120% 120% at 70% 0%,#3a2a4d 0%,#0e0d10 70%)"
    if hero:
        return f"{velo},{base},url('{esc(hero)}')"
    return f"{velo},{base}"


def _poster_html(ficha: dict) -> str:
    poster = ficha.get("poster")
    if poster:
        return f'<div class="pf-poster"><img src="{esc(poster)}" alt="Afiche de {esc(ficha.get("titulo"))}" loading="eager"></div>'
    return f'<div class="pf-poster pf-poster-ph">{esc(ficha.get("titulo"))}</div>'


def _meta_hero(ficha: dict) -> str:
    partes = []
    if ficha.get("anio"):
        partes.append(f"<span>{esc(ficha['anio'])}</span>")
    if ficha.get("duracion"):
        try:
            partes.append(f"<span>{int(ficha['duracion'])} min</span>")
        except (TypeError, ValueError):
            pass
    if ficha.get("generos"):
        partes.append(f"<span>{esc(' · '.join(ficha['generos'][:3]))}</span>")
    try:
        score = float(ficha.get("score") or 0)
        if score > 0:
            partes.append(f'<span class="pf-star">★ {score:.1f}</span>')
    except (TypeError, ValueError):
        pass
    fila = "<span aria-hidden='true'>·</span>".join(partes)
    if ficha.get("certificacion"):
        fila += f'<span class="pf-badge">{esc(ficha["certificacion"])}</span>'
    return fila


def _bloque_donde(ficha: dict, presencia: list[dict], jueves: datetime) -> str:
    titulo = esc(ficha.get("titulo"))
    if not presencia:
        return (
            '<section class="pf-donde pf-donde-off">'
            '<p class="pf-eyebrow">◆ Dónde verla en La Plata</p>'
            f'<h2 class="pf-h2">Esta semana no está en cartelera</h2>'
            f'<p class="pf-off-copy">{titulo} no tiene funciones en La Plata esta semana. '
            'Mirá la cartelera vigente para ver qué se está proyectando ahora.</p>'
            '<a class="pf-backlink" href="/cine/">Ver la cartelera de cine de esta semana →</a>'
            '</section>'
        )

    salas_html = []
    for s in presencia:
        times = []
        for h in s["horarios"]:
            clase = " pf-t3d" if ("3d" in h.lower() or "4d" in h.lower()) else ""
            times.append(f'<li class="pf-time{clase}">{esc(h)}</li>')
        if not times:
            times.append('<li class="pf-time">Consultar horarios</li>')
        maps = ""
        if s["maps"]:
            maps = f'<a class="pf-maps" href="{esc(s["maps"])}" target="_blank" rel="noopener">Cómo llegar →</a>'
        dir_html = f'<p class="pf-dir">{esc(s["direccion"])}</p>' if s["direccion"] else ""
        badges = ""
        if s["badges"]:
            badges = '<div class="pf-salabadges">' + "".join(
                f'<span class="pf-mini">{esc(b)}</span>' for b in s["badges"]
            ) + "</div>"
        salas_html.append(
            f'<div class="pf-sala"><h3 class="pf-sala-nombre">{esc(s["sala"])}</h3>'
            f'{dir_html}{badges}<ul class="pf-times">{"".join(times)}</ul>{maps}</div>'
        )

    wa_svg = (
        '<svg viewBox="0 0 24 24" fill="#25d366" aria-hidden="true"><path d="M12 2a10 10 0 0 0-8.6 15l-1.3 4.7 '
        '4.8-1.3A10 10 0 1 0 12 2zm0 18.2c-1.5 0-3-.4-4.3-1.2l-.3-.2-2.9.8.8-2.8-.2-.3A8.2 8.2 0 1 1 12 20.2zm4.6-6.1c-.2-.1-1.5-.7-1.7-.8-.2-.1-.4-.1-.6.1-.2.2-.6.8-.8 1-.1.1-.3.2-.5.1-.7-.3-1.4-.7-2-1.4-.5-.6-.8-1.1-.9-1.3-.1-.2 0-.4.1-.5l.4-.4c.1-.1.2-.3.2-.4.1-.2 0-.3 0-.4l-.8-1.9c-.2-.5-.4-.4-.6-.4h-.5c-.2 0-.4.1-.6.3-.7.7-.9 1.6-.6 2.6.3 1.1 1 2.1 1.2 2.4.2.2 2 3.1 4.9 4.2 1.9.7 2.3.6 2.7.5.5-.1 1.5-.6 1.7-1.2.2-.6.2-1.1.1-1.2 0-.1-.2-.2-.4-.3z"/></svg>'
    )
    return (
        '<section class="pf-donde">'
        '<p class="pf-eyebrow">◆ Dónde verla en La Plata · esta semana</p>'
        f'<h2 class="pf-h2">En cartelera del {esc(rango_texto(jueves))}</h2>'
        f'{"".join(salas_html)}'
        f'<button class="pf-wa-invite" type="button" data-share-page>{wa_svg}<span>Invitá a alguien: «¿vamos a ver esta?»</span></button>'
        '</section>'
    )


def _bloque_galeria(ficha: dict) -> str:
    galeria = ficha.get("galeria") or []
    if not galeria:
        return ""
    shots = "".join(
        f'<div class="pf-shot" style="background-image:url(\'{esc(u)}\')"></div>' for u in galeria
    )
    return (
        '<section class="pf-sec">'
        '<p class="pf-eyebrow">Galería</p>'
        f'<div class="pf-galeria">{shots}</div>'
        '</section>'
    )


def _bloque_score(ficha: dict) -> str:
    izquierda = ""
    try:
        score = float(ficha.get("score") or 0)
        if score > 0:
            votos = ""
            if ficha.get("votos"):
                try:
                    votos = f'<p class="pf-votos">{int(ficha["votos"]):,} votos en TMDb</p>'.replace(",", ".")
                except (TypeError, ValueError):
                    votos = ""
            izquierda = f'<div><div class="pf-num">{score:.1f}<small>/10</small></div>{votos}</div>'
    except (TypeError, ValueError):
        pass

    botones = []
    if ficha.get("trailer"):
        botones.append(f'<a class="pf-btn" href="{esc(ficha["trailer"])}" target="_blank" rel="noopener">▶ Tráiler</a>')
    if ficha.get("teaser"):
        botones.append(f'<a class="pf-btn pf-btn-ghost" href="{esc(ficha["teaser"])}" target="_blank" rel="noopener">▶ Teaser</a>')

    if not izquierda and not botones:
        return ""
    botones_html = f'<div class="pf-trailers">{"".join(botones)}</div>' if botones else ""
    return f'<section class="pf-score">{izquierda}{botones_html}</section>'


def _bloque_sinopsis(ficha: dict) -> str:
    if not ficha.get("sinopsis"):
        return ""
    return (
        '<section class="pf-sec">'
        '<p class="pf-eyebrow">La película</p>'
        '<h2 class="pf-h2">Sinopsis</h2>'
        f'<p>{esc(ficha["sinopsis"])}</p>'
        '</section>'
    )


def _fila_dato(etiqueta: str, valor: str) -> str:
    if not valor:
        return ""
    return f'<div class="pf-dato"><b>{esc(etiqueta)}</b><span>{esc(valor)}</span></div>'


def _bloque_ficha_tecnica(ficha: dict) -> str:
    datos = []
    datos.append(_fila_dato("Título original", ficha.get("titulo_original")))
    datos.append(_fila_dato("Dirección", ficha.get("director")))
    if ficha.get("guionistas"):
        datos.append(_fila_dato("Guion", " · ".join(ficha["guionistas"])))
    datos.append(_fila_dato("Música", ficha.get("musica")))
    if ficha.get("generos"):
        datos.append(_fila_dato("Género", " · ".join(ficha["generos"])))
    if ficha.get("duracion"):
        try:
            datos.append(_fila_dato("Duración", f"{int(ficha['duracion'])} minutos"))
        except (TypeError, ValueError):
            pass
    datos.append(_fila_dato("Estreno", _fecha_texto(ficha.get("estreno", ""))))
    if ficha.get("paises"):
        datos.append(_fila_dato("País", " · ".join(ficha["paises"][:3])))
    if ficha.get("idiomas"):
        datos.append(_fila_dato("Idioma", " · ".join(ficha["idiomas"][:3])))
    if ficha.get("productoras"):
        datos.append(_fila_dato("Productora", " · ".join(ficha["productoras"][:3])))
    datos_html = "".join(d for d in datos if d)

    elenco_html = ""
    if ficha.get("elenco"):
        actores = []
        for a in ficha["elenco"]:
            if a.get("foto"):
                cara = f'<div class="pf-cara"><img src="{esc(a["foto"])}" alt="{esc(a["nombre"])}" loading="lazy"></div>'
            else:
                cara = f'<div class="pf-cara pf-ph">{esc(a["iniciales"])}</div>'
            rol = f'<small class="pf-rol">{esc(a["personaje"])}</small>' if a.get("personaje") else ""
            actores.append(
                f'<div class="pf-actor">{cara}<small class="pf-actor-nombre">{esc(a["nombre"])}</small>{rol}</div>'
            )
        elenco_html = (
            '<p class="pf-eyebrow pf-eyebrow-in">Elenco</p>'
            f'<div class="pf-cast">{"".join(actores)}</div>'
        )

    temas_html = ""
    if ficha.get("temas"):
        chips = "".join(f'<span class="pf-chip">{esc(t)}</span>' for t in ficha["temas"])
        temas_html = f'<p class="pf-eyebrow pf-eyebrow-in">Temas</p><div class="pf-chips">{chips}</div>'

    ext = []
    if ficha.get("imdb_id"):
        ext.append(f'<a href="https://www.imdb.com/title/{esc(ficha["imdb_id"])}/" target="_blank" rel="noopener">Ver en IMDb ↗</a>')
    if ficha.get("homepage"):
        ext.append(f'<a href="{esc(ficha["homepage"])}" target="_blank" rel="noopener">Sitio oficial ↗</a>')
    ext_html = f'<div class="pf-extlinks">{"".join(ext)}</div>' if ext else ""

    if not (datos_html or elenco_html or temas_html or ext_html):
        return ""
    datos_wrap = f'<div class="pf-datos">{datos_html}</div>' if datos_html else ""
    return (
        '<section class="pf-sec"><div class="pf-ficha">'
        '<p class="pf-eyebrow">Ficha técnica</p>'
        f'{datos_wrap}{elenco_html}{temas_html}{ext_html}'
        '</div></section>'
    )


def _card_film(item: dict, marca_esta: bool = False) -> str:
    poster = item.get("poster")
    titulo = esc(item.get("titulo"))
    if poster:
        bloque = f'<div class="pf-p" style="background-image:url(\'{esc(poster)}\')"></div>'
    else:
        bloque = f'<div class="pf-p pf-p-ph"><span>{titulo}</span></div>'
    anio = esc(item.get("anio"))
    if marca_esta:
        anio = f"{anio} · esta" if anio else "esta"
    return f'<div class="pf-film">{bloque}<small>{titulo}</small><small class="pf-film-anio">{anio}</small></div>'


def _bloque_saga(ficha: dict) -> str:
    col = ficha.get("coleccion")
    if not col or not col.get("partes"):
        return ""
    nombre = esc(col.get("nombre") or "La saga")
    actual = ficha.get("tmdb_id")
    cards = "".join(_card_film(p, marca_esta=(p.get("tmdb_id") == actual)) for p in col["partes"])
    return (
        '<section class="pf-sec">'
        '<p class="pf-eyebrow">Parte de la saga</p>'
        f'<h2 class="pf-h2">{nombre}</h2>'
        f'<div class="pf-filmrow">{cards}</div>'
        '</section>'
    )


def _bloque_similares(ficha: dict) -> str:
    similares = ficha.get("similares") or []
    if not similares:
        return ""
    cards = "".join(_card_film(s) for s in similares)
    return (
        '<section class="pf-sec">'
        '<p class="pf-eyebrow">Si te gusta esta, mirá estas</p>'
        '<h2 class="pf-h2">Similares</h2>'
        f'<div class="pf-filmrow">{cards}</div>'
        '</section>'
    )


def _bloque_cruce() -> str:
    return (
        '<section class="pf-sec">'
        '<p class="pf-eyebrow">También esta semana en La Plata</p>'
        '<h2 class="pf-h2">Date una vuelta por lo de acá</h2>'
        '<p class="pf-cruce-intro">Ya que viniste por el cine, mirá lo que se mueve en la escena '
        'independiente de la ciudad.</p>'
        '<div class="pf-tambien">'
        '<a class="pf-tcard" href="/cine/#cine-alternativo"><span class="pf-ti">🎬</span>'
        '<b>Cine independiente y alternativo</b>'
        '<small>Cineclubes y funciones especiales que no están en el mainstream.</small>'
        '<span class="pf-go">Ver funciones alternativas →</span></a>'
        '<a class="pf-tcard" href="/en-vivo/teatro/"><span class="pf-ti">🎭</span>'
        '<b>Teatro en La Plata</b>'
        '<small>Obras, unipersonales y salas independientes con función esta semana.</small>'
        '<span class="pf-go">Ver cartelera de teatro →</span></a>'
        '</div></section>'
    )


def _bloque_promo() -> str:
    return (
        '<section class="pf-promo">'
        '<p class="pf-ad-label">Espacio promocional</p>'
        '<h3 class="pf-promo-h">Disfrutá del buen cine 🎬</h3>'
        '<p>Y algún viernes date una vuelta por el <b>Tres Empanadas Comedia</b> a reírte en vivo '
        'con la Sociedad Platense de Stand Up. A la gorra, en La Plata.</p>'
        f'<a class="pf-btn" href="{esc(PROMO_URL)}" target="_blank" rel="noopener">Más info del show →</a>'
        '</section>'
    )


def render_schema_ficha(ficha: dict, url: str) -> str:
    movie = {
        "@context": "https://schema.org",
        "@type": "Movie",
        "name": ficha.get("titulo") or "",
        "url": url,
    }
    if ficha.get("titulo_original"):
        movie["alternateName"] = ficha["titulo_original"]
    if ficha.get("sinopsis"):
        movie["description"] = ficha["sinopsis"]
    img = ficha.get("hero") or ficha.get("backdrop") or ficha.get("poster")
    if img:
        movie["image"] = img
    if ficha.get("estreno"):
        movie["datePublished"] = ficha["estreno"]
    if ficha.get("director"):
        movie["director"] = {"@type": "Person", "name": ficha["director"]}
    if ficha.get("generos"):
        movie["genre"] = ficha["generos"]
    if ficha.get("duracion"):
        try:
            movie["duration"] = f"PT{int(ficha['duracion'])}M"
        except (TypeError, ValueError):
            pass
    actores = [{"@type": "Person", "name": a["nombre"]} for a in ficha.get("elenco", [])[:6] if a.get("nombre")]
    if actores:
        movie["actor"] = actores
    try:
        score = float(ficha.get("score") or 0)
        votos = int(ficha.get("votos") or 0)
        if score > 0 and votos > 0:
            movie["aggregateRating"] = {
                "@type": "AggregateRating",
                "ratingValue": round(score, 1),
                "bestRating": 10,
                "ratingCount": votos,
            }
    except (TypeError, ValueError):
        pass
    return '<script type="application/ld+json">' + json.dumps(movie, ensure_ascii=False) + "</script>"


def render_ficha(ficha: dict, presencia: list[dict], jueves: datetime, anio_actual: int) -> str:
    slug = slug_pelicula(ficha.get("titulo", ""), ficha.get("anio", ""))
    url = f"{SITIO}/cine/pelis/{slug}/"
    titulo = esc(ficha.get("titulo"))
    og_image = ficha.get("hero") or ficha.get("backdrop") or ficha.get("poster") or f"{SITIO}/assets/images/cartelera-cine.jpg"

    descr_base = f"{ficha.get('titulo')} en La Plata: dónde y a qué hora verla esta semana, más ficha completa — dirección, elenco, sinopsis, tráiler y temas."
    tagline_html = f'<p class="pf-tagline">{esc(ficha["tagline"])}</p>' if ficha.get("tagline") else ""

    cuerpo = "".join(
        [
            _bloque_donde(ficha, presencia, jueves),
            _bloque_galeria(ficha),
            _bloque_score(ficha),
            _bloque_sinopsis(ficha),
            _bloque_ficha_tecnica(ficha),
            _bloque_saga(ficha),
            _bloque_similares(ficha),
            _bloque_cruce(),
            _bloque_promo(),
        ]
    )

    return f"""<!doctype html>
<html lang="es-AR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{titulo} en La Plata: horarios, salas y ficha completa · MoVeTe</title>
  <meta name="description" content="{esc(descr_base)}">
  <link rel="canonical" href="{esc(url)}">
  <meta property="og:type" content="video.movie">
  <meta property="og:site_name" content="MoVeTe">
  <meta property="og:title" content="{titulo} en La Plata · MoVeTe">
  <meta property="og:description" content="{esc(descr_base)}">
  <meta property="og:url" content="{esc(url)}">
  <meta property="og:image" content="{esc(og_image)}">
  <meta name="twitter:card" content="summary_large_image">
  {render_schema_ficha(ficha, url)}
  <link rel="icon" href="/favicon.svg" type="image/svg+xml">
  <link rel="icon" href="/favicon.ico" sizes="32x32">
  <link rel="apple-touch-icon" href="/apple-touch-icon.png">
  <link rel="stylesheet" href="/assets/css/movete.css">
  <link rel="stylesheet" href="/assets/css/ficha.css">
</head>

<body class="pf-body">
  <header class="site-header">
    <a class="brand" href="/">MoVeTe<span>●</span></a>
    <nav class="site-nav" aria-label="Secciones principales">
      <a href="/">Inicio</a>
      <a href="/cine/">Cine</a>
      <a href="/cine/pelis/" aria-current="page">Pelis</a>
      <a href="/en-vivo/">En vivo</a>
    </nav>
  </header>

  <div class="pf-hero" style="background-image:{_hero_style(ficha)}">
    <div class="pf-hero-inner">
      {_poster_html(ficha)}
      <div class="pf-hero-copy">
        <h1 class="pf-h1">{titulo}</h1>
        {tagline_html}
        <div class="pf-meta">{_meta_hero(ficha)}</div>
      </div>
    </div>
  </div>

  <main class="pf-wrap">
    {cuerpo}
    <section class="pf-sec">
      <a class="pf-backlink" href="/cine/">← Volver a la cartelera de cine en La Plata</a>
    </section>
    <p class="pf-credit">Información de la película, imágenes y datos: The Movie Database (TMDb). Este producto usa la API de TMDb pero no está avalado ni certificado por TMDb. Horarios y funciones: confirmá con cada sala.</p>
  </main>

  <footer class="site-footer">
    <p class="footer-line">
      <span class="footer-brand">MoVeTe<span>.</span></span>
      <span aria-hidden="true">·</span>
      <span>La Plata</span>
      <span aria-hidden="true">·</span>
      <span>{anio_actual}</span>
      <span aria-hidden="true">·</span>
      <button class="footer-share" type="button" data-share-page title="Avisá que existimos por WhatsApp" aria-label="Avisá que existimos por WhatsApp">Avisá que existimos <img class="share-icon" src="/assets/icons/whatsapp.svg" alt=""></button>
    </p>
  </footer>
  <script src="/assets/js/movete.js" defer></script>
</body>
</html>
"""


# --------------------------------------------------------------------------
# Home de la sección /cine/pelis/
# --------------------------------------------------------------------------

def _card_indice(meta: dict) -> str:
    slug = meta["slug"]
    poster = meta.get("poster")
    titulo = esc(meta.get("titulo"))
    if poster:
        bloque = f'<div class="pf-ip" style="background-image:url(\'{esc(poster)}\')"></div>'
    else:
        bloque = f'<div class="pf-ip pf-p-ph"><span>{titulo}</span></div>'
    sub = []
    if meta.get("anio"):
        sub.append(esc(meta["anio"]))
    if meta.get("generos"):
        sub.append(esc(" · ".join(meta["generos"][:2])))
    subt = " · ".join(sub)
    marca = '<span class="pf-icartelera">En cartelera</span>' if meta.get("en_cartelera") else ""
    return (
        f'<a class="pf-icard" href="/cine/pelis/{esc(slug)}/">{bloque}{marca}'
        f'<b>{titulo}</b><small>{subt}</small></a>'
    )


def render_indice(fichas_meta: list[dict], jueves: datetime, anio_actual: int) -> str:
    url = f"{SITIO}/cine/pelis/"
    rango = rango_texto(jueves)
    activas = [m for m in fichas_meta if m.get("en_cartelera")]
    otras = [m for m in fichas_meta if not m.get("en_cartelera")]

    def grilla(items):
        return '<div class="pf-igrid">' + "".join(_card_indice(m) for m in items) + "</div>"

    secciones = []
    if activas:
        secciones.append(
            '<section class="pf-sec"><h2 class="pf-h2">En cartelera esta semana</h2>'
            f'<p class="pf-cruce-intro">Fichas de las películas que se están dando en La Plata del {esc(rango)}.</p>'
            f'{grilla(activas)}</section>'
        )
    if otras:
        secciones.append(
            '<section class="pf-sec"><h2 class="pf-h2">Fichas del archivo</h2>'
            '<p class="pf-cruce-intro">Películas que pasaron por la cartelera. La ficha queda, '
            'con su elenco, sinopsis y saga.</p>'
            f'{grilla(otras)}</section>'
        )
    if not secciones:
        secciones.append('<section class="pf-sec"><p class="pf-cruce-intro">Todavía no hay fichas para mostrar.</p></section>')

    schema = {
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        "name": "Fichas de películas en cartelera en La Plata",
        "url": url,
    }

    return f"""<!doctype html>
<html lang="es-AR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Fichas de películas en cartelera en La Plata · MoVeTe</title>
  <meta name="description" content="Fichas completas de las películas en cartelera en La Plata: horarios, salas, elenco, sinopsis, tráilers y saga. Actualizado cada semana.">
  <link rel="canonical" href="{esc(url)}">
  <meta property="og:type" content="website">
  <meta property="og:site_name" content="MoVeTe">
  <meta property="og:title" content="Fichas de películas en cartelera en La Plata · MoVeTe">
  <meta property="og:description" content="Cada película en cartelera con su ficha completa: dónde verla, elenco, sinopsis, tráiler y saga.">
  <meta property="og:url" content="{esc(url)}">
  <meta property="og:image" content="{SITIO}/assets/images/cartelera-cine.jpg">
  <meta name="twitter:card" content="summary_large_image">
  <script type="application/ld+json">{json.dumps(schema, ensure_ascii=False)}</script>
  <link rel="icon" href="/favicon.svg" type="image/svg+xml">
  <link rel="icon" href="/favicon.ico" sizes="32x32">
  <link rel="apple-touch-icon" href="/apple-touch-icon.png">
  <link rel="stylesheet" href="/assets/css/movete.css">
  <link rel="stylesheet" href="/assets/css/ficha.css">
</head>

<body class="pf-body pf-index">
  <header class="site-header">
    <a class="brand" href="/">MoVeTe<span>●</span></a>
    <nav class="site-nav" aria-label="Secciones principales">
      <a href="/">Inicio</a>
      <a href="/cine/">Cine</a>
      <a href="/cine/pelis/" aria-current="page">Pelis</a>
      <a href="/en-vivo/">En vivo</a>
    </nav>
  </header>

  <main class="pf-wrap">
    <section class="pf-intro">
      <p class="pf-eyebrow">Cine · Fichas</p>
      <h1 class="pf-h1-index">Cada película, con su ficha completa</h1>
      <p class="pf-lead">Dónde y a qué hora verla en La Plata, más elenco, sinopsis, tráiler, saga y temas. La cartelera te dice qué hay; la ficha te cuenta la película.</p>
    </section>
    {"".join(secciones)}
    <section class="pf-sec">
      <a class="pf-backlink" href="/cine/">← Volver a la cartelera de cine en La Plata</a>
    </section>
  </main>

  <footer class="site-footer">
    <p class="footer-line">
      <span class="footer-brand">MoVeTe<span>.</span></span>
      <span aria-hidden="true">·</span>
      <span>La Plata</span>
      <span aria-hidden="true">·</span>
      <span>{anio_actual}</span>
    </p>
  </footer>
  <script src="/assets/js/movete.js" defer></script>
</body>
</html>
"""
