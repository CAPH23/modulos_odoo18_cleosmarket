# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repository is

This is the **extra-addons folder for a single live Odoo 18 instance** running "Super Tienda Cleo"
(cleosmarket.com), an e-commerce + POS grocery business in El Salvador. It is not a standalone
application with its own build/run/test pipeline — everything here is installed into, and exercised
through, a real Odoo server process. There is no bundler, no package.json, no separate test runner;
all "build" and "test" activity happens via `odoo-bin` against the live database.

The repo is a mix of two kinds of content, and they should be treated differently:
- **Custom modules written for this business** (Sitio_web_cleosmarket, payment_wompi_sv,
  delivery_pedidosya, cleo_invoice_design, the various `website_*` and product-ribbon modules, etc.)
- **Vendored copies of OCA community repos**, checked in directly as plain folders (not submodules):
  `multi-company`, `l10n_sv`, `pos`, `server-ux`, `reporting-engine`, `account-financial-reporting`.
  Each of these is a multi-module container (e.g. `multi-company/` holds 30 separate addons). Treat
  their contents as third-party code — don't refactor across them or "clean up" their conventions;
  patch narrowly if a fix is needed and prefer overriding in a custom module instead.

## Entorno

- Odoo 18 Community Edition sobre Ubuntu, en una VM de Google Cloud.
- **Esta es la VM de PRUEBAS** (`http://136.107.12.30:8069`). Producción es `https://cleosmarket.com`
  y **nunca se toca desde aquí**; el código viaja a producción solo vía GitHub.
- Core de Odoo: `/opt/odoo18/odoo` (v18.0) — **solo lectura como referencia, jamás se modifica**.
- Módulos personalizados: `/opt/odoo18/odoo-extra-addons` (este repositorio).
- Entorno virtual de Python: `/opt/odoo18/odoo-venv` (Python 3.12) — usar siempre este intérprete,
  nunca el python del sistema.
- Archivo de configuración: `/etc/odoo18.conf`.
- Servicio systemd: `odoo18.service` (ejecuta `odoo-bin -c /etc/odoo18.conf` como usuario del
  sistema **`odoo18`** — no `odoo`; verificado en la unit file).
- Base de datos de desarrollo/pruebas: `cleosmarket.com` (coincide con `dbfilter = ^cleosmarket.*$`
  en `/etc/odoo18.conf`). En esta misma VM también existe `SuperTiendaCleo.com_pruebas`; confirmar
  contra cuál se está trabajando antes de correr comandos si hay dudas.
- La BD `cleosmarket.com` es un **clon de producción neutralizado**: correo saliente, crons y
  proveedores de pago están desactivados. **No reactivar nada de eso de forma global.**
- `.vscode/settings.json` ya apunta el tooling de Python/pylint al venv y a `/opt/odoo18/odoo` para
  resolución de imports (`python.analysis.extraPaths`), y habilita el plugin `pylint_odoo` con solo
  los checks `odoolint`.
- El parámetro de sistema `report.url` (`ir.config_parameter`) está fijado a `http://127.0.0.1:8069`
  en la BD `cleosmarket.com` de esta VM. Ver "wkhtmltopdf y `report.url`" más abajo — es necesario
  para que la generación de PDFs no se cuelgue, y **no vive en el código ni en `/etc/odoo18.conf`**,
  así que se pierde si la BD se reemplaza por un clon fresco de producción.

## wkhtmltopdf y `report.url` (limitación de red en GCP)

Los reportes PDF (`sale.action_report_saleorder` y cualquier otro que use el layout estándar) incrustan
el logo/fondo de la compañía como una URL HTTP que **wkhtmltopdf descarga en el momento de renderizar**.
Esa URL se arma a partir de `web.base.url`, que en esta VM apunta a su propia IP pública/externa
(`http://136.107.12.30:8069`, ver "Entorno" arriba).

Google Cloud VPC no soporta "hairpin NAT": una instancia no puede alcanzar su propia IP externa desde
adentro. El resultado es que wkhtmltopdf se queda esperando esa descarga hasta hacer timeout (~2
minutos, log: `wkhtmltopdf: Exit with code 1 due to network error: TimeoutError`), y cualquier flujo
sincrónico que genere un PDF dentro de un request HTTP —por ejemplo `payment_cobro_entrega` adjuntando
el ticket de compra al confirmar el pedido— se percibe como la página "congelada" hasta que el proxy
corta la conexión.

Fix aplicado (2026-07-16): parámetro de sistema `report.url = http://127.0.0.1:8069`. Odoo usa ese
parámetro en vez de `web.base.url` **solo** para que wkhtmltopdf busque las imágenes de los reportes
(`ir_actions_report.py::_get_report_url`), sin afectar los links públicos que van en correos o el
portal. Si la BD se restaura desde un backup/clon de producción y el problema reaparece (PDFs o pagos
con "Cobro contra entrega" colgándose), reaplicar con:

```python
env['ir.config_parameter'].sudo().set_param('report.url', 'http://127.0.0.1:8069')
```

## Mantenimiento del core

Actualización de seguridad aplicada a `/opt/odoo18/odoo` (rama `origin/18.0`) para cerrar la
vulnerabilidad #4, en ambas máquinas:

| Máquina             | Fecha de actualización | Commit resultante | Punto de retorno (pre-update) |
|---------------------|------------------------|--------------------|--------------------------------|
| VM de producción     | 2026-07-18             | `6251a03c429`      | `0a00e430254ec6efaf021bdc917505e87cc9f422` |
| VM de pruebas        | 2026-07-16             | `02145783a5c`      | `7db31717cfad431ac44d8c1b90992c2716cf6424` |

Verificado desde esta VM (pruebas): `git log -1` en `/opt/odoo18/odoo` confirma HEAD en
`02145783a5c97f939e1bfcb428ee950f7dd7be03` (2026-07-16) y que el punto de retorno
`7db31717cfad431ac44d8c1b90992c2716cf6424` es ancestro de HEAD. El commit y punto de retorno de
producción no se verificaron desde aquí (sin acceso a esa VM); quedan registrados según lo
confirmado por el responsable de la actualización.

Para revertir en caso de regresión: `git checkout <punto de retorno>` en `/opt/odoo18/odoo` de la
máquina correspondiente, seguido de un reinicio del servicio (`odoo18.service` en pruebas).

## Comandos frecuentes

Ejecutar como usuario `odoo18` (o vía `sudo -u odoo18`), que es el usuario real bajo el que corren
el servicio y el venv.

```bash
# Reiniciar Odoo
sudo systemctl restart odoo18.service

# Ver logs en vivo
sudo journalctl -u odoo18.service -f

# Actualizar un módulo (detener el servicio antes evita que dos procesos compitan por el puerto/DB)
sudo systemctl stop odoo18.service && \
sudo -u odoo18 /opt/odoo18/odoo-venv/bin/python3 /opt/odoo18/odoo/odoo-bin \
  -c /etc/odoo18.conf -d cleosmarket.com -u nombre_modulo --stop-after-init && \
sudo systemctl start odoo18.service

# Instalar un módulo por primera vez (mismo patrón, con -i en vez de -u)
sudo systemctl stop odoo18.service && \
sudo -u odoo18 /opt/odoo18/odoo-venv/bin/python3 /opt/odoo18/odoo/odoo-bin \
  -c /etc/odoo18.conf -d cleosmarket.com -i nombre_modulo --stop-after-init && \
sudo systemctl start odoo18.service

# Correr tests de un módulo: igual que actualizar pero agregando --test-enable
sudo systemctl stop odoo18.service && \
sudo -u odoo18 /opt/odoo18/odoo-venv/bin/python3 /opt/odoo18/odoo/odoo-bin \
  -c /etc/odoo18.conf -d cleosmarket.com -u nombre_modulo --test-enable --stop-after-init && \
sudo systemctl start odoo18.service

# Lint de un módulo (pylint_odoo, igual que .vscode y Sitio_web_cleosmarket/.pylintrc)
/opt/odoo18/odoo-venv/bin/pylint --load-plugins=pylint_odoo --disable=all --enable=odoolint <module_dir>
```

`nombre_modulo` es el nombre de la carpeta que contiene directamente `__manifest__.py`
(p. ej. `l10n_sv_city`, no `l10n_sv`; `base_multi_company`, no `multi-company`).

Formateo para `Sitio_web_cleosmarket` sigue su `pyproject.toml`: Black a line-length 88, isort con
perfil `black`. El resto de módulos personalizados no define configuración de formateador propia.

## Reglas de desarrollo

- **Nunca modificar el core de Odoo** (`/opt/odoo18/odoo`); siempre extender por herencia (`_inherit`).
- Seguir las guías de desarrollo de la OCA.
- Todo modelo nuevo debe incluir sus reglas de acceso en `security/ir.model.access.csv`.
- Cada tarea se trabaja en una rama `feature/`, nunca directo en `main`.
- Antes de dar por terminada una tarea: actualizar el módulo, revisar el log en busca de errores y
  advertencias, y correr los tests.
- Proyecto en curso: sitio web con tienda en línea, integración de pasarela de pagos y conector con
  PedidosYa (ver `Sitio_web_cleosmarket`, `payment_wompi_sv`/`payment_cubopago`/
  `payment_cobro_entrega`, y `delivery_pedidosya` en el mapa de módulos más abajo).

## addons_path (`/etc/odoo18.conf`)

Odoo's addons_path scanning is **one level deep only** per configured path entry. This matters here:

- The repo root (`/opt/odoo18/odoo-extra-addons`) is itself on the path, so every module that sits
  directly at the repo root (Sitio_web_cleosmarket, payment_wompi_sv, delivery_pedidosya,
  cleo_invoice_design, all the `website_*` modules, etc.) is auto-discovered.
- The vendored OCA containers (`multi-company`, `l10n_sv`, `pos`, `server-ux`, `reporting-engine`,
  `account-financial-reporting`) hold their modules one level deeper, so each container also has its
  own **explicit** addons_path entry in `/etc/odoo18.conf`. If you add a new vendored multi-module
  repo, remember to add its folder to addons_path too — being under the repo root is not enough for
  nested modules.
- Being on addons_path does **not** mean a module is installed in the `cleosmarket` database — that's
  tracked in `ir.module.module` and toggled via the Apps UI or the `-i`/`-u` flags above. Check
  installed state before assuming a module's code is actually running.

## Module map

**El Salvador localization**: `l10n_sv` (OCA-style suite of 8 modules: DTE document types, cities,
chart of accounts, fiscal positions, incoterms, payment terms, UoM) and `l10n_sv_1` (a separate,
older single-module base chart of accounts for El Salvador). `website_default_country` and
`no_zip_required` force El Salvador / drop postal-code requirements at checkout.

**Storefront (Super Tienda Cleo)**: `Sitio_web_cleosmarket` (primary, actively developed — see below),
`mi_sitio_web_personalizado` (footer/social links), `cleo_invoice_design` (invoice & 80mm POS ticket
layout + portal links), `website_payment_status_cleo`, `website_sale_confirmation_cleo`,
`website_sale_checkout_hints`, `website_sale_cleo_category_sidebar`, `website_google_map_custom`,
`website_product_border`, `website_snow_effect`, `website_plausible`, `hide_empty_product_categories`,
`product_variant_image_switch`, `website_sale_collect_public_default`.

**Out-of-stock ribbons** (⚠ overlapping — see below): `auto_ribbon_stock`, `auto_ribbon_stock_clean`,
`auto_set_out_of_stock_ribbon`, `custom_product_ribbon`, `product_ribbon_out_of_stock`,
`website_sale_ribbon_show`.

**Payments & delivery**: `payment_wompi_sv`, `payment_cubopago`, `payment_cobro_entrega` (each a
`payment.provider` integration), `delivery_pedidosya` (`delivery.carrier` integration with PedidosYa's
Courier API v3).

**POS**: the vendored `pos/` OCA suite (barcode price rule, order-number display, total-quantity
display, order-summary divider, lot/serial barcode scan), plus `bi_pos_restrict_zero_qty` and
`point_of_sale_image_512_V2`.

**Multi-company** (vendored OCA `multi-company/`, 30 modules): extends multi-company support across
partners, products, CRM (stage/tag/lost reason), calendar, HR employee, mail templates, UTM, and
inter-company purchase/sale/stock rules.

**Reporting/base utilities** (vendored OCA): `account-financial-reporting` (financial reports + tax
balance), `reporting-engine` → `report_xlsx` (xlsx report base), `server-ux` → `date_range`.

## Things to verify before touching — known overlaps

- Six different modules implement "out of stock ribbon" behavior with essentially the same intent.
  Check the Apps list in the live DB for which one(s) are actually installed before modifying any of
  them — editing an uninstalled duplicate has no effect on the live site.
- `l10n_sv` and `l10n_sv_1` both provide a base chart of accounts for El Salvador. Confirm which one
  the `cleosmarket` database actually loaded before changing either.

## Primary active development module: `Sitio_web_cleosmarket`

This is where ongoing storefront redesign work happens (currently at version `18.0.1.8.6`). It depends
on `website`, `website_sale`, `website_sale_collect`, `crm`, `website_crm`, and covers: header/hero/
category redesign, checkout flow (address geolocation via a vendored Leaflet build, address selection/
requirement changes, checkout progress bar, T&Cs acceptance), a custom login page, legal pages, and an
order-confirmation map.

Conventions specific to this module:
- Full standard Odoo module layout: `controllers/`, `models/`, `views/`, `wizards/`, `security/`
  (`ir.model.access.csv`, `record_rules.xml`, `security.xml`), `data/`, `demo/`, `migrations/`
  (versioned `pre-migration.py`/`post-migration.py` scripts), `i18n/` (`es.po`), `tests/`.
- Frontend assets are registered explicitly per-file under `web.assets_frontend` in
  `__manifest__.py` — there's no glob/auto-discovery, so a new JS/SCSS file must be added to that
  list or it silently won't load.
- Uses a vendored Leaflet build under `static/lib/leaflet/` for map features rather than a package
  manager dependency — follow that pattern for any similar third-party frontend library need.

## Payment & delivery integration pattern

`payment_wompi_sv`, `payment_cubopago`, and `payment_cobro_entrega` all follow the same shape: a
`const.py` for provider constants, `controllers/main.py` for the return/webhook HTTP routes, and
`models/payment_provider.py` + `models/payment_transaction.py` implementing the Odoo payment provider
API. Follow this split when adding another payment provider. `delivery_pedidosya` follows the
equivalent shape for a delivery carrier: `models/pedidosya_client.py` (API client), `models/
delivery_carrier.py` / `stock_picking.py` / `sale_order.py` (Odoo-side integration), and
`controllers/webhook.py` / `portal.py` / `website_sale.py` plus an `ir.cron` job in `data/`.
