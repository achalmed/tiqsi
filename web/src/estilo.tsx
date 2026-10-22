/**
 * TIQSI WEB, EL LENGUAJE VISUAL COMÚN — las piezas puras que todos los módulos dibujan igual, con o sin anfitrión
 * (2026-10-21, para Qillqasqa Q6b-2c). Venían de Qillqa (`componentes/Estilo.tsx`, `BotonActualizar.tsx`,
 * `HojaInferior.tsx`), que ahora las toma de aquí: una sola forma para todas las pantallas.
 *
 *   · `Titulo` — tres niveles, y solo tres: `seccion` (título de un bloque), `sub` (subtítulo dentro de un bloque) y
 *     `grupo` (rótulo de un grupo de campos, con la letra de la etiqueta flotante de un campo).
 *   · `Bloque` — una sección sin caja: espacio, una línea fina arriba (salvo el primero) y un filete a la izquierda.
 *   · `EstadoPieza` — punto + palabra: gris = pendiente, ámbar = parcial, verde = completo.
 *   · `BotonActualizar` — un ícono pequeño que gira mientras el módulo vuelve a leer (no toca lo que espera).
 *   · `HojaInferior` — lo que se abre desde abajo en el celular: esquinas redondeadas, el asa y el borde seguro.
 *   · `pdfEnLinea` — si el navegador muestra un PDF dentro de la página (en el celular, no: se descarga).
 *
 * Es una entrada aparte (`@qillqa/tiqsi/estilo`) para que el contrato (`@qillqa/tiqsi`), que el anfitrión carga al
 * arrancar, no arrastre MUI: los colores salen de `PALETA`, que se lee al pintar. Solo usa las piezas básicas de MUI
 * (Box, Stack, Typography, Tooltip, IconButton, Drawer): el anfitrión la instala por un enlace y su servidor de desarrollo
 * no preempaqueta lo que importa (un `SvgIcon` que el anfitrión no usa llegaba crudo y la página no abría); el ícono
 * de «Actualizar» es un `<svg>` sobre Box.
 */
import { useEffect, useRef, useState, type ReactNode } from 'react'
import Box from '@mui/material/Box'
import Drawer from '@mui/material/Drawer'
import IconButton from '@mui/material/IconButton'
import Stack from '@mui/material/Stack'
import Tooltip from '@mui/material/Tooltip'
import Typography from '@mui/material/Typography'
import { PALETA } from './index'

/** Título con jerarquía fija. `accion` va pegada al borde derecho (un botón, una marca). */
export function Titulo({ nivel = 'seccion', icono, children, accion, sx }: {
  nivel?: 'seccion' | 'sub' | 'grupo'
  icono?: ReactNode
  children: ReactNode
  accion?: ReactNode
  sx?: object
}) {
  const variante = nivel === 'seccion' ? 'h6' : nivel === 'sub' ? 'subtitle2' : 'caption'
  return (
    <Stack direction="row" spacing={0.75} useFlexGap alignItems="center" flexWrap="wrap"
      sx={{ mb: nivel === 'grupo' ? 0.5 : 0.75, minWidth: 0, ...sx }}>
      {icono && <Box sx={{ display: 'flex', color: 'text.secondary', '& svg': { fontSize: 18 } }}>{icono}</Box>}
      <Typography variant={variante} component={nivel === 'seccion' ? 'h2' : nivel === 'sub' ? 'h3' : 'span'}
        sx={nivel === 'grupo' ? { color: 'text.secondary', fontSize: 12, lineHeight: 1.2 } : { minWidth: 0 }}>
        {children}
      </Typography>
      {accion && <Box sx={{ ml: 'auto', display: 'flex', alignItems: 'center', flex: '0 0 auto' }}>{accion}</Box>}
    </Stack>
  )
}

/** Estado de una pieza (firmado, cargo, respuesta…): la gramática del estado —punto + palabra— sin colores decorativos. */
export function EstadoPieza({ estado, texto }: { estado: 'pendiente' | 'parcial' | 'completo' | 'neutro'; texto: string }) {
  const color = estado === 'completo' ? PALETA.exito : estado === 'parcial' ? PALETA.aviso : PALETA.apagado
  return (
    <Box component="span" sx={{
      display: 'inline-flex', alignItems: 'center', gap: 0.75, fontSize: 11.5, fontWeight: 600,
      color: estado === 'pendiente' || estado === 'neutro' ? 'text.secondary' : color, whiteSpace: 'nowrap',
    }}>
      <Box component="span" sx={{ width: 7, height: 7, borderRadius: '50%', bgcolor: color, flex: '0 0 auto' }} />
      {texto}
    </Box>
  )
}

/** Bloque de sección sin caja: separación por espacio, una línea fina arriba (salvo el primero) y un filete a la izquierda. */
export function Bloque({ children, primero = false, sx }: { children: ReactNode; primero?: boolean; sx?: object }) {
  return (
    <Box sx={{
      pt: primero ? 0 : 2.5, mt: primero ? 0 : 2.5, borderTop: primero ? 'none' : `1px solid ${PALETA.borde}`,
      pl: 1.5, borderLeft: `2px solid ${PALETA.borde}`, ...sx,
    }}>
      {children}
    </Box>
  )
}

/** «Actualizar» discreto: gira mientras `alActualizar` relee (al menos media vuelta, para que se note). */
export function BotonActualizar({ alActualizar, etiqueta = 'Actualizar', tamano = 'small', color = 'text.secondary' }: {
  /** Vuelve a leer; si devuelve una promesa, el ícono gira hasta que termine. */
  alActualizar: () => void | Promise<unknown>
  etiqueta?: string
  tamano?: 'small' | 'medium'
  /** Color del ícono: `inherit` sobre un encabezado oscuro. */
  color?: string
}) {
  const [girando, setGirando] = useState(false)
  const vivo = useRef(true)
  useEffect(() => () => { vivo.current = false }, [])
  const pulsar = async () => {
    if (girando) return
    setGirando(true)
    const desde = Date.now()
    try {
      await alActualizar()
    } catch {
      /* el módulo ya muestra su propio error */
    } finally {
      window.setTimeout(() => { if (vivo.current) setGirando(false) }, Math.max(0, 450 - (Date.now() - desde)))
    }
  }
  return (
    <Tooltip title={etiqueta} disableInteractive>
      <span>
        <IconButton size={tamano} onClick={() => void pulsar()} aria-label={etiqueta} disabled={girando}
          sx={{ color, '&.Mui-disabled': { color, opacity: 0.7 } }}>
          <Box component="svg" viewBox="0 0 24 24" aria-hidden sx={{
            width: '1em', height: '1em', fill: 'currentColor', fontSize: tamano === 'small' ? 20 : 24,
            '@keyframes tiqsi-girar': { to: { transform: 'rotate(360deg)' } },
            animation: girando ? 'tiqsi-girar 0.9s linear infinite' : 'none',
          }}>
            <path d="M17.65 6.35C16.2 4.9 14.21 4 12 4c-4.42 0-7.99 3.58-7.99 8s3.57 8 7.99 8c3.73 0 6.84-2.55 7.73-6h-2.08c-.82 2.33-3.04 4-5.65 4-3.31 0-6-2.69-6-6s2.69-6 6-6c1.66 0 3.14.69 4.22 1.78L13 11h7V4z" />
          </Box>
        </IconButton>
      </span>
    </Tooltip>
  )
}

/** El papel de toda hoja inferior: una sola forma para todas (en la tableta, centrada y no más ancha que un teléfono). */
export const PAPEL_HOJA = {
  borderTopLeftRadius: 16,
  borderTopRightRadius: 16,
  pb: 'env(safe-area-inset-bottom)',
  maxHeight: '85dvh',
  maxWidth: 640,
  mx: 'auto',
} as const

/** El asa: la rayita que dice «esto se desliza». */
export function Asa() {
  return <Box sx={{ width: 36, height: 4, borderRadius: 2, bgcolor: 'divider', mx: 'auto', mt: 1, flexShrink: 0 }} />
}

/** El ícono en un círculo de color (como el menú de adjuntar de un chat). */
export function Circulo({ color, tamano = 36, children }: { color: string; tamano?: number; children: ReactNode }) {
  return (
    <Box sx={{
      width: tamano, height: tamano, borderRadius: '50%', bgcolor: `${color}26`, color, flexShrink: 0,
      display: 'flex', alignItems: 'center', justifyContent: 'center', '& svg': { fontSize: Math.round(tamano * 0.52) },
    }}>
      {children}
    </Box>
  )
}

/** La hoja inferior con su asa y, si se da, un título breve. */
export function HojaInferior({ abierta, alCerrar, titulo, children }: {
  abierta: boolean
  alCerrar: () => void
  titulo?: ReactNode
  children: ReactNode
}) {
  return (
    <Drawer anchor="bottom" open={abierta} onClose={alCerrar} PaperProps={{ sx: { ...PAPEL_HOJA, display: 'flex', flexDirection: 'column' } }}>
      <Asa />
      {titulo && <Typography component="h2" sx={{ fontWeight: 700, fontSize: 15.5, px: 2, pt: 1.25, pb: 0.5 }}>{titulo}</Typography>}
      <Box sx={{ overflowY: 'auto', minHeight: 0 }}>{children}</Box>
    </Drawer>
  )
}

/** ¿El navegador muestra un PDF dentro de la página? (`pdfViewerEnabled`; sin él, no en el celular). */
export const pdfEnLinea = (): boolean => {
  const n = navigator as Navigator & { pdfViewerEnabled?: boolean }
  if (typeof n.pdfViewerEnabled === 'boolean') return n.pdfViewerEnabled
  return !/Android|iPhone|iPad|iPod|Mobile/i.test(navigator.userAgent)
}
