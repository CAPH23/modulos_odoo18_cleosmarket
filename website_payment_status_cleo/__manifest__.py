# -*- coding: utf-8 -*-
{
    'name': 'Cleo - Estado de Pago Mejorado',
    'summary': 'Mejora visual e interactiva de la página temporal /payment/status.',
    'description': '''
Página de estado de pago personalizada para Super Tienda Cleo.
Incluye diseño visual de marca, engranaje animado, contador de redirección
y datos dinámicos de la transacción en curso.
    ''',
    'version': '18.0.1.0.2',
    'category': 'Website/Payment',
    'author': 'Carlos Palacios / Super Tienda Cleo',
    'website': 'https://cleosmarket.com',
    'license': 'LGPL-3',
    'depends': [
        'payment',
        'website_sale',
        'portal',
    ],
    'data': [
        'views/payment_status_templates.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'website_payment_status_cleo/static/src/scss/payment_status.scss',
            'website_payment_status_cleo/static/src/js/payment_status_countdown.js',
        ],
    },
    'images': [
        'static/description/icon.png',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
