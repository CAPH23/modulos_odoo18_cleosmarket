# -*- coding: utf-8 -*-
{
    'name': 'Payment Provider: Cobro contra entrega',
    'version': '18.0.1.0.3',
    'category': 'Accounting/Payment Providers',
    'sequence': 360,
    'summary': 'Proveedor de pago para pedidos contra entrega en eCommerce.',
    'description': 'Crea el proveedor de pago Cobro contra entrega para confirmar pedidos, dejarlos pendientes de pago y enviar el ticket de compra adjunto.',
    'author': "Cleo's Market",
    'website': 'https://cleosmarket.com',
    'depends': ['payment', 'sale'],
    'data': [
        'views/payment_cobro_entrega_templates.xml',
        'views/payment_provider_views.xml',
        'data/mail_template_data.xml',
        'data/payment_method_data.xml',
        'data/payment_provider_data.xml',
        'data/payment_cobro_entrega_refresh_data.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'payment_cobro_entrega/static/src/js/post_processing.js',
        ],
    },
    'post_init_hook': 'post_init_hook',
    'uninstall_hook': 'uninstall_hook',
    'license': 'LGPL-3',
    'installable': True,
    'application': False,
}
