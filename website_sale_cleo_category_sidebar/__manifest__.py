# -*- coding: utf-8 -*-
{
    'name': 'Super Tienda Cleo - Menú lateral de categorías',
    'summary': 'Rediseña el menú lateral de categorías de la tienda con estilo Super Tienda Cleo.',
    'description': """
Menú lateral dinámico de categorías para /shop.
- Usa product.public.category.
- Excluye categorías específicas.
- Mantiene enlaces /shop/category/<slug>.
- Agrega botón colapsable.
- Mantiene el menú visible con position: sticky.
- Diseño visual alineado al estilo crema, azul y amarillo de Cleosmarket.
    """,
    'version': '18.0.1.0.4',
    'category': 'Website/Website',
    'author': 'Super Tienda Cleo',
    'website': 'https://cleosmarket.com',
    'license': 'LGPL-3',
    'depends': ['website_sale'],
    'data': [
        'views/category_sidebar_templates.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'website_sale_cleo_category_sidebar/static/src/scss/category_sidebar.scss',
            'website_sale_cleo_category_sidebar/static/src/js/category_sidebar.js',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
