# MoVeTe · Sistema de Cine

Genera, una vez por semana, la página de cartelera de cine de La Plata para
**movete.info**. Junta dos fuentes y arma un HTML autónomo y archivable con el
diseño de MoVeTe.

## Qué hace

- **Cine tradicional** (comercial): scrapea la guía de cines del diario **El Día**.
  Cartelera por complejo → películas → horarios.
- **Cine alternativo**: scrapea **Agenda La Plata** filtrando la etiqueta "Cine".
  Ciclos, INCAA, cine-clubes, funciones especiales.
- Genera `cine/AAAA-MM-DD.html` (la fecha es el jueves de inicio de semana).
- Genera `cine/index.html` que redirige a la cartelera más reciente.
- Las páginas viejas **no se borran**: se acumulan como archivo (bueno para SEO).

## Cuándo corre

- **Automático**: todos los **jueves 7:00 (hora Argentina)** vía GitHub Actions.
- **Manual**: pestaña *Actions* → *MoVeTe Cine semanal* → *Run workflow*.

La cartelera publicada vale de ese jueves hasta el jueves siguiente.

## Estructura

```
main.py                      orquestador (junta fuentes + genera)
scraper_eldia.py             cine tradicional (El Día)
scraper_agendalp_cine.py     cine alternativo (Agenda La Plata)
generar_html.py              arma el HTML con el diseño MoVeTe
requirements.txt
.github/workflows/cine.yml    cron jueves 7am + FTP
```

## Configuración (una sola vez)

En el repo de GitHub → *Settings* → *Secrets and variables* → *Actions*,
crear estos secrets:

| Secret | Qué es |
|---|---|
| `FTP_SERVER` | host FTP de Hostinger (ej: `ftp.movete.info`) |
| `FTP_USER` | usuario FTP |
| `FTP_PASSWORD` | contraseña FTP |
| `FTP_REMOTE_CINE` | carpeta destino en el server (ej: `/public_html/cine/`) |

## Principio de diseño

Si una fuente falla (El Día caído, Agenda cambió el HTML), la otra sigue y la
página sale igual con lo que haya. Si fallan las dos, **no** se pisa la página
anterior. Es una agenda, no un respirador: cuando algo se rompe, se arregla.

## Pendiente / a futuro

- Pósters (esta versión es solo texto, usa el placeholder de cine).
- Títulos definitivos de las dos secciones (hoy: "Cine tradicional" / "alternativo").
