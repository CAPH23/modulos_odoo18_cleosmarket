# delivery_pedidosya — PedidosYa Courier API v3 para Odoo 18 CE

Conector de envíos con la flota de PedidosYa. **Fase 1: cliente simulado**
(sin credenciales) con el mismo contrato que la API real.

## Instalación en tu servidor (cleosmarket)

Tu `/etc/odoo18.conf` tiene `addons_path` **vacío**, así que hay que crear un
directorio de addons personalizados y declararlo junto con el de Odoo:

```bash
# 1. Crear directorio y copiar el módulo
sudo mkdir -p /opt/odoo18/custom-addons
sudo cp -r delivery_pedidosya /opt/odoo18/custom-addons/

# 2. Dar permisos al usuario del servicio (verificá cuál es)
grep ^User /etc/systemd/system/odoo18.service
sudo chown -R <usuario_odoo>: /opt/odoo18/custom-addons

# 3. Declarar el addons_path en /etc/odoo18.conf
#    IMPORTANTE: al definirlo hay que incluir también los addons de Odoo,
#    porque al dejar de estar vacío ya no se usa el valor por defecto.
addons_path = /opt/odoo18/odoo/addons,/opt/odoo18/custom-addons

# 4. Reiniciar
sudo systemctl restart odoo18
```

Luego, **primero en la base `cleosmarket.com_pruebas`**:
Modo desarrollador → Apps → *Actualizar lista de aplicaciones* → buscar
"PedidosYa" → Instalar. (Instalará `stock_delivery` automáticamente si falta.)

## Configuración

1. Inventario → Configuración → *Métodos de envío* → Nuevo.
2. Proveedor: **PedidosYa**. Pestaña *PedidosYa* → Modo: **Simulado**.
3. Asignar el "Producto de envío" (se crea uno si no existe).
4. Botón *Publicar* (o marcar disponible en el sitio web) para que aparezca
   en el checkout de cleosmarket.com.
5. Verificar que la dirección del almacén/compañía tenga **calle, ciudad y
   teléfono** (obligatorios para el waypoint PICK_UP).

## Qué se puede probar en modo simulado

- Cotización en el checkout: base + $/km (Haversine si hay coordenadas en los
  contactos — con `base_geolocalize` podés geolocalizarlos; si no, 5 km).
- Al validar la entrega (picking) se "crea" el envío: shipping ID, código de
  confirmación, URL de seguimiento y mensaje en el chatter.
- El estado avanza solo con el tiempo (CONFIRMED → … → COMPLETED en ~10 min):
  botón *Actualizar estado* en la pestaña PedidosYa del picking, o el cron
  cada 10 minutos.
- Cancelación desde el picking (botón estándar de cancelar envío del carrier).

## Fase 2 (cuando PedidosYa entregue credenciales)

- Completar la *URL de autenticación* + ClientID/Secret/Usuario/Contraseña en
  la pestaña PedidosYa y cambiar el modo a **Pruebas (isTest)**. El manejo de
  token (45 min, caché, reintento ante 401, protección contra el bloqueo por
  exceso de solicitudes) ya está implementado en `models/pedidosya_client.py`;
  solo puede requerir ajustar el parseo de la respuesta del endpoint de token
  según la doc que entreguen.
- Webhooks SHIPPING_STATUS: controlador HTTP público + registro vía
  `PUT /v3/webhooks-configuration`. Nota previa: tu `dbfilter = ^cleosmarket.*$`
  matchea 2 bases (producción y pruebas); el webhook necesitará `?db=` en la
  URL o un dbfilter por host para resolver la base sin ambigüedad.
- Validación de cobertura (`/v3/estimates/coverage`) antes de cotizar y
  horarios de flota (`/v3/schedules`) para envíos programados.

## v0.2.0 — Barra de seguimiento en el portal (/my/orders)

- Tarjeta "Seguimiento de tu envío" con 8 etapas (orden tomada → …→ pedido
  finalizado) insertada arriba de todo en la columna derecha del pedido.
  La columna izquierda no se modifica.
- Paleta y estilo homologados con website_sale_confirmation_cleo.
- Cada etapa se convierte en check verde (animación pop) según el estado que
  reporta PedidosYa; la etapa en curso pulsa suavemente.
- Refresco en vivo: JS sondea /my/orders/<id>/pedidosya_status cada 30 s
  (con control de acceso estándar del portal) y actualiza sin recargar.
- Restyle CSS de la sección derecha (tarjeta, encabezados navy, alerta
  amarilla, tabla) sin tocar estructura ni funcionalidades.
- La barra solo aparece en pedidos cuyo método de envío es PedidosYa.

Actualizar con: reemplazar la carpeta del módulo y ejecutar
`Apps → PedidosYa Envíos → Actualizar` (o `-u delivery_pedidosya`).

## v0.3.0 — Fase 2: Webhooks SHIPPING_STATUS

- Endpoint público POST /pedidosya/webhook (validación de authorizationKey en
  header Authorization, comparación en tiempo constante, protección contra
  eventos fuera de orden; CANCELLED registra código y motivo en el chatter).
- La URL incluye ?db=<base> porque el dbfilter del servidor matchea 2 bases.
- Nueva sección "Webhook de estados" en el transportista: URL calculada,
  generador de clave y botón "Registrar webhook" (PUT /v3/webhooks-configuration
  en modo real; en modo simulado solo valida y marca registrado).
- Incluye los ajustes previos: etapa "Repartidor asignado" (9 pasos) y regla
  de visibilidad de la barra basada en las entregas reales.

### Probar sin credenciales (simulando a PedidosYa con curl)
1. En el método de envío → pestaña PedidosYa → "Generar clave" → "Registrar
   webhook". Copiar la clave y la URL.
2. Crear un pedido simulado y validar la entrega; copiar el Shipping ID.
3. Desde cualquier terminal:
   curl -X POST "https://cleosmarket.com/pedidosya/webhook?db=cleosmarket.com_pruebas" \
     -H "Content-Type: application/json" -H "Authorization: LA_CLAVE" \
     -d '{"topic":"SHIPPING_STATUS","id":"SHIPPING_ID","data":{"status":"PICKED_UP"}}'
4. Verificar: estado del picking actualizado + chatter + barra del portal
   (se refresca sola en ≤30 s). Probar también clave errónea (401), un estado
   viejo (ignored/out_of_order) y una cancelación:
   -d '{"topic":"SHIPPING_STATUS","id":"SHIPPING_ID","data":{"status":"CANCELLED","cancelCode":"COURIER_CANCEL","cancelReason":"Sin repartidores disponibles"}}'
