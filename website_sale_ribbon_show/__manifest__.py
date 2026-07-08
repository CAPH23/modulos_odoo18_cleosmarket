# -*- coding: utf-8 -*-
# Copyright 2021 RL Software Development ApS. See LICENSE file for full copyright and licensing details.
{
    'name': "Website - show ribbon",

    'summary': """
        Show ribbon on product template in backend.
    """,

    'description': """

        Show ribbon on product template in backend so it is easier to see which products have a ribbon and customize the ribbon.
        
    """,

    'author': "RL Software Development ApS",
    'website': "https://www.rlsd.dk/",

    'category': 'Website/Sale',
    'version': '18.0.1.0.2',

    'depends': [
        'website_sale', 
    ],

    'data': [
        'views/product_template.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
    'license': 'OPL-1',
    
}