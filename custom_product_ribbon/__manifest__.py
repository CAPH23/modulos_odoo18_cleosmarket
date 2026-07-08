{
    "name": "Custom Product Ribbon",
    "version": "1.0",
    "category": "Website",
    "summary": "Asigna automáticamente el ribbon 'Fuera de stock' a productos sin inventario",
    "author": "Carlos Palacios",
    "depends": ["product", "website_sale", "stock"],
    "data": [
        "data/ribbon_data.xml",
        "data/cron.xml",
    ],
    "installable": True,
    "auto_install": False,
    "application": False,
    "license": "LGPL-3",
}
