/**
 * Tiqsi web — el contrato con que la web de un módulo habla con su anfitrión (fase 10.2b de la plataforma Qillqa,
 * 2026-10-20). Como en el backend, un módulo no importa nada del anfitrión: usa estos marcadores, y el anfitrión
 * web activo los atiende. Qillqa los conecta con su sesión, su marco, sus diálogos y su paleta; la cáscara mínima
 * (`@qillqa/tiqsi/minimo`), con los suyos, para que el módulo funcione solo.
 *
 *   import { api, Marco, PALETA, confirmar } from '@qillqa/tiqsi'
 */
import { Suspense, createElement, type ComponentType, type ReactNode } from 'react'

/** El error de una petición: el mensaje para la persona, el detalle del servidor (`{codigo, …}`) y el estado HTTP.
 *  Todo anfitrión lanza este (así `e instanceof ErrorApi && e.estado === 409` vale en Qillqa y solo). */
export class ErrorApi extends Error {
  detalle: unknown
  estado: number
  constructor(mensaje: string, detalle: unknown, estado: number) {
    super(mensaje)
    this.name = 'ErrorApi'
    this.detalle = detalle
    this.estado = estado
  }
}

export interface OpcionesConfirmar {
  titulo?: string
  aceptar?: string
  cancelar?: string
  peligro?: boolean
}
/** Pedir un texto corto (el nombre de una lista): lo inicial, si es de varias líneas y la etiqueta del campo. */
export interface OpcionesTexto extends OpcionesConfirmar {
  inicial?: string
  multilinea?: boolean
  etiqueta?: string
}
/** Una opción de la página (los pasos de un trámite): el marco la pinta como pestaña o en su menú. */
export interface OpcionPagina {
  clave: string
  etiqueta: string
  icono?: ReactNode
  activa: boolean
  alPulsar: () => void
  /** Número a la derecha (0 no se muestra). */
  contador?: number
}
export interface PropsMarco {
  /** El módulo que se muestra (Qillqa marca su entrada en el menú). */
  modulo?: string
  /** Lo que se trabaja en la página (una rendición, un proyecto) y la ruta de «atrás». */
  titulo?: ReactNode
  volver?: string
  opciones?: OpcionPagina[]
  fondo?: string
  sinBotonModulo?: boolean
  /** Sin la barra inferior del celular (una conversación a pantalla completa, con su propia caja de escribir). */
  sinBarraInferior?: boolean
  /** Botones propios de la página (junto al título) y sus «⋮» (Gestión documental, Qillqasqa Q6b-2b). */
  acciones?: ReactNode
  accionesFijas?: ReactNode
  /** Quién más está en lo que se trabaja (la presencia del anfitrión que la tiene; sola, nada). */
  equipo?: ReactNode
  /** El botón del módulo flota sobre el contenido sin reservarle sitio (un lienzo a todo el alto). */
  sinReservaFlotante?: boolean
  children?: ReactNode
}
/** Una acción secundaria de la barra del módulo (va en «⋮»). */
export interface AccionSecundaria {
  etiqueta: string
  icono?: ReactNode
  alPulsar: () => void
  deshabilitada?: boolean
}
export interface PropsBarraModulo {
  /** El botón de la acción principal («Nueva rendición»). */
  principal?: ReactNode
  /** Filtros, buscador o navegación que la acompañan. */
  children?: ReactNode
  mas?: (AccionSecundaria | false | null | undefined)[]
  /** Relee la información del módulo (el botón «Actualizar»). */
  alActualizar?: () => void | Promise<unknown>
  mb?: number
}
export interface PropsBotonAyuda {
  titulo: string
  children: ReactNode
  etiqueta?: string
}
export interface PropsVisorPdf {
  /** Ruta de la API que entrega el PDF; vacía = nada que mostrar. */
  ruta: string
  /** Cambiarla obliga a volver a pedirlo. */
  version?: number | string
  nombre?: string
  alto?: number | string
  /** Lo que se muestra si no hay PDF (la ruta responde 404); sin esto, el aviso del anfitrión. */
  vacio?: ReactNode
  /** El PDF se está preparando (una compilación en curso). */
  cargando?: boolean
  /** Los demás archivos del módulo, para la lista del visor completo, y el que se abre primero (Qillqasqa Q6b-2b). */
  archivos?: ArchivoVisor[]
  claveInicial?: string
}
/** Un archivo de la lista del visor completo (como Outlook): su grupo («Documento», «Firmado», «Adjuntos»…), una línea
 *  de datos y cómo obtenerlo (una URL, blob o ruta) y, si se puede, descargarlo. */
export interface ArchivoVisor {
  clave: string
  nombre: string
  grupo: string
  detalle?: string
  obtener: () => Promise<string>
  descargar?: () => void
}
/** El mapa de relaciones de algo («rend:12»): lo da el anfitrión que lo tiene (Qillqa); si no, no se muestra. */
export interface PropsMapaLocal {
  foco: string
  alto?: number
  titulo?: string
}
/** Cómo llenar algo: a mano o pegando lo que responde la IA (con el prompt del formato `tipo`); lo da el anfitrión
 *  que tiene la lectura de lo pegado. Sin él, el módulo abre directamente lo manual. */
export interface PropsElegirEntrada {
  ancla: HTMLElement | null
  alCerrar: () => void
  tipo: string
  alManual: () => void
  alPrompt: () => void
  /** La segunda modalidad de Gestión documental, «Formato Word»; sin esto no se ofrece (Qillqasqa Q6b-2b). */
  alWord?: () => void
  etiquetaManual?: string
  etiquetaPrompt?: string
  ayudaManual?: string
  ayudaPrompt?: string
}
export interface PropsEstadoVacio {
  icono?: ReactNode
  titulo: string
  texto?: ReactNode
  accion?: ReactNode
}

/** Lo que todo anfitrión web da a sus módulos. */
export interface AnfitrionWeb {
  nombre: string
  /** Petición a la API con la sesión; lanza un Error con el mensaje del servidor si falla. */
  api<T>(ruta: string, opciones?: RequestInit): Promise<T>
  /** La ficha de la sesión (para pedir archivos como blob) y el rol de quien la tiene. */
  token(): string | null
  rol(): string
  cerrarSesion(): void
  confirmar(mensaje: string, opciones?: OpcionesConfirmar): Promise<boolean>
  /** Un aviso que se acepta, y un texto que se pide (`null` si se cancela). */
  avisar(mensaje: string, opciones?: OpcionesConfirmar): Promise<void>
  pedirTexto(mensaje: string, opciones?: OpcionesTexto): Promise<string | null>
  /** Subir archivos (FormData) y traerlos: con la sesión; los errores, como `ErrorApi`. */
  subirArchivo<T>(ruta: string, datos: FormData, metodo?: 'POST' | 'PUT'): Promise<T>
  descargarBlob(ruta: string): Promise<Blob>
  /** Guardar un archivo de la API en el equipo (cada anfitrión decide dónde: Qillqa, en la carpeta recordada). */
  descargarArchivo(ruta: string, nombre?: string): Promise<unknown>
  Marco: ComponentType<PropsMarco>
  EstadoVacio: ComponentType<PropsEstadoVacio>
  BarraModulo: ComponentType<PropsBarraModulo>
  BotonAyuda: ComponentType<PropsBotonAyuda>
  VisorPdf: ComponentType<PropsVisorPdf>
  /** Lo que solo algunos anfitriones tienen (el módulo lo APROVECHA: sin ello, esa parte no se muestra). */
  opcionales?: {
    MapaLocal?: ComponentType<PropsMapaLocal>
    ElegirEntrada?: ComponentType<PropsElegirEntrada>
    /** Algo cambió sus vínculos (`foco`: «rend:12»): el anfitrión refresca lo que los muestra. */
    relacionesCambiaron?: (foco: string) => void
  }
  /** Servicios del anfitrión por nombre, como las capacidades del backend («personas.buscar», «sinconexion.encolar»…):
   *  el módulo los APROVECHA con `servicio(nombre)`; sin ellos, esa ayuda no aparece. */
  servicios?: Record<string, (...args: any[]) => any>
  /** Piezas de pantalla del anfitrión o de otros módulos, por nombre («personas.Avatar», «tareas.DialogoTarea»): el
   *  módulo las pinta con `<Pieza pieza=… />` y pregunta `hayPieza(nombre)`; sin ellas, esa parte no se ofrece. */
  piezas?: Record<string, ComponentType<any>>
  /** Los colores del tema (los mismos nombres en todo anfitrión: fondo, superficie, texto, acento…). */
  paleta: Record<string, string>
  /** Si el tema es claro u oscuro (para lo que un módulo pinta con sus propios colores); claro si no lo dice. */
  modo?: 'claro' | 'oscuro'
  /** Un almacén local para lo que el navegador no deja guardar en texto (la carpeta de una copia local). */
  almacen: {
    guardarHandle(h: FileSystemDirectoryHandle, clave?: string): Promise<void>
    leerHandle(clave?: string): Promise<FileSystemDirectoryHandle | null>
    olvidarHandle(clave?: string): Promise<void>
  }
}

let activo: AnfitrionWeb | null = null

/** El anfitrión de esta página pasa a atender los marcadores. Se llama una vez, antes de pintar. */
export function activarAnfitrionWeb(anfitrion: AnfitrionWeb): void {
  activo = anfitrion
}

export function anfitrionWeb(): AnfitrionWeb {
  if (!activo) throw new Error('Tiqsi web: no hay anfitrión activo (activarAnfitrionWeb antes de pintar el módulo).')
  return activo
}

// --- los marcadores que usa un módulo ------------------------------------------------------------------
export const api = <T,>(ruta: string, opciones?: RequestInit): Promise<T> => anfitrionWeb().api<T>(ruta, opciones)
export const token = (): string | null => anfitrionWeb().token()
export const rol = (): string => anfitrionWeb().rol()
export const cerrarSesion = (): void => anfitrionWeb().cerrarSesion()
export const confirmar = (mensaje: string, opciones?: OpcionesConfirmar): Promise<boolean> =>
  anfitrionWeb().confirmar(mensaje, opciones)
export const avisar = (mensaje: string, opciones?: OpcionesConfirmar): Promise<void> => anfitrionWeb().avisar(mensaje, opciones)
export const pedirTexto = (mensaje: string, opciones?: OpcionesTexto): Promise<string | null> =>
  anfitrionWeb().pedirTexto(mensaje, opciones)
export const modo = (): 'claro' | 'oscuro' => anfitrionWeb().modo ?? 'claro'
/** Un servicio del anfitrión, o `undefined` si este no lo tiene (Qillqa los tiene; la cáscara mínima, no). */
export const servicio = <F extends (...args: any[]) => any>(nombre: string): F | undefined =>
  anfitrionWeb().servicios?.[nombre] as F | undefined
/** ¿El error es que no hubo servidor (sin red, o el proxy sin API detrás) y no una respuesta suya? */
export function esSinServidor(error: unknown): boolean {
  if (!(error instanceof ErrorApi)) return true
  const codigo = (error.detalle as { codigo?: string } | undefined)?.codigo
  return codigo === 'sin_conexion' || codigo === 'sin_servidor' || error.estado === 502 || error.estado === 503 || error.estado === 504
}
export const subirArchivo = <T,>(ruta: string, datos: FormData, metodo?: 'POST' | 'PUT'): Promise<T> =>
  anfitrionWeb().subirArchivo<T>(ruta, datos, metodo)
export const descargarBlob = (ruta: string): Promise<Blob> => anfitrionWeb().descargarBlob(ruta)
export const descargarArchivo = (ruta: string, nombre?: string): Promise<unknown> => anfitrionWeb().descargarArchivo(ruta, nombre)
export const avisarRelaciones = (foco: string): void => anfitrionWeb().opcionales?.relacionesCambiaron?.(foco)
export const guardarHandle = (h: FileSystemDirectoryHandle, clave?: string) => anfitrionWeb().almacen.guardarHandle(h, clave)
export const leerHandle = (clave?: string) => anfitrionWeb().almacen.leerHandle(clave)
export const olvidarHandle = (clave?: string) => anfitrionWeb().almacen.olvidarHandle(clave)

/** Los colores del anfitrión activo, leídos al usarlos (`PALETA.fondo`). */
export const PALETA: Record<string, string> = new Proxy({} as Record<string, string>, {
  get: (_t, clave) => (typeof clave === 'string' ? anfitrionWeb().paleta[clave] : undefined),
})

export function Marco(props: PropsMarco) {
  return createElement(anfitrionWeb().Marco, props)
}

export function EstadoVacio(props: PropsEstadoVacio) {
  return createElement(anfitrionWeb().EstadoVacio, props)
}

/** Las piezas del anfitrión pueden llegar diferidas (`lazy`): se esperan sin tapar la página. */
const diferido = <P,>(C: ComponentType<P> | undefined, props: P) =>
  C ? createElement(Suspense, { fallback: null }, createElement(C as ComponentType<any>, props as any)) : null

export function BarraModulo(props: PropsBarraModulo) {
  return diferido(anfitrionWeb().BarraModulo, props)
}

export function BotonAyuda(props: PropsBotonAyuda) {
  return diferido(anfitrionWeb().BotonAyuda, props)
}

export function VisorPdf(props: PropsVisorPdf) {
  return diferido(anfitrionWeb().VisorPdf, props)
}

/** ¿El anfitrión tiene este opcional? (para ofrecer, o no, lo que depende de él). */
export const hay = (nombre: 'MapaLocal' | 'ElegirEntrada'): boolean => Boolean(anfitrionWeb().opcionales?.[nombre])

/** ¿El anfitrión tiene esta pieza? (para ofrecer, o no, lo que depende de ella). */
export const hayPieza = (nombre: string): boolean => Boolean(anfitrionWeb().piezas?.[nombre])

/** Una pieza del anfitrión por nombre, con sus props. `respaldo`: lo que se pinta mientras llega y si el anfitrión no
 *  la tiene (sin él, nada). */
export function Pieza({ pieza, respaldo = null, ...props }: { pieza: string; respaldo?: ReactNode } & Record<string, any>) {
  const C = anfitrionWeb().piezas?.[pieza]
  return C ? createElement(Suspense, { fallback: respaldo }, createElement(C as ComponentType<any>, props)) : respaldo
}

export function MapaLocal(props: PropsMapaLocal) {
  return diferido(anfitrionWeb().opcionales?.MapaLocal, props)
}

export function ElegirEntrada(props: PropsElegirEntrada) {
  return diferido(anfitrionWeb().opcionales?.ElegirEntrada, props)
}

// --- el módulo web ---------------------------------------------------------------------------------------
/** Una opción del menú de un módulo: un lugar (o una acción) con dirección propia. */
export interface OpcionMenu {
  etiqueta: string
  /** Ruta interna, con su consulta si la lleva («/fototeca?ver=favoritas»). */
  ruta: string
  icono: ComponentType<any>
  ayuda?: string
  /** Una acción (crear, subir) se pinta distinto de un lugar. */
  accion?: boolean
  soloAdmin?: boolean
}

/** Lo que la web de un módulo declara: su pantalla, dónde va y cómo entra al menú del anfitrión. El nombre, en
 *  castellano y por su función (el nombre del proyecto no se muestra en la plataforma). */
export interface ModuloWeb {
  id: string
  nombre: string
  ruta: string
  /** La pantalla, cargada cuando se abre: cada anfitrión la envuelve a su manera (reintentos, espera). */
  cargar: () => Promise<{ default: ComponentType<any> }>
  /** Nombre corto (la barra inferior del celular). */
  corto?: string
  icono?: ComponentType<any>
  descripcion?: string
  opciones?: OpcionMenu[]
  /** Sus otras pantallas, cada una con su ruta (el detalle: «/rendiciones/:id»); las monta el anfitrión igual. */
  pantallas?: { ruta: string; cargar: () => Promise<{ default: ComponentType<any> }> }[]
  /** Sus pantallas PÚBLICAS, sin sesión ni marco (la mesa de partes virtual: quien envía no tiene cuenta). El
   *  anfitrión las monta fuera del inicio de sesión; la ruta puede terminar en «/*». */
  publicas?: { ruta: string; cargar: () => Promise<{ default: ComponentType<any> }> }[]
  /** Solo estos roles lo ven (sin la lista, todos). */
  roles?: string[]
  soloAdmin?: boolean
}

export const definirModuloWeb = (m: ModuloWeb): ModuloWeb => m
