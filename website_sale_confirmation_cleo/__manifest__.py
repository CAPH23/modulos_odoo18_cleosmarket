# -*- coding: utf-8 -*-
{
    'name': 'Cleo - Confirmación de Pedido Mejorada',
    'version': '18.0.1.0.2',
    'category': 'Website/eCommerce',
    'summary': 'Mejora visual y funcional de la página /shop/confirmation para Super Tienda Cleo.',
    'description': '\nPágina de confirmación de pedido personalizada para Super Tienda Cleo.\nIncluye estado de pedido, resumen, botones funcionales, comprobante PDF cuando exista factura y diseño responsive.\n',
    'author': 'Super Tienda Cleo',
    'website': 'https://cleosmarket.com',
    'license': 'LGPL-3',
    'depends': [
        'website_sale',
        'portal',
        'account',
        'sale_management',
    ],
    'data': [
        'views/website_sale_confirmation_templates.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'website_sale_confirmation_cleo/static/src/scss/confirmation.scss',
	    'website_sale_confirmation_cleo/static/src/js/confirmation_cart_clear.js',
        ],
    },
    'images': [
        'static/description/icon.png',
        'static/src/img/logo_super_tienda_cleo.png',
        'static/src/img/confirmation_delivery_bg.png',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
