========
CuboPago
========

Proveedor de pago **CuboPago** para Odoo 18, construido sobre la arquitectura
nativa de Odoo (``payment.provider``, ``payment.transaction`` y controladores
HTTP).

Funcionalidades
===============

* Creación automática del link de pago CuboPago desde el checkout de Odoo.
* Redirección segura del cliente a la pantalla de pago de CuboPago.
* Confirmación por webhook con **verificación obligatoria por API**: como el
  webhook de CuboPago no viene firmado, cada notificación se valida volviendo a
  consultar la transacción contra el endpoint oficial antes de confirmar el pago.
* Selector de entorno SANDBOX / PRODUCCIÓN con API Key y URL base configurables
  por entorno (ligado al modo de prueba del proveedor en Odoo).
* Envío opcional del detalle de productos (items) y datos del cliente.
* Soporte de meses sin intereses (``monthlyInstallmentId``).
* Manejo correcto del monto en centavos requerido por CuboPago.
* Confirmación automática del pedido cuando CuboPago aprueba el pago.
* Logs de depuración configurables.

Requisitos
==========

* Odoo 18 (Community o Enterprise).
* Módulos ``payment`` y ``website_sale``.
* Moneda USD.
* Cuenta y API Key de CuboPago (Sandbox y/o Producción) desde Cubo Admin.

Configuración
=============

1. Instala el módulo y abre el proveedor de pago **CuboPago**.
2. Ingresa la API Key y la URL base para Sandbox y/o Producción.
3. Copia la URL de webhook mostrada y pégala en Cubo Admin (sección Developers).
4. Usa "Probar conexión" para validar la API Key.
5. Deja el proveedor en modo prueba para Sandbox o habilítalo para Producción.

Compatibilidad
==============

Por contener código Python, este módulo está pensado para instalaciones
on-premise u Odoo.sh. No es compatible con Odoo Online (SaaS).

Licencia
========

Odoo Proprietary License v1.0 (OPL-1). Consulte el archivo ``LICENSE``.

Soporte
=======

ph03001gnu@yahoo.com
