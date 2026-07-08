# -*- coding: utf-8 -*-
# Part of the "Ayudas de checkout" module.
# Copyright 2026 Carlos Palacios. License LGPL-3.
{
    'name': 'Ayudas de checkout (motivos para habilitar el botón)',
    'version': '18.0.1.1.0',
    'category': 'Website/eCommerce',
    'summary': 'Muestra, encima del botón "Proceder a comprar", un texto de ayuda '
               'a la vez indicando qué falta para poder continuar la compra.',
    'description': """
Ayudas de checkout
==================

Mejora la experiencia del checkout en el eCommerce de Odoo 18: cuando el botón
"Proceder a comprar" está deshabilitado, muestra justo encima un único texto de
ayuda —el de mayor prioridad entre las condiciones sin resolver— para que el
cliente sepa exactamente qué le falta.

A medida que el cliente resuelve cada condición (dirección, método de entrega,
monto mínimo, términos y condiciones), aparece la siguiente ayuda en orden de
prioridad, hasta que el botón se habilita y el mensaje desaparece.

* Un solo mensaje a la vez, por prioridad configurable.
* Reactivo: se actualiza ante cambios del DOM y del cliente.
* Sutil, visible y responsive; accesible (aria-live).
* Sin plantillas que sobrescribir: se integra por JS y CSS.
""",
    'author': 'Carlos Palacios',
    'maintainer': 'Carlos Palacios',
    'website': '',
    'support': 'ph03001gnu@yahoo.com',
    'depends': ['website_sale'],
    'assets': {
        'web.assets_frontend': [
            'website_sale_checkout_hints/static/src/scss/checkout_hints.scss',
            'website_sale_checkout_hints/static/src/js/checkout_hints.js',
        ],
    },
    'license': 'LGPL-3',
    'installable': True,
    'application': False,
}
