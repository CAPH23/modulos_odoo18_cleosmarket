# Changelog

## 18.0.1.1.0 — 2026-07-22

- El checkout muestra la lista completa de couriers que Boxful devuelve para la dirección del
  cliente (checkbox de selección, logo, fechas de recolección/entrega, peso máximo y tipo de
  entrega), en vez de un único courier autoseleccionado.
- Nueva clasificación por transportista (`goboxful.courier`, pestaña Boxful del método de
  envío): cada courier se autorregistra como "Mismo día" la primera vez que se cotiza y puede
  reclasificarse como "Entrega programada" (día siguiente o posterior).
- `goboxful_same_day_only` ahora filtra según esa clasificación manual en vez de una llamada
  extra a `/quoter`.
- Nuevo campo `sale.order.goboxful_selected_courier_id`: recuerda el courier elegido por el
  cliente y se usa al recotizar, en vez de forzar siempre la opción más barata/rápida.
- La clasificación "Mismo día" ahora también valida que la fecha de recolección y la fecha
  estimada de entrega caigan en el mismo día calendario; si Boxful cotiza un courier
  clasificado como "Mismo día" pero con fechas en días distintos, se trata como "Entrega
  programada" (afecta tanto la etiqueta mostrada como el filtro `goboxful_same_day_only`).
- Se quitó el dato "Tipo de entrega" de la tarjeta de courier en el checkout; la sección de
  couriers ahora ocupa casi todo el ancho de la tarjeta de método de envío.
- El ícono de la tarjeta de método de envío usa el logo real de Boxful (vendorizado en
  `static/src/img/goboxful_logo.svg`) en vez del ícono genérico de camión.
- Corregido: cambiar "Solo couriers del mismo día" o reclasificar un courier no invalidaba una
  cotización ya cacheada (`_goboxful_build_quote_hash` ahora incluye esa configuración).
- Corregida la alineación de las tarjetas de courier en `/shop/checkout`: antes quedaban
  encajonadas dentro de la columna de título/descripción de la tarjeta Boxful (sin llegar al
  borde derecho); ahora ocupan su propia fila del grid, alineadas desde el título hasta el
  precio, en las 3 variantes responsive de la tarjeta.
- Cada sub-tarjeta de courier ahora muestra también el nombre del courier.
- Las fechas de recolección/entrega se muestran como día/mes/año, sin hora.
- Peso máximo y costo del envío se unieron a la misma línea de recolección/entrega en cada
  sub-tarjeta de courier.

## 18.0.1.0.0 — 2026-07-19

- Primera versión.
- Configuración multiempresa.
- JWT v2 y refresh rotativo.
- Ubicaciones, cotización same-day, guía, etiqueta, tracking y webhook.
- Integración con `cleo_cod`.
- Portal y bloqueo de productos congelados.
- Modo simulado y controles para pruebas.
- Etiqueta PDF simulada, logs navegables y payloads desactivados por defecto.
- Compatibilidad con el Distrito de Cleos Market sin instalar `base_address_city`.
