# -*- coding: utf-8 -*-
{
    'name': 'PedidosYa Envíos (Courier API)',
    'summary': 'Conector de envíos con la flota de PedidosYa (Courier API v3)',
    'description': """
Integración de Odoo con PedidosYa Courier API v3
================================================
- Nuevo método de envío tipo "PedidosYa" (delivery.carrier).
- Cotización en tiempo real en el checkout del eCommerce (rate_shipment).
- Creación y confirmación del envío al validar la entrega (send_shipping).
- Cancelación de envíos y refresco de estado (manual + cron).
- Modo SIMULADO (sin credenciales), modo PRUEBAS (isTest=true) y PRODUCCIÓN.

Fase 1: cliente simulado que replica el contrato de la API real.
Fase 2 (pendiente): credenciales reales + webhooks SHIPPING_STATUS.
""",
    'version': '18.0.0.3.0',
    'category': 'Inventory/Delivery',
    'author': 'Cleos Market',
    'website': 'https://cleosmarket.com',
    'license': 'LGPL-3',
    'depends': [
        'stock_delivery',      # delivery.carrier + integración con pickings (Odoo 18)
        'website_sale',        # publicación del método de envío en el checkout
        'base_geolocalize',    # partner_latitude / partner_longitude
        'portal',              # barra de seguimiento en /my/orders
    ],
    'data': [
        'views/delivery_carrier_views.xml',
        'views/stock_picking_views.xml',
        'views/portal_templates.xml',
        'data/ir_cron_data.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'delivery_pedidosya/static/src/scss/pedidosya_portal.scss',
            'delivery_pedidosya/static/src/js/pedidosya_portal.js',
        ],
    },
    'installable': True,
    'application': False,
}
