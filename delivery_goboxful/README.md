# delivery_goboxful

Conector Boxful para Odoo 18 Community, preparado para la instalación de Cleos Market.

## Funciones

- Una cuenta y dirección de recolección Boxful por compañía.
- Autenticación JWT v2 con renovación rotativa protegida para instalaciones multiworker.
- Sincronización de departamentos y ciudades Boxful.
- Mapeo de la ciudad Boxful contra el campo `state_id` usado como Municipio en Cleos Market,
  sin instalar `base_address_city` ni cambiar el campo de Distrito existente.
- Lista completa de couriers Boxful en el checkout, con checkbox de selección, logo, fechas de
  recolección/entrega y peso máximo; el cliente puede elegir cualquiera, con el mejor según el
  criterio configurado preseleccionado.
- Clasificación de couriers por transportista (`goboxful.courier`), autorregistrada al cotizar;
  "Mismo día" también exige que recolección y entrega estimada caigan en el mismo día calendario.
- Cambio manual del courier desde el checkout o desde la transferencia.
- Creación manual de la guía con `POST /shipment`.
- Cobro contra entrega para transacciones del proveedor `cleo_cod`, usando el total del pedido.
- Una caja por pedido, con peso, volumen, dimensiones y fragilidad.
- Ocultamiento completo de Boxful cuando una categoría bloqueada participa en el carrito.
- Descarga y adjunto de etiqueta PDF con validación del host.
- Webhook autenticado, eventos idempotentes y protección ante estados fuera de orden.
- Consulta programada de estados como respaldo.
- Barra dinámica de seguimiento en `/my/orders`.
- Actividades para un usuario interno responsable de incidencias.
- Modo simulado sin tráfico externo.
- Etiqueta PDF simulada para comprobar adjunto, chatter y apertura antes de usar la API real.

## Compatibilidad objetivo

- Odoo Community 18.0.
- Revisión analizada: `02145783a5c97f939e1bfcb428ee950f7dd7be03`.
- Python 3.12.
- `product.weight_in_lbs = 1`.
- `product.volume_in_cubic_feet = 0`.
- `payment_cobro_entrega`, código de proveedor `cleo_cod`.
- `Sitio_web_cleosmarket` y su flujo personalizado de checkout.
- `delivery_pedidosya` puede permanecer instalado y publicado simultáneamente.

## Seguridad de los modos

- **Simulado:** no realiza llamadas externas.
- **Pruebas:** usa la URL configurada, pero bloquea `POST /shipment` hasta activar expresamente la autorización.
- **Producción:** crea guías reales.

Lea `INSTALL.md`, `CONFIGURE.md` y `SECURITY.md` antes de habilitar producción.
