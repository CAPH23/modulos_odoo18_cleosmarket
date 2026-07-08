# -*- coding: utf-8 -*-
{
    'name': 'Product Variant Image Switch',
    'version': '1.0',
    'category': 'Website',
    'summary': 'Change product image to selected variant image on website',
    'description': 'Replaces main product image with variant image when selected in website shop.',
    'author': 'ChatGPT',
    'depends': ['website_sale'],
    'data': [
        'views/product_template_inherit.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'product_variant_image_switch/static/src/js/product_variant_image.js',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
