# -*- coding: utf-8 -*-
{
    'name': 'Super Tienda Cleo - Diseño de Comprobantes y Tickets',
    'summary': 'Diseño de comprobante de compra, ticket 80mm mejorado y enlaces en portal para Super Tienda Cleo.',
    'version': '18.0.1.11.0',
    'category': 'Accounting/Accounting',
    'author': 'Super Tienda Cleo',
    'website': 'https://cleosmarket.com',
    'license': 'LGPL-3',
    'depends': [
        'account',
        'account_payment',
        'portal',
        'point_of_sale',
        'pos_sale',
    ],
    'data': [
        'report/paperformat.xml',
        'report/cleo_invoice_reports.xml',
        'report/cleo_pos_ticket_reports.xml',
        'views/account_move_views.xml',
        'views/portal_invoice_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'cleo_invoice_design/static/src/scss/backend_invoice.scss',
        ],
        'web.assets_frontend': [
            'cleo_invoice_design/static/src/scss/portal_invoice.scss',
        ],
        'point_of_sale._assets_pos': [
            'cleo_invoice_design/static/src/js/pos_receipt.js',
            'cleo_invoice_design/static/src/xml/pos_receipt.xml',
            'cleo_invoice_design/static/src/scss/pos_receipt.scss',
        ],
    },
    'installable': True,
    'application': False,
}
