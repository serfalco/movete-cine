# MoVeTe · Cine

Generador de cartelera de cine para `movete.info/cine/`.

Este repo no publica por FTP ni depende de Hostinger. Es una herramienta que genera HTML estático para el repo final `Movete-info`.

## Qué hace

- Scrapea cine tradicional desde El Día.
- Scrapea cine alternativo desde Agenda La Plata.
- Enriquece películas con TMDb si existe `TMDB_API_KEY`.
- Genera la edición semanal jueves→miércoles.
- Escribe:
  - `/cine/index.html`
  - `/cine/YYYY-MM-DD/index.html`

## Uso local

```bash
python main.py --output ../Movete-info/cine
```

## Publicación

La publicación real la ejecuta el workflow central del repo `Movete-info`.

Flujo:

```text
Movete-info GitHub Actions
↓
checkout movete-cine
↓
python main.py --output ../Movete-info/cine
↓
commit en Movete-info
↓
Cloudflare Pages
```

## Secrets

Opcional:

```text
TMDB_API_KEY
```

Si no existe, el sitio usa placeholder de cine y sigue funcionando.

## Fuentes

- Cine tradicional: Diario El Día.
- Cine alternativo: Agenda La Plata.
- Datos y afiches: TMDb.
