# -*- coding: utf-8 -*-
{
    "name": "Boxful Shipping Connector",
    "summary": "Cotización, guías, tracking y webhooks de Boxful para Odoo 18",
    "description": """
Boxful Shipping Connector para Odoo 18 Community
=================================================
* Configuración y credenciales independientes por compañía.
* Lista de couriers Boxful en el checkout (mismo día y entrega programada), a elegir por el cliente.
* Preselección automática del courier según el criterio configurado (más barato/más rápido).
* Cambio manual del courier antes de crear la guía.
* Creación manual del envío desde la transferencia.
* Cobro contra entrega compatible con payment_cobro_entrega (cleo_cod).
* Etiqueta PDF adjunta al chatter y apertura automática.
* Tracking por webhook y consulta periódica de respaldo.
* Barra de progreso dinámica en /my/orders.
* Bloqueo por categorías refrigeradas o no transportables.
* Modo simulado para desarrollar sin crear envíos reales.
""",
    "version": "18.0.1.1.0",
    "category": "Inventory/Delivery",
    "author": "Cleos Market",
    "website": "https://cleosmarket.com",
    "license": "LGPL-3",
    "depends": [
        "stock_delivery",
        "website_sale",
        "portal",
        "mail",
        "base_geolocalize",
        "payment_cobro_entrega",
        "Sitio_web_cleosmarket",
    ],
    "data": [
        "security/goboxful_security.xml",
        "security/ir.model.access.csv",
        "views/goboxful_account_views.xml",
        "views/goboxful_location_views.xml",
        "views/goboxful_log_views.xml",
        "views/delivery_carrier_views.xml",
        "views/product_template_views.xml",
        "views/product_category_views.xml",
        "views/res_partner_views.xml",
        "views/res_country_state_views.xml",
        "views/sale_order_views.xml",
        "views/stock_picking_views.xml",
        "views/portal_templates.xml",
        "views/checkout_templates.xml",
        "data/ir_cron_data.xml",
    ],
    "assets": {
        "web.assets_frontend": [
            "delivery_goboxful/static/src/scss/goboxful_portal.scss",
            "delivery_goboxful/static/src/js/goboxful_portal.js",
            "delivery_goboxful/static/src/scss/goboxful_checkout.scss",
            "delivery_goboxful/static/src/js/goboxful_checkout.js",
        ],
    },
    "post_init_hook": "post_init_hook",
    "installable": True,
    "application": False,
}
