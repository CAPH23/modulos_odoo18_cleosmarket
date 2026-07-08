# Payment Provider: Cobro contra entrega

Módulo para Odoo 18 Community que agrega el proveedor de pago **Cobro contra entrega**.

## Comportamiento

- El cliente selecciona **Cobro contra entrega** en el checkout.
- La transacción se marca como `pending`.
- El pedido queda confirmado para preparación y envío, pero el pago queda pendiente.
- Se muestra una página de estado indicando que el cliente pagará al recibir el producto.
- Se envía un correo al cliente aclarando que el pedido está confirmado, pendiente de pago y será cobrado al momento de la entrega.

## Flujo operativo recomendado

1. El transportista entrega el pedido y cobra al cliente.
2. El transportista liquida el dinero a la tienda en efectivo o transferencia bancaria.
3. En Odoo, registrar manualmente el pago recibido contra la factura o el pedido correspondiente, según la operación contable configurada.

## Instalación

Copiar la carpeta `payment_cobro_entrega` dentro de un directorio incluido en `addons_path`, actualizar la lista de aplicaciones e instalar el módulo.

## Cambios 18.0.1.0.2

- Evita mensajes duplicados en la vista de estado/portal para transacciones contra entrega.
- Oculta los avisos de pago pendiente cuando las facturas relacionadas ya aparecen como pagadas en Odoo.
- Cambia el mensaje interno de la transacción a español.
- Actualiza el icono del módulo, del proveedor de pago y del método de pago.


## 18.0.1.0.3

- Adjunta automáticamente el ticket de compra en PDF al correo de confirmación de Cobro contra entrega.
- El ticket usa el reporte estándar de pedido de venta de Odoo (`sale.action_report_saleorder`).
- Reutiliza el PDF existente si ya fue generado para evitar duplicados innecesarios.
