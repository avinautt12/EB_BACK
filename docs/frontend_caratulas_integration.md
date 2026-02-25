Integración rápida (Frontend) — Consumo de `/detalle-compras-odoo`

Resumen
- Endpoint: `GET /detalle-compras-odoo?cliente=...` devuelve JSON `{ data: [...], rows: [...] }`.
- `rows` es una lista plana con columnas: `numero_factura`, `clave_producto`, `producto`, `descripcion`, `fecha`, `precio_unitario`, `cantidad`, `total`, `orden`, `cliente`, `pickings`, `estatus_out`.
- Use `rows` para alimentar la tabla del UI. `pickings` es un array con objetos `{ picking, estado, scheduled_date, moves }`.

Ejemplo (React + fetch)

- Pegar en el componente donde quiere cargar la tabla.

```jsx
import React, { useEffect, useState } from 'react'

export default function DetalleComprasTable({ cliente }) {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!cliente) return
    setLoading(true)
    setError(null)

    fetch(`http://127.0.0.1:5001/detalle-compras-odoo?cliente=${encodeURIComponent(cliente)}`, {
      credentials: 'include'
    })
      .then(res => res.json())
      .then(json => {
        if (json.error) throw new Error(json.error)
        // Preferir `rows` para la tabla; si no existe, derivar de `data`
        const out = json.rows || (json.data ? json.data.flatMap(d => d.lineas || []) : [])
        setRows(out)
      })
      .catch(err => setError(err.message || 'Error'))
      .finally(() => setLoading(false))
  }, [cliente])

  if (loading) return <div>Cargando...</div>
  if (error) return <div>Error: {error}</div>
  if (!rows.length) return <div>No hay datos</div>

  return (
    <table className="table">
      <thead>
        <tr>
          <th>Factura / Orden</th>
          <th>Clave</th>
          <th>Producto</th>
          <th>Descripción</th>
          <th>Fecha</th>
          <th>Precio</th>
          <th>Cantidad</th>
          <th>Total</th>
          <th>Estatus OUT</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r, i) => (
          <tr key={i}>
            <td>{r.numero_factura || r.orden}</td>
            <td>{r.clave_producto}</td>
            <td>{r.producto}</td>
            <td>{r.descripcion}</td>
            <td>{r.fecha}</td>
            <td>{(r.precio_unitario ?? 0).toFixed ? r.precio_unitario.toFixed(2) : r.precio_unitario}</td>
            <td>{r.cantidad}</td>
            <td>{r.total}</td>
            <td>
              {r.estatus_out ? (
                <span className={`badge badge-${estatusClass(r.estatus_out)}`}>{r.estatus_out}</span>
              ) : (
                '—'
              )}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function estatusClass(estatus) {
  // mapear colores: Listo = success, Hecho = primary, En espera = warning
  if (!estatus) return 'secondary'
  const s = estatus.toLowerCase()
  if (s === 'listo') return 'success'
  if (s === 'hecho') return 'primary'
  if (s.includes('espera')) return 'warning'
  return 'secondary'
}
```

Notas
- Asegúrate de que el origen del frontend esté incluido en `allowed_origins` (ya configurado en `app.py`).
- Si necesitas columnas distintas, dime exactamente el orden/nombres y adapto el backend para devolver `columns` metadata.
- Para paginación/filtrado en backend, puedo añadir parámetros `limit`, `offset`, `estado`, `desde`, `hasta`.
