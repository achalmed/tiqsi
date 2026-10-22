/**
 * La cáscara MÍNIMA: la web de un módulo funcionando sola, sin Qillqa (fase 10.2b de la plataforma, 2026-10-20).
 * Habla con el anfitrión mínimo del backend (`tiqsi.minimo`): inicio de sesión en /api/auth/login y la ficha en
 * cada petición. Da a su módulo todo lo de `AnfitrionWeb`: petición con sesión, subir y bajar archivos, un marco
 * sencillo con el nombre del módulo, su título, «atrás», sus opciones de página (o, sin ellas, el menú del módulo de
 * su manifiesto) y «Salir», la barra del módulo, la
 * ayuda, el visor de PDF, confirmaciones, avisos, pedir un texto, estado vacío, una paleta neutra y el almacén
 * local. Los opcionales (el mapa de relaciones, elegir cómo llenar con la IA) y los servicios (buscar personas, la
 * cola sin conexión…) no están: el módulo funciona sin ellos.
 *
 *   createRoot(raiz).render(<CascaronMinimo modulo={MEDIATECA} />)
 */
import { Suspense, lazy, useEffect, useMemo, useState, type FormEvent } from 'react'
import { BrowserRouter, Link, Route, Routes, useLocation } from 'react-router'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import CircularProgress from '@mui/material/CircularProgress'
import CssBaseline from '@mui/material/CssBaseline'
import Dialog from '@mui/material/Dialog'
import DialogContent from '@mui/material/DialogContent'
import DialogTitle from '@mui/material/DialogTitle'
import Menu from '@mui/material/Menu'
import MenuItem from '@mui/material/MenuItem'
import TextField from '@mui/material/TextField'
import Typography from '@mui/material/Typography'
import useMediaQuery from '@mui/material/useMediaQuery'
import { ThemeProvider, createTheme } from '@mui/material/styles'

import {
  ErrorApi, activarAnfitrionWeb, type AnfitrionWeb, type AccionSecundaria, type ModuloWeb, type OpcionMenu, type PropsBarraModulo,
  type PropsBotonAyuda, type PropsEstadoVacio, type PropsMarco, type PropsVisorPdf,
} from './index'

const CLAVE_FICHA = 'tiqsi_token'
const CLAVE_ROL = 'tiqsi_rol'
const CLAVE_NOMBRE = 'tiqsi_nombre'

/** Colores neutros, con los nombres que comparten todos los anfitriones. */
export const PALETA_NEUTRA: Record<string, string> = {
  fondo: '#F5F5F7', superficie: '#FFFFFF', superficieMedia: '#EFEFF1', borde: '#E5E5EA',
  texto: '#1D1D1F', textoSecundario: '#515154', textoTenue: '#86868B', acento: '#0A6BDB',
  guinda: '#1D1D1F', guindaSuave: 'rgba(29, 29, 31, 0.06)', sobrePrimario: '#FFFFFF', oscuroVisor: '#1D1D1F',
  barra: 'rgba(255, 255, 255, 0.92)', aviso: '#9A7A3C', error: '#B5484D', exito: '#4F8A5B',
  sombra: '0 1px 2px rgba(0, 0, 0, 0.04), 0 4px 16px rgba(0, 0, 0, 0.06)',
  superficieTenue: '#FAFAFA', apagado: '#AEAEB2', info: '#5B7DB1', avisoOscuro: '#7C5F2A',
  avisoFondo: 'rgba(154, 122, 60, 0.09)', exitoFondo: 'rgba(79, 138, 91, 0.09)', bordeFuerte: '#D1D1D6',
  velo: 'rgba(29, 29, 31, 0.04)', dorado: '#9A7A3C', enRevision: '#5B7DB1',
  // Los estados de un trámite (borrador → observado → aprobado → firmado → enviado).
  borrador: '#86868B', observado: '#9A7A3C', aprobado: '#4F8A8B', firmado: '#4A5C7A', enviado: '#4F8A5B',
}

/** El tema de la cáscara: neutro, con la tinta como color principal y los botones sin mayúsculas (como Qillqa). */
const TEMA = createTheme({
  palette: {
    primary: { main: PALETA_NEUTRA.texto, contrastText: PALETA_NEUTRA.sobrePrimario },
    background: { default: PALETA_NEUTRA.fondo, paper: PALETA_NEUTRA.superficie },
    text: { primary: PALETA_NEUTRA.texto, secondary: PALETA_NEUTRA.textoSecundario },
    divider: PALETA_NEUTRA.borde,
    error: { main: PALETA_NEUTRA.error }, success: { main: PALETA_NEUTRA.exito }, warning: { main: PALETA_NEUTRA.aviso },
  },
  shape: { borderRadius: 10 },
  typography: {
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
    button: { textTransform: 'none', fontWeight: 600 },
  },
})

// --- el almacén local (IndexedDB): lo que el navegador no deja guardar como texto ------------------------
const BASE = 'tiqsi-almacen'
function abrir(): Promise<IDBDatabase> {
  return new Promise((res, rej) => {
    const p = indexedDB.open(BASE, 1)
    p.onupgradeneeded = () => p.result.createObjectStore('handles')
    p.onsuccess = () => res(p.result)
    p.onerror = () => rej(p.error)
  })
}
async function operar<T>(modo: IDBTransactionMode, hacer: (s: IDBObjectStore) => IDBRequest): Promise<T> {
  const db = await abrir()
  try {
    return await new Promise<T>((res, rej) => {
      const peticion = hacer(db.transaction('handles', modo).objectStore('handles'))
      peticion.onsuccess = () => res(peticion.result as T)
      peticion.onerror = () => rej(peticion.error)
    })
  } finally {
    db.close()
  }
}

function salir(): void {
  for (const k of [CLAVE_FICHA, CLAVE_ROL, CLAVE_NOMBRE]) localStorage.removeItem(k)
  window.location.reload()
}

const conFicha = (): Record<string, string> => {
  const ficha = localStorage.getItem(CLAVE_FICHA)
  return ficha ? { Authorization: `Bearer ${ficha}` } : {}
}

/** Una respuesta que no es 2xx → `ErrorApi` con el mensaje del servidor (o el primero de sus errores). */
async function fallo(r: Response): Promise<never> {
  if (r.status === 401 && localStorage.getItem(CLAVE_FICHA)) salir()
  const cuerpo = await r.json().catch(() => null)
  const detalle = cuerpo?.detail
  const mensaje = typeof detalle === 'string' ? detalle
    : detalle?.mensaje ?? detalle?.errores?.[0] ?? (Array.isArray(detalle) ? detalle[0]?.msg : undefined) ?? `Error ${r.status}`
  throw new ErrorApi(String(mensaje), detalle, r.status)
}

async function pedir<T>(ruta: string, opciones: RequestInit = {}): Promise<T> {
  const cabeceras: Record<string, string> = conFicha()
  if (!(opciones.body instanceof FormData)) cabeceras['Content-Type'] = 'application/json'
  const r = await fetch(ruta, { ...opciones, headers: { ...cabeceras, ...(opciones.headers as Record<string, string>) } })
  if (!r.ok) await fallo(r)
  if (r.status === 204) return undefined as T
  return ((r.headers.get('content-type') ?? '').includes('json') ? r.json() : r.text()) as Promise<T>
}

async function subir<T>(ruta: string, datos: FormData, metodo: 'POST' | 'PUT' = 'POST'): Promise<T> {
  const r = await fetch(ruta, { method: metodo, headers: conFicha(), body: datos })
  if (!r.ok) await fallo(r)
  return ((r.headers.get('content-type') ?? '').includes('json') ? r.json() : r.text()) as Promise<T>
}

async function blob(ruta: string): Promise<Blob> {
  const r = await fetch(ruta, { headers: conFicha(), cache: 'no-store' })
  if (!r.ok) await fallo(r)
  return r.blob()
}

/** Guarda en la carpeta de descargas del navegador, con el nombre del servidor si no se da uno. */
async function descargar(ruta: string, nombre = ''): Promise<string> {
  const r = await fetch(ruta, { headers: conFicha(), cache: 'no-store' })
  if (!r.ok) await fallo(r)
  const delServidor = /filename\*?=(?:UTF-8'')?"?([^";]+)"?/i.exec(r.headers.get('content-disposition') ?? '')?.[1]
  const final = nombre || (delServidor ? decodeURIComponent(delServidor) : ruta.split('/').pop() ?? 'archivo')
  const url = URL.createObjectURL(await r.blob())
  const a = Object.assign(document.createElement('a'), { href: url, download: final })
  a.click()
  setTimeout(() => URL.revokeObjectURL(url), 30_000)
  return final
}

/** El menú del módulo (sus `opciones` del manifiesto), cuando la página no trae las suyas: lo que en Qillqa da su
 *  barra de módulo. Lo de administración, solo al administrador. */
function MenuDelModulo({ menu }: { menu: OpcionMenu[] }) {
  const lugar = useLocation()
  const aqui = lugar.pathname + lugar.search
  const visibles = menu.filter((o) => !o.soloAdmin || localStorage.getItem(CLAVE_ROL) === 'administrador')
  if (visibles.length === 0) return null
  return (
    <Box component="nav" sx={{ display: 'flex', gap: 0.5, px: 1.5, py: 0.75, overflowX: 'auto', bgcolor: PALETA_NEUTRA.barra,
      borderBottom: `1px solid ${PALETA_NEUTRA.borde}` }}>
      {visibles.map((o) => {
        const Icono = o.icono
        return (
          <Button key={o.ruta} component={Link} to={o.ruta} size="small" startIcon={<Icono fontSize="small" />}
            variant={aqui === o.ruta ? 'contained' : 'text'} disableElevation sx={{ flexShrink: 0, textTransform: 'none' }}>
            {o.etiqueta}
          </Button>
        )
      })}
    </Box>
  )
}

/** Los módulos de un proyecto que trae varios (Qillqasqa: Gestión documental, Proyectos de ley y la Semana): una barra
 *  para pasar de uno a otro, siempre visible (cada página trae sus propias pestañas). */
function SeccionesDelProyecto({ secciones }: { secciones: OpcionMenu[] }) {
  const lugar = useLocation()
  return (
    <Box component="nav" aria-label="Módulos" sx={{ display: 'flex', gap: 0.5, px: 1.5, py: 0.5, overflowX: 'auto',
      bgcolor: PALETA_NEUTRA.superficieMedia, borderBottom: `1px solid ${PALETA_NEUTRA.borde}` }}>
      {secciones.map((s) => {
        const Icono = s.icono
        const aqui = lugar.pathname === s.ruta || lugar.pathname.startsWith(`${s.ruta}/`)
        return (
          <Button key={s.ruta} component={Link} to={s.ruta} size="small" startIcon={<Icono fontSize="small" />}
            variant={aqui ? 'contained' : 'text'} disableElevation sx={{ flexShrink: 0, textTransform: 'none' }}>
            {s.etiqueta}
          </Button>
        )
      })}
    </Box>
  )
}

function MarcoMinimo({ fondo, children, nombre, titulo, volver, opciones, menu, secciones, acciones, accionesFijas }: PropsMarco & { nombre: string; menu: OpcionMenu[]; secciones: OpcionMenu[] }) {
  return (
    <Box sx={{ minHeight: '100dvh', bgcolor: fondo ?? PALETA_NEUTRA.fondo, display: 'flex', flexDirection: 'column' }}>
      <Box component="header" sx={{ display: 'flex', alignItems: 'center', gap: 1.5, px: 2, py: 1, bgcolor: PALETA_NEUTRA.barra,
        borderBottom: `1px solid ${PALETA_NEUTRA.borde}`, position: 'sticky', top: 0, zIndex: 10 }}>
        {volver && <Button component={Link} to={volver} size="small" aria-label="Atrás" sx={{ minWidth: 0 }}>‹</Button>}
        <Typography noWrap sx={{ fontWeight: 700, flex: 1, minWidth: 0 }}>
          {nombre}{titulo ? <Box component="span" sx={{ fontWeight: 400, color: PALETA_NEUTRA.textoSecundario }}> · {titulo}</Box> : null}
        </Typography>
        {(acciones || accionesFijas) && <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>{acciones}{accionesFijas}</Box>}
        <Typography variant="body2" sx={{ color: PALETA_NEUTRA.textoSecundario, display: { xs: 'none', sm: 'block' } }}>
          {localStorage.getItem(CLAVE_NOMBRE)}
        </Typography>
        <Button size="small" onClick={salir}>Salir</Button>
      </Box>
      {opciones && opciones.length > 0 && (
        <Box component="nav" sx={{ display: 'flex', gap: 0.5, px: 1.5, py: 0.75, overflowX: 'auto', bgcolor: PALETA_NEUTRA.barra,
          borderBottom: `1px solid ${PALETA_NEUTRA.borde}` }}>
          {opciones.map((o) => (
            <Button key={o.clave} size="small" startIcon={o.icono} onClick={o.alPulsar}
              variant={o.activa ? 'contained' : 'text'} disableElevation sx={{ flexShrink: 0, textTransform: 'none' }}>
              {o.etiqueta}{o.contador ? ` (${o.contador})` : ''}
            </Button>
          ))}
        </Box>
      )}
      {secciones.length > 1 && <SeccionesDelProyecto secciones={secciones} />}
      {!(opciones && opciones.length > 0) && <MenuDelModulo menu={menu} />}
      {/* Una columna que ocupa lo que queda: una pantalla con `flex: 1` (el marco del Observatorio) llena la ventana. */}
      <Box component="main" sx={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column' }}>{children}</Box>
    </Box>
  )
}

/** La acción principal y, a la derecha, «Actualizar» y «⋮» en la primera fila; los filtros, a su lado en pantallas
 *  anchas y en su propia fila en el celular (nunca partidos entre las dos). */
function BarraModuloMinima({ principal, children, mas = [], alActualizar, mb = 1.5 }: PropsBarraModulo) {
  const [menu, setMenu] = useState<HTMLElement | null>(null)
  const angosta = useMediaQuery('(max-width: 599.95px)')
  const secundarias = mas.filter(Boolean) as AccionSecundaria[]
  const filtros = children ? <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap', minWidth: 0 }}>{children}</Box> : null
  return (
    <Box sx={{ mb }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        {principal}
        {!angosta && filtros}
        <Box sx={{ ml: 'auto', display: 'flex', alignItems: 'center', flexShrink: 0 }}>
          {alActualizar && <Button size="small" onClick={() => void alActualizar()} aria-label="Actualizar" sx={{ minWidth: 36 }}>↻</Button>}
          {secundarias.length > 0 && (
            <Button size="small" onClick={(e) => setMenu(e.currentTarget)} aria-label="Más acciones" sx={{ minWidth: 36 }}>⋮</Button>
          )}
        </Box>
      </Box>
      {angosta && filtros && <Box sx={{ mt: 1 }}>{filtros}</Box>}
      {secundarias.length > 0 && (
        <>
          <Menu anchorEl={menu} open={Boolean(menu)} onClose={() => setMenu(null)}>
            {secundarias.map((a) => (
              <MenuItem key={a.etiqueta} disabled={a.deshabilitada} onClick={() => { setMenu(null); a.alPulsar() }}>
                {a.icono}<Box component="span" sx={{ ml: a.icono ? 1 : 0 }}>{a.etiqueta}</Box>
              </MenuItem>
            ))}
          </Menu>
        </>
      )}
    </Box>
  )
}

function BotonAyudaMinimo({ titulo, children, etiqueta }: PropsBotonAyuda) {
  const [abierta, setAbierta] = useState(false)
  return (
    <>
      <Button size="small" onClick={() => setAbierta(true)} aria-label={`Ayuda: ${titulo}`}>{etiqueta ?? '?'}</Button>
      <Dialog open={abierta} onClose={() => setAbierta(false)} maxWidth="sm" fullWidth>
        <DialogTitle>{titulo}</DialogTitle>
        <DialogContent><Typography variant="body2" component="div">{children}</Typography></DialogContent>
      </Dialog>
    </>
  )
}

/** El PDF de la API, con la sesión, en el visor del navegador. */
function VisorPdfMinimo({ ruta, version, nombre, alto = '100%', vacio }: PropsVisorPdf) {
  const [url, setUrl] = useState('')
  const [error, setError] = useState('')
  useEffect(() => {
    if (!ruta) return
    let vivo = true
    let creada = ''
    blob(ruta).then((b) => { if (vivo) { creada = URL.createObjectURL(b); setUrl(creada) } })
      .catch((e) => vivo && setError((e as Error).message))
    return () => { vivo = false; if (creada) URL.revokeObjectURL(creada) }
  }, [ruta, version])
  if (!ruta) return null
  if (error) return vacio ? <>{vacio}</> : <Typography variant="body2" sx={{ p: 2, color: PALETA_NEUTRA.error }}>{error}</Typography>
  if (!url) return <Box sx={{ display: 'grid', placeItems: 'center', height: alto }}><CircularProgress size={24} /></Box>
  return <Box component="iframe" title={nombre ?? 'PDF'} src={url} sx={{ width: '100%', height: alto, border: 0 }} />
}

function EstadoVacioMinimo({ icono, titulo, texto, accion }: PropsEstadoVacio) {
  return (
    <Box sx={{ textAlign: 'center', py: 6, px: 2, color: PALETA_NEUTRA.textoSecundario }}>
      {icono}
      <Typography sx={{ fontWeight: 600, color: PALETA_NEUTRA.texto, mt: 1 }}>{titulo}</Typography>
      {texto && <Typography variant="body2" sx={{ mt: 0.5 }}>{texto}</Typography>}
      {accion && <Box sx={{ mt: 2 }}>{accion}</Box>}
    </Box>
  )
}

/** El anfitrión web de la cáscara mínima (se activa al importar el módulo de la página). */
export function anfitrionMinimo(nombre: string, menu: OpcionMenu[] = [], secciones: OpcionMenu[] = []): AnfitrionWeb {
  return {
    nombre,
    api: pedir,
    token: () => localStorage.getItem(CLAVE_FICHA),
    rol: () => localStorage.getItem(CLAVE_ROL) ?? '',
    cerrarSesion: salir,
    confirmar: (mensaje, op = {}) => Promise.resolve(window.confirm(op.titulo ? `${op.titulo}\n\n${mensaje}` : mensaje)),
    avisar: (mensaje, op = {}) => Promise.resolve(window.alert(op.titulo ? `${op.titulo}\n\n${mensaje}` : mensaje)),
    pedirTexto: (mensaje, op = {}) => Promise.resolve(window.prompt(mensaje, op.inicial ?? '')),
    subirArchivo: subir,
    descargarBlob: blob,
    descargarArchivo: descargar,
    Marco: (props: PropsMarco) => <MarcoMinimo {...props} nombre={nombre} menu={menu} secciones={secciones} />,
    EstadoVacio: EstadoVacioMinimo,
    BarraModulo: BarraModuloMinima,
    BotonAyuda: BotonAyudaMinimo,
    VisorPdf: VisorPdfMinimo,
    paleta: PALETA_NEUTRA,
    modo: 'claro',
    almacen: {
      guardarHandle: async (h, clave = 'carpeta') => void (await operar('readwrite', (s) => s.put(h, clave))),
      leerHandle: async (clave = 'carpeta') => (await operar<FileSystemDirectoryHandle | undefined>('readonly', (s) => s.get(clave))) ?? null,
      olvidarHandle: async (clave = 'carpeta') => void (await operar('readwrite', (s) => s.delete(clave))),
    },
  }
}

function Entrar({ nombre, alEntrar }: { nombre: string; alEntrar: () => void }) {
  const [usuario, setUsuario] = useState('')
  const [clave, setClave] = useState('')
  const [error, setError] = useState('')
  const enviar = async (e: FormEvent) => {
    e.preventDefault()
    setError('')
    try {
      const r = await pedir<{ token: string; rol: string; nombre: string }>('/api/auth/login', {
        method: 'POST', body: JSON.stringify({ usuario, clave }),
      })
      localStorage.setItem(CLAVE_FICHA, r.token)
      localStorage.setItem(CLAVE_ROL, r.rol)
      localStorage.setItem(CLAVE_NOMBRE, r.nombre)
      alEntrar()
    } catch (x) {
      setError((x as Error).message)
    }
  }
  return (
    <Box sx={{ minHeight: '100dvh', display: 'grid', placeItems: 'center', bgcolor: PALETA_NEUTRA.fondo, px: 2 }}>
      <Box component="form" onSubmit={enviar} sx={{ width: '100%', maxWidth: 360, bgcolor: PALETA_NEUTRA.superficie, p: 3,
        borderRadius: 3, boxShadow: PALETA_NEUTRA.sombra, display: 'grid', gap: 2 }}>
        <Typography variant="h6" sx={{ fontWeight: 700 }}>{nombre}</Typography>
        <TextField label="Usuario" value={usuario} onChange={(e) => setUsuario(e.target.value)} autoComplete="username" autoFocus />
        <TextField label="Clave" type="password" value={clave} onChange={(e) => setClave(e.target.value)} autoComplete="current-password" />
        {error && <Typography variant="body2" sx={{ color: PALETA_NEUTRA.error }}>{error}</Typography>}
        <Button type="submit" variant="contained" disabled={!usuario || !clave}>Entrar</Button>
      </Box>
    </Box>
  )
}

/** La página entera: las pantallas públicas del módulo (sin sesión) y, para lo demás, el inicio de sesión y, con
 *  sesión, la pantalla del módulo. Un proyecto con varios módulos (`modulos`, con su `nombre`) los monta todos, cada uno
 *  en su ruta y con sus pantallas, y una barra para pasar de uno a otro; lo que no casa con ninguna ruta abre el primero. */
export function CascaronMinimo({ modulo, modulos, nombre }: { modulo?: ModuloWeb; modulos?: ModuloWeb[]; nombre?: string }) {
  const lista = useMemo(() => modulos ?? (modulo ? [modulo] : []), [modulo, modulos])
  const principal = lista[0]
  const titulo = nombre ?? principal.nombre
  const [conSesion, setConSesion] = useState(() => Boolean(localStorage.getItem(CLAVE_FICHA)))
  const secciones = lista.length > 1
    ? lista.map((m) => ({ etiqueta: m.corto ?? m.nombre, ruta: m.ruta, icono: m.icono ?? (() => null) }))
    : []
  activarAnfitrionWeb(anfitrionMinimo(titulo, lista.length === 1 ? principal.opciones ?? [] : [], secciones))
  const Pantalla = useMemo(() => lazy(principal.cargar), [principal])
  const otras = useMemo(() => lista.flatMap((m, i) => [
    ...(i > 0 ? [{ ruta: m.ruta, Pantalla: lazy(m.cargar) }] : []),
    ...(m.pantallas ?? []).map((p) => ({ ruta: p.ruta, Pantalla: lazy(p.cargar) })),
  ]), [lista])
  const publicas = useMemo(() => lista.flatMap((m) => (m.publicas ?? []).map((p) => ({ ruta: p.ruta, Pantalla: lazy(p.cargar) }))), [lista])
  const privado = conSesion ? (
    <Routes>
      {otras.map(({ ruta, Pantalla: Otra }) => <Route key={ruta} path={ruta} element={<Otra />} />)}
      <Route path="*" element={<Pantalla />} />
    </Routes>
  ) : <Entrar nombre={titulo} alEntrar={() => setConSesion(true)} />
  return (
    <ThemeProvider theme={TEMA}>
    <BrowserRouter>
      <CssBaseline />
      <Suspense fallback={<Box sx={{ display: 'grid', placeItems: 'center', minHeight: '100dvh' }}><CircularProgress /></Box>}>
        <Routes>
          {publicas.map(({ ruta, Pantalla: Publica }) => <Route key={ruta} path={ruta} element={<Publica />} />)}
          <Route path="*" element={privado} />
        </Routes>
      </Suspense>
    </BrowserRouter>
    </ThemeProvider>
  )
}
