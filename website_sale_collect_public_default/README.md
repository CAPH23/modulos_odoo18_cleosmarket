# Website Sale Collect Public Default Zip

Módulo para Odoo 18 Community.

## Objetivo

Permite que el popup de **puntos de recogida** de `website_sale_collect` muestre la tienda aunque el visitante esté como **Public User**, sin iniciar sesión y sin dirección de envío todavía.

Por defecto usa:

- ZIP: `01101`
- País: `SV` / El Salvador

## Icono

Incluye el icono de Super Tienda Cleo en:

```text
static/description/icon.png
```

Ese es el icono que Odoo muestra en la ventana/lista de instalación de módulos.

## Instalación

1. Copiar la carpeta `website_sale_collect_public_default` dentro de tu ruta de addons, por ejemplo:

```bash
/opt/odoo18/odoo-extra-addons/
```

2. Reiniciar Odoo:

```bash
sudo systemctl restart odoo18
```

3. Activar modo desarrollador en Odoo.
4. Apps > Actualizar lista de aplicaciones.
5. Buscar e instalar:

```text
Website Sale Collect Public Default Zip
```

## Parámetros opcionales

Puedes cambiar el ZIP o país desde Parámetros del Sistema:

```text
website_sale_collect_public_default.zip_code = 01101
website_sale_collect_public_default.country_code = SV
```

Si no existen esos parámetros, el módulo usa esos valores por defecto.
