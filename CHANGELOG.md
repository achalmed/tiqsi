---
tipo: changelog
estado: activo
---
# CHANGELOG — tiqsi

## [Unreleased]

### Añadido

- **El exportador de demos y lo de terceros** (2026-10-21, para la demo de Qillqa): `TERCEROS` en `demo.conf` (globs)
  marca las bibliotecas incluidas tal cual: en ellas no cuentan los correos, IP ni teléfonos de sus autores; lo privado y
  los tokens sí. Prueba en `tests/test_demo.py`.
- **Cáscara mínima con varios módulos** (2026-10-21, para Qillqasqa Q6b-4): `CascaronMinimo` acepta `modulos` (y su
  `nombre`) además de `modulo`: los monta todos, cada uno en su ruta y con sus pantallas, con una barra para pasar de
  uno a otro siempre visible (cada página trae sus propias pestañas); lo que no casa con ninguna ruta abre el primero.
  Con un solo módulo, igual que antes. `anfitrionMinimo(nombre, menu, secciones)`.
- **Tiqsi web, el lenguaje visual común** (2026-10-21, para Qillqasqa Q6b-2c): `@qillqa/tiqsi/estilo`, una entrada aparte
  (el contrato no arrastra MUI al arranque del anfitrión) con las piezas puras que todos dibujan igual, con o sin
  anfitrión: `Titulo` (tres niveles), `Bloque`, `EstadoPieza`, `BotonActualizar`, `HojaInferior` (con `PAPEL_HOJA`,
  `Asa` y `Circulo`) y `pdfEnLinea`. Venían de Qillqa, que ahora las reexporta. Solo usa las piezas básicas de MUI: el
  servidor de desarrollo del anfitrión no preempaqueta lo que importa un paquete enlazado (y no vigila sus cambios:
  tras editar Tiqsi web, reiniciar el `vite` del anfitrión).
- **Tiqsi web, el marco y el visor de un módulo con documento** (2026-10-21, para Qillqasqa Q6b-2b): `PropsMarco` suma
  `acciones` y `accionesFijas` (los botones de la página junto al título, que la cáscara mínima pinta en su cabecera),
  `equipo` (la presencia, si el anfitrión la tiene) y `sinReservaFlotante`; `PropsVisorPdf`, `cargando` y la lista del
  visor completo (`archivos`, `claveInicial`, tipo `ArchivoVisor`); `PropsElegirEntrada.alWord`, la modalidad «Formato
  Word». Todo opcional: los módulos que ya los usaban no cambian.
- **El exportador de demos común** (2026-10-21, `tiqsi/demo.py`): venía de Qillqa (`scripts/exportar_demo.py`), que ahora
  es su receta. Arma el árbol desde un commit (o la copia de trabajo), quita lo excluido, pone lo propio de la demo,
  aplica las sustituciones genéricas y las del mapa privado, corre los ganchos del proyecto, escanea (un hallazgo y no
  sale nada; los términos privados nunca se imprimen), compromete en una rama huérfana y, al publicar, re-escanea,
  exige que no comparta historia con main e instala la guarda pre-push. Pruebas en `tests/test_demo.py` (repositorio
  y remoto temporales).
- **`Superficie`, la capacidad con lista explícita** (2026-10-21, para Qillqasqa Q3): `tiqsi.Superficie(nombre,
  funciones, donde)` ofrece solo las funciones declaradas, cada una resuelta al usarla (una prueba con monkeypatch ve
  la de hoy); lo demás da AttributeError con el nombre de la capacidad y dónde vive. Venía de Qillqa
  (`servicios/contratos_plataforma.py`), que ahora la toma de aquí: así un módulo ofrece su contrato sin importar al
  anfitrión. Prueba en `tests/test_contrato.py`.
- **Cáscara mínima: el contenido es una columna** (2026-10-20, para el Observatorio, Qhawana Q2): el `main` del marco
  mínimo es una columna flexible, como el de Qillqa; una pantalla con `flex: 1` (el marco del Observatorio) llena la
  ventana en lugar de quedar con el alto de su contenido.
- **Tiqsi web, pantallas públicas** (2026-10-20, para la Mesa de Partes, Punku P4): `ModuloWeb.publicas` declara las
  pantallas sin sesión ni marco (la mesa de partes virtual: quien envía no tiene cuenta); el anfitrión las monta fuera
  del inicio de sesión y la cáscara mínima, antes de pedir entrar. `PropsVisorPdf.vacio`: lo que se muestra si no hay
  PDF.
- **Nombres y páginas de archivo comunes** (2026-10-20, para la Mesa de Partes, Punku P1c): `tiqsi.nombres` suma
  `unico_en` (el mismo nombre si está libre; si no, «…-2», «…-3») y `LIMITE` (100, el largo máximo con la
  extensión), y `tiqsi.pdf.contar_paginas` (con `pdfinfo` o, sin él, por el árbol de páginas; None antes que un
  número incorrecto). Venían de Qillqa (`servicios/nombres.py`, `servicios/pdf.py`), que ahora los toma de aquí: una
  sola convención. Pruebas en `tests/test_archivos.py`.
- **Tiqsi web, piezas del anfitrión** (2026-10-20, para el chat, Rimay R4): `AnfitrionWeb.piezas` y `<Pieza pieza=…
  respaldo=… />` (lo que se pinta mientras llega y si el anfitrión no la tiene) con `hayPieza(nombre)`: el avatar con
  foto, la invitación a los avisos push o los diálogos de otro módulo (Tareas y Agenda) llegan por nombre, y solo el
  módulo no los ofrece. El marco acepta `sinBarraInferior` (una conversación a pantalla completa en el celular).
- **Separar una tabla que se apunta a sí misma** (2026-10-20, Rimay R3): `tiqsi.sql.separar` copia en orden de clave
  primaria y, si la tabla tiene una clave foránea hacia sí misma (`canales.padre_id`, `mensajes.padre_id`), esas
  columnas entran vacías y se ponen al final: antes, una fila hija que llegaba antes que su padre rompía la copia.
- **«identidad.v1».de_ficha** en el anfitrión mínimo (2026-10-20, Rimay R3): la cuenta de una ficha de sesión sin
  cabeceras (un WebSocket la manda en la dirección); None si no vale.
- **Difusión en vivo** (2026-10-20, para el chat, Rimay R2): `tiqsi.en_vivo` (venía de Qillqa, `servicios/difusor.py`):
  cada pestaña conectada a un WebSocket se suscribe con su cuenta y recibe lo que se publica para ella; sabe qué
  conversación mira y si la aplicación está a la vista (para decidir entre sonido y aviso push). En el proceso, sin
  colas externas; lo comparten todos los módulos. Pruebas en `tests/test_en_vivo.py`.
- **Tiqsi web, tercera pieza** (2026-10-20, para Tareas y Agenda): `avisar` y `pedirTexto` (como `confirmar`),
  `modo()` (claro u oscuro, para los colores propios de un módulo), `esSinServidor` (venía de Qillqa) y los
  **servicios** del anfitrión por nombre, como las capacidades del backend: `servicio('personas.buscar')` devuelve la
  función o `undefined`, y el módulo ofrece esa ayuda solo si está. La cáscara mínima atiende avisos y textos, y sin
  opciones de página muestra el **menú del módulo** de su manifiesto (lo de administración, solo al administrador);
  su paleta neutra suma `bordeFuerte`, `dorado`, `enRevision`, `exitoFondo` y `velo`.
- **Tiqsi web, segunda pieza** (2026-10-20, para Rendición de cuentas): `ErrorApi` (la misma clase en todo anfitrión),
  subir y descargar archivos, `Marco` con título, «atrás» y opciones de página, `BarraModulo`, `BotonAyuda`, `VisorPdf`
  y los opcionales `MapaLocal`, `ElegirEntrada` y `avisarRelaciones` (con `hay()`); el manifiesto web declara sus
  `pantallas` (el detalle «/rendiciones/:id»). La cáscara mínima los atiende todos, con un tema neutro, una barra que
  no se parte en el celular y sus otras pantallas; el anfitrión mínimo devuelve la página en un enlace directo.
- **La base propia de un módulo** (2026-10-20): `tiqsi.sql.crear_base_si_falta` (venía de la Mediateca) y
  `tiqsi.sql.separar` (sus tablas de la base del anfitrión a la suya: simula, copia con sus ids y secuencias,
  verifica filas y huella por tabla; nunca toca el origen ni mezcla con un destino con datos). Pruebas en
  `tests/test_sql.py`. El anfitrión mínimo da también `cuenta` y `cuentas` en «identidad.v1» (la ficha de Qillqa)
  y las cuentas guardan `nombres` y `dni`.
- **Nombres de archivo** (2026-10-20): `tiqsi.nombres.sanear`, la convención de toda la plataforma, que venía de
  Qillqa (`servicios/nombres.py` la reexporta): los módulos aislados (Rendición) nombran sus archivos igual sin
  importar a Qillqa.
- **Bandeja de salida durable** (2026-10-20): `tiqsi.bandeja` (`Bandeja`, `BandejaEnMemoria`, `Repartidor`) y
  `tiqsi.bandeja_sql` (una tabla en la base del módulo; el evento entra en la misma transacción que el cambio). El
  manifiesto declara `bandeja=` y el anfitrión la reparte al bus en `arrancar()`. Entrega «al menos una vez»:
  `Evento.id` estable («modulo:n») para que el manejador no repita; `Bus.entregar` devuelve los fallos y el
  repartidor reintenta hasta `max_intentos`. Pruebas en `tests/test_bandeja.py`.
- **Contrato 0.1** (2026-10-20, fase 10.2 de la plataforma Qillqa): manifiesto, capacidades, bus de eventos en
  proceso, referencias «modulo:tipo:id», anfitrión que valida, conecta, monta en orden y arranca tareas, y
  compatibilidad de versiones. Pruebas en `tests/test_contrato.py`.
- **El módulo pide al anfitrión activo** (2026-10-20): `Anfitrion.activar()` y `tiqsi.modulo` (`capacidad`, `opcional`,
  `hay`, `publicar`, `resolver`): un módulo usa capacidades, eventos y referencias sin importar a quien las ofrece.
- **Puertos de identidad y kit web** (2026-10-20): `tiqsi.puertos` (marcadores `usuario_actual` y `solo_administrador`
  que el anfitrión conecta con `dependencias=`; sin anfitrión, 503) y `tiqsi.web.enviar_archivo` (caché `private,
  no-cache`, 304 y tramos 206), que venía de Qillqa.
- **Anfitrión mínimo** (2026-10-20): `tiqsi.minimo.crear_app` monta un módulo solo, con cuentas locales (scrypt, archivo
  600), inicio de sesión en `/api/auth/login` (fichas HMAC), la identidad conectada a los marcadores y «identidad.v1»;
  `python -m tiqsi.minimo cuenta` crea cuentas.
- **Tiqsi web** (2026-10-20): el paquete `@qillqa/tiqsi` (`web/`): el contrato `AnfitrionWeb` y los marcadores que usa la
  web de un módulo (`api`, `token`, `rol`, `cerrarSesion`, `confirmar`, `Marco`, `EstadoVacio`, `PALETA`, almacén local),
  `definirModuloWeb`, y la cáscara mínima (`@qillqa/tiqsi/minimo`: inicio de sesión, marco sencillo, paleta neutra);
  `crear_app(web=…)` sirve la página del módulo.
- **El menú desde el manifiesto web** (2026-10-20): `ModuloWeb` suma su entrada de menú (`corto`, `icono`, `descripcion`,
  `opciones`, `roles`, `soloAdmin`) y cambia `Pantalla` por `cargar` (cada anfitrión envuelve la carga a su manera).
