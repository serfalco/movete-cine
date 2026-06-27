"""Generador HTML de Cine para MoVeTe."""

from __future__ import annotations

import html
from collections import defaultdict
from datetime import datetime, timedelta

MESES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]

DIAS = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]

POSTER_PLACEHOLDER = "/assets/img/cine-placeholder.jpg"


def esc(valor: object) -> str:
    return html.escape(str(valor or ""), quote=True)


def rango_texto(jueves: datetime) -> str:
    fin = jueves + timedelta(days=6)
    if jueves.month == fin.month:
        return f"{jueves.day} al {fin.day} de {MESES[fin.month - 1]}"
    return f"{jueves.day} de {MESES[jueves.month - 1]} al {fin.day} de {MESES[fin.month - 1]}"


def meta_badges(idioma: str, formato: str) -> str:
    badges = []
    if idioma:
        idi = "Subtitulada" if idioma.lower().startswith("subt") else "Castellano"
        badges.append(f'<span class="pill">{esc(idi)}</span>')
    if formato:
        badges.append(f'<span class="pill">{esc(formato)}</span>')
    return "".join(badges)


def slugify(valor: str) -> str:
    texto = (valor or "").lower()
    reemplazos = {
        "á": "a",
        "é": "e",
        "í": "i",
        "ó": "o",
        "ú": "u",
        "ñ": "n",
    }
    for origen, destino in reemplazos.items():
        texto = texto.replace(origen, destino)
    limpio = []
    for char in texto:
        if char.isalnum():
            limpio.append(char)
        elif limpio and limpio[-1] != "-":
            limpio.append("-")
    return "".join(limpio).strip("-") or "sala"


def nombre_sala(cine: str) -> str:
    nombre = str(cine or "").strip()
    for prefijo in ("Cinema ", "Cine "):
        if nombre.lower().startswith(prefijo.lower()):
            return nombre[len(prefijo):].strip()
    return nombre


def nav_salas(cines: list[dict]) -> str:
    links = []
    for cine in cines:
        nombre = nombre_sala(cine.get("cine", ""))
        if nombre:
            links.append(f'<a class="filter-button" href="#sala-{slugify(nombre)}">{esc(nombre)}</a>')
    if not links:
        return ""
    return f'<div class="pill-row filter-bar sala-nav" aria-label="Salas comerciales">{"".join(links)}</div>'


def ficha_extra(info: dict | None) -> str:
    if not info:
        return ""

    facts = []

    if info.get("anio"):
        facts.append(f'<span class="movie-fact">🎬 {esc(info["anio"])}</span>')

    if info.get("duracion"):
        try:
            facts.append(f'<span class="movie-fact">⏱ {int(info["duracion"])} min</span>')
        except (TypeError, ValueError):
            pass

    if info.get("generos"):
        facts.append(f'<span class="movie-fact">🎭 {esc(" · ".join(info["generos"]))}</span>')

    if info.get("paises"):
        facts.append(f'<span class="movie-fact">🌎 {esc(" · ".join(info["paises"][:2]))}</span>')

    if info.get("score") not in (None, ""):
        try:
            score = float(info["score"])
            if score > 0:
                facts.append(f'<span class="movie-fact">⭐ {score:.1f}/10</span>')
        except (TypeError, ValueError):
            pass

    if not facts:
        return ""

    return f'<p class="event-meta movie-facts">{" ".join(facts)}</p>'


def creditos_html(info: dict | None) -> str:
    if not info:
        return ""

    partes = []

    if info.get("director"):
        partes.append(f'<p class="movie-credit"><strong>Dir:</strong> {esc(info["director"])}</p>')

    if info.get("elenco"):
        partes.append(f'<p class="movie-credit"><strong>Elenco:</strong> {esc(" · ".join(info["elenco"]))}</p>')

    return "".join(partes)


def sinopsis_html(info: dict | None) -> str:
    if info and info.get("sinopsis"):
        return f'<p>{esc(info["sinopsis"])}</p>'
    return ""


def trailer_html(info: dict | None) -> str:
    if info and info.get("trailer"):
        return f'<p><a class="button small trailer-button" href="{esc(info["trailer"])}" target="_blank" rel="noopener">▶ Ver trailer</a></p>'
    return ""


def poster_url(info: dict | None) -> str:
    if info and info.get("poster"):
        return esc(info["poster"])
    return POSTER_PLACEHOLDER


def bloque_tradicional(cines: list[dict]) -> str:
    if not cines:
        return '<p class="empty">Esta semana no hay cartelera comercial disponible.</p>'

    bloques = []

    for cine in cines:
        peliculas = []

        for peli in cine.get("peliculas", []):
            info = peli.get("tmdb")
            horarios = peli.get("horarios", [])
            horarios_html = "".join(f"<li>{esc(h)}</li>" for h in horarios)

            peliculas.append(
                f"""
                <article class="movie-card">
                  <img class="movie-poster" src="{poster_url(info)}" alt="Afiche de {esc(peli.get('titulo'))}" loading="lazy">
                  <div>
                    <h3>{esc(peli.get('titulo'))}</h3>
                    {ficha_extra(info)}
                    <div class="pill-row">{meta_badges(peli.get('idioma', ''), peli.get('formato', ''))}</div>
                    {creditos_html(info)}
                    {sinopsis_html(info)}
                    {trailer_html(info)}
                    <ul class="times">{horarios_html}</ul>
                  </div>
                </article>
                """
            )

        bloques.append(
            f"""
            <section class="day-block" id="sala-{slugify(nombre_sala(cine.get('cine', '')))}">
              <h2>{esc(nombre_sala(cine.get('cine')))}</h2>
              <p class="event-meta">{esc(cine.get('direccion'))}</p>
              <div class="movie-list">
                {''.join(peliculas)}
              </div>
            </section>
            """
        )

    return "\n".join(bloques)


def bloque_alternativo(funciones: list[dict]) -> str:
    if not funciones:
        return '<p class="empty">Esta semana no hay funciones alternativas cargadas.</p>'

    por_fecha: dict[str, list[dict]] = defaultdict(list)

    for funcion in funciones:
        por_fecha[funcion.get("fecha", "")].append(funcion)

    bloques = []

    for fecha in sorted(por_fecha):
        try:
            d = datetime.strptime(fecha, "%Y-%m-%d")
            dia_label = f"{DIAS[d.weekday()]} {d.day} {MESES[d.month - 1]}"
        except ValueError:
            dia_label = fecha

        cards = []

        for funcion in sorted(por_fecha[fecha], key=lambda x: x.get("hora", "")):
            cards.append(
                f"""
                <article class="event-card">
                  <p class="event-date">{esc(funcion.get('hora'))} hs</p>
                  <h3>{esc(funcion.get('titulo'))}</h3>
                  <p class="event-meta">{esc(funcion.get('espacio'))}</p>
                  <p class="pill">Cine alternativo</p>
                </article>
                """
            )

        bloques.append(
            f"""
            <section class="day-block">
              <h2>{esc(dia_label)}</h2>
              <div class="grid cards">
                {''.join(cards)}
              </div>
            </section>
            """
        )

    return "\n".join(bloques)


def generar(cines_tradicional: list[dict], funciones_alternativo: list[dict], jueves: datetime) -> str:
    rango = rango_texto(jueves)
    fecha_iso = jueves.strftime("%Y-%m-%d")
    trad = bloque_tradicional(cines_tradicional)
    alt = bloque_alternativo(funciones_alternativo)
    salas_nav = nav_salas(cines_tradicional)

    total_peliculas = sum(len(c.get("peliculas", [])) for c in cines_tradicional)
    total_alt = len(funciones_alternativo)

    return f"""<!doctype html>
<html lang="es-AR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Cartelera de cine en La Plata · Semana del {esc(rango)} · MoVeTe</title>
  <meta name="description" content="Cartelera de cine en La Plata para encontrar tu función: salas, cineclubes y funciones especiales. Edición semanal del {esc(rango)}.">
  <link rel="stylesheet" href="/assets/css/movete.css">
</head>

<body id="top">
  <header class="site-header">
    <a class="brand" href="/">MoVeTe<span>●</span></a>
    <nav class="site-nav" aria-label="Secciones principales">
      <a href="/">Inicio</a>
      <a href="/cine/" aria-current="page">Cine</a>
      <a href="/en-vivo/">En vivo</a>
    </nav>
  </header>

  <main>
    <section class="hero compact">
      <p class="eyebrow">Cine · Edición {esc(fecha_iso)}</p>
      <h1>Cartelera de cine en La Plata</h1>
      <p class="lead">Películas en salas, ciclos, cineclubes y funciones especiales para encontrar tu función y armar plan.</p>
      <div class="actions quick-nav">
        <a class="button" href="#cine-tradicional">Cine en salas</a>
        <a class="button secondary" href="#cine-alternativo">Cine alternativo</a>
        <button class="button small" type="button" data-share-page>Compartir</button>
      </div>
    </section>

    <section class="card edition-summary">
      <h2>{total_peliculas} películas en salas comerciales y {total_alt} funciones alternativas.</h2>
      <p>Tu mapa rápido de cine para la semana. Revisá sala, día y horario antes de salir.</p>
    </section>

    <section id="cine-tradicional" class="section">
      <p class="eyebrow">Salas comerciales</p>
      <h2>Cine en salas</h2>
      {salas_nav}
      {trad}
    </section>

    <section id="cine-alternativo" class="section">
      <p class="eyebrow">Cineclubes y espacios culturales</p>
      <h2>Cine alternativo</h2>
      <p>Ciclos, espacios INCAA, proyecciones especiales y cineclubes para moverte por fuera del circuito de siempre.</p>
      {alt}
    </section>

    <section class="ad-box">
      <p class="ad-label">Espacio promocional</p>
      <h2>Tres Empanadas Comedia</h2>
      <p>Stand up en La Plata. Shows a la gorra, todos los viernes.</p>
      <a class="button small" href="https://tresempanadas.com.ar/reservas">Reservar</a>
    </section>

    <section class="card">
      <p class="tag">También en MoVeTe</p>
      <h2>Cartelera en vivo en La Plata</h2>
      <p>Teatro, música, stand up, danza, talleres y propuestas para compartir, cruzarte y encontrarte.</p>
      <a href="/en-vivo/">Ver cartelera en vivo →</a>
    </section>
  </main>

  <footer class="site-footer">
    <div class="footer-inner">
      <div>
        <p class="footer-title">MoVeTe.info</p>
        <p>Cartelera de cine en La Plata · Edición {esc(fecha_iso)}</p>
        <p>Información de películas y afiches: The Movie Database (TMDb). Este producto usa la API de TMDb pero no está avalado ni certificado por TMDb.</p>
      </div>
      <div class="footer-links" aria-label="Links del pie">
        <a href="#top">Arriba</a>
        <a href="#cine-tradicional">Cine en salas</a>
        <a href="#cine-alternativo">Cine alternativo</a>
        <a href="/en-vivo/">En vivo</a>
        <button type="button" data-share-page>Compartir</button>
      </div>
    </div>
  </footer>
  <nav class="mobile-nav" aria-label="Navegación rápida">
    <a href="/">Inicio</a>
    <a href="/cine/" aria-current="page">Cine</a>
    <a href="/en-vivo/">En vivo</a>
    <button type="button" data-share-page>Compartir</button>
  </nav>
  <script src="/assets/js/movete.js" defer></script>
</body>
</html>
"""
