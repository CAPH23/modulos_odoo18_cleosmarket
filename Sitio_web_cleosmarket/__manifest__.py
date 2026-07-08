# -*- coding: utf-8 -*-
{
    "name": "Sitio Web Cleosmarket",
    "summary": "Encabezado, hero, categorías, footer, página Sobre Nosotros y página Contactenos para Super Tienda Cleo",
    "description": """
Sitio Web Cleosmarket
=====================

Segunda etapa del rediseño visual de cleosmarket.com.
Esta versión reemplaza el encabezado, agrega el hero principal de la Home y muestra categorías internas de cuarto nivel del modelo product.category.
    """,
    "version": "18.0.1.8.6",
    "category": "Website/Website",
    "author": "Carlos Palacios",
    "website": "https://www.cleosmarket.com",
    "license": "LGPL-3",
    "depends": [
        "website",
        "website_sale",
        "website_sale_collect",
        "crm",
        "website_crm",
    ],
    "data": [
        "views/templates.xml",
        "views/checkout_templates.xml",
        "views/legal_templates.xml",
        "views/login_templates.xml",
	"views/sale_order_terms_views.xml",
	"views/address_geo_templates.xml",
	"views/confirmation_map_templates.xml",
        "views/checkout_progress_templates.xml",
    ],
    "assets": {
        "web.assets_frontend": [
	    "Sitio_web_cleosmarket/static/lib/leaflet/leaflet.css",
	    "Sitio_web_cleosmarket/static/lib/leaflet/leaflet.js",

            "Sitio_web_cleosmarket/static/src/scss/mi_modulo.scss",
	    "Sitio_web_cleosmarket/static/src/scss/address_geo.scss",
	    "Sitio_web_cleosmarket/static/src/scss/confirmation_map.scss",
            "Sitio_web_cleosmarket/static/src/scss/login.scss",
            "Sitio_web_cleosmarket/static/src/scss/checkout_progress.scss",
	    "Sitio_web_cleosmarket/static/src/scss/checkout_address_improvements.scss",
	    "Sitio_web_cleosmarket/static/src/scss/checkout_address_selection.scss",
	    "Sitio_web_cleosmarket/static/src/scss/checkout_address_required.scss",

            "Sitio_web_cleosmarket/static/src/js/mi_modulo.js",
	    "Sitio_web_cleosmarket/static/src/js/dairy_carousel.js",
            "Sitio_web_cleosmarket/static/src/js/legal_links.js",
	    "Sitio_web_cleosmarket/static/src/js/terms_acceptance.js",
	    "Sitio_web_cleosmarket/static/src/js/address_geo_map.js",
	    "Sitio_web_cleosmarket/static/src/js/confirmation_map.js",
	    "Sitio_web_cleosmarket/static/src/js/checkout_address_improvements.js",
	    "Sitio_web_cleosmarket/static/src/js/checkout_address_selection.js",
	    "Sitio_web_cleosmarket/static/src/js/checkout_address_required.js",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}
