{
    'name': 'Auto Ribbon Stock',
    'version': '1.0',
    'category': 'Website',
    'summary': 'Mostrar ribbon automáticamente cuando no hay stock',
    'author': 'TuNombre',
    'depends': ['website_sale'],
    'data': [
        'security/ir.model.access.csv',
        'data/website_sale_ribbon_data.xml',
    ],
    'installable': True,
    'application': False,
}
