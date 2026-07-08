# -*- coding: utf-8 -*-
{
    'name': 'Payment Provider: Wompi El Salvador v2',
    'version': '18.0.2.0.3',
    'category': 'Accounting/Payment Providers',
    'sequence': 350,
    'summary': 'Integración avanzada de Wompi El Salvador con Odoo 18: enlace de pago, retorno, webhook, capacidades y configuración extendida.',
    'description': '''Proveedor de pago Wompi El Salvador para Odoo 18 Community.

Versión 2:
- Configuración avanzada de métodos de pago.
- Payload enriquecido para enlaces de pago.
- Consulta de capacidades /Aplicativo.
- Fallback seguro por API para webhook sin header wompi_hash.
- Debug log configurable.
- Almacenamiento de referencias Wompi en la transacción.
- Imágenes del plugin WooCommerce Wompi ubicadas en posiciones equivalentes: icono de gateway, logos de tarjetas y banner de enlace.
- Corrección: método de pago propio wompi_sv_card para no cambiar imágenes de otros proveedores.
- Mejora: logo HD en /shop/payment solo para el método wompi_sv_card, sin afectar otros proveedores.
''',
    'author': 'Super Tienda Cleo',
    'website': 'https://cleosmarket.com',
    'depends': ['payment', 'website_sale'],
    'data': [
        'views/payment_wompi_sv_templates.xml',
        'views/payment_provider_views.xml',
        'data/payment_provider_data.xml',
        'data/payment_method_attach.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'payment_wompi_sv/static/src/scss/payment_wompi_sv_frontend.scss',
	    'payment_wompi_sv/static/src/js/payment_wompi_sv_frontend.js',
        ],
    },
    'post_init_hook': 'post_init_hook',
    'uninstall_hook': 'uninstall_hook',
    'license': 'LGPL-3',
    'application': False,
    'installable': True,
}
