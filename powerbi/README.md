# Guía de implementación en Power BI Desktop

Esta guía toma los CSV de `../data/processed/` y reconstruye el mismo
cuadro de mando que ya existe en `../dashboard/` (D3.js), como opción
adicional o de respaldo.

## 1. Importar los datos

`Obtener datos` → `Carpeta` → selecciona `data/processed/` → `Combinar y
transformar` → carga cada CSV como una tabla independiente (no combines
archivos, son tablas distintas del modelo en estrella).

Tablas a cargar:

| Tabla origen | Rol en el modelo |
|---|---|
| `dim_sucursal.csv` | Dimensión |
| `dim_producto_tamano.csv` | Dimensión |
| `dim_factor_estacional.csv` | Dimensión (calendario/estacionalidad) |
| `fact_ventas_diarias.csv` | Hecho |
| `fact_serie_diaria_cadena_estacional.csv` | Hecho (serie ejecutiva) |
| `fact_compras_estimadas.csv` | Hecho |
| `fact_kpis_modelos.csv` | Hecho (KPIs Módulo 1 base + Módulo 2) |
| `fact_kpis_modulo1_estacional.csv` | Hecho (KPIs Módulo 1 con estacionalidad) |
| `fact_importancia_variables_m1_estacional.csv` | Hecho |
| `resumen_insumos_final.csv` | Hecho (pedidos, ya estandarizado) |

**Tipos de dato:** `fecha` / `fecha_dia` se modifican como *Fecha*, debido a que vienen como texto, y en *decimal* `valor`, `cantidad_valor`, `bowls_estimados`, `kg_arroz_estimado`, `kg_proteina_estimado`.

## 2. Relaciones del modelo

En la vista de Modelo, crea:

- `fact_ventas_diarias[sucursal]` → `dim_sucursal[sucursal]` (varios a uno)
- `fact_ventas_diarias[tamano]` → `dim_producto_tamano[tamano]`
- `fact_compras_estimadas[sucursal]` → `dim_sucursal[sucursal]`
- `fact_compras_estimadas[tamano]` → `dim_producto_tamano[tamano]`
- `fact_serie_diaria_cadena_estacional[fecha_dia]` → `dim_factor_estacional[fecha_dia]`

No relaciones directamente `fact_kpis_modelos` ni `fact_kpis_modulo1_estacional`
con nada — son tablas de métricas planas, se consultan con `CALCULATE` + filtros
de columna (ver medidas abajo), no por relación.

## 3. Medidas DAX

Crea una tabla nueva vacía llamada `_Medidas` (Modelado → Nueva tabla →
`_Medidas = ROW("x", 0)`) y agrega ahí todas las medidas, para mantenerlas
ordenadas y fuera de las tablas de datos.

### Resumen ejecutivo

```dax
Ingreso Total =
SUM(fact_serie_diaria_cadena_estacional[ingreso_total_mxn])

Transacciones Totales =
SUM(fact_serie_diaria_cadena_estacional[n_tickets])

Tasa Conversion Combo =
AVERAGE(fact_serie_diaria_cadena_estacional[tasa_bebida])

Ticket Promedio =
DIVIDE([Ingreso Total], [Transacciones Totales])
```

### Módulo 1 — Demanda

```dax
MAE Modulo 1 (Seleccionado) =
CALCULATE(
    SUM(fact_kpis_modulo1_estacional[valor]),
    fact_kpis_modulo1_estacional[modelo] = "HistGradientBoosting (Seleccionado)",
    fact_kpis_modulo1_estacional[metrica] = "MAE_MXN"
)

R2 Modulo 1 (Seleccionado) =
CALCULATE(
    SUM(fact_kpis_modulo1_estacional[valor]),
    fact_kpis_modulo1_estacional[modelo] = "HistGradientBoosting (Seleccionado)",
    fact_kpis_modulo1_estacional[metrica] = "R2"
)
```

Para la gráfica de comparación de modelos, usa `fact_kpis_modulo1_estacional`
directamente como tabla (Eje = `modelo`, Valor = `valor`, con un filtro
visual `metrica = "MAE_MXN"`) — no necesitas una medida separada por modelo.

### Módulo 2 — Venta cruzada

```dax
ROC AUC Modulo 2 (Seleccionado) =
CALCULATE(
    SUM(fact_kpis_modelos[valor]),
    fact_kpis_modelos[modulo] = "Modulo 2 - Combo",
    fact_kpis_modelos[modelo] = "Random Forest Balanced (Seleccionado)",
    fact_kpis_modelos[metrica] = "ROC_AUC"
)

Recall Solo Bowl (Seleccionado) =
CALCULATE(
    SUM(fact_kpis_modelos[valor]),
    fact_kpis_modelos[modulo] = "Modulo 2 - Combo",
    fact_kpis_modelos[modelo] = "Random Forest Balanced (Seleccionado)",
    fact_kpis_modelos[metrica] = "Recall_SoloBowl"
)

F1 Macro (Seleccionado) =
CALCULATE(
    SUM(fact_kpis_modelos[valor]),
    fact_kpis_modelos[modulo] = "Modulo 2 - Combo",
    fact_kpis_modelos[modelo] = "Random Forest Balanced (Seleccionado)",
    fact_kpis_modelos[metrica] = "F1_Macro"
)
```

### Estimación de compras

```dax
Bowls Estimados =
SUM(fact_compras_estimadas[bowls_estimados])

Kg Arroz Estimado =
SUM(fact_compras_estimadas[kg_arroz_estimado])

Kg Proteina Estimado =
SUM(fact_compras_estimadas[kg_proteina_estimado])
```
Estas tres medidas ya responden solas a los segmentadores de `horizonte` y
`escenario_temporada` (ver Sección 4) — no necesitas una medida por
combinación de horizonte/escenario.

### Pedidos e insumos — confiabilidad de unidad

```dax
% Unidad Confirmada =
DIVIDE(
    CALCULATE(COUNTROWS(resumen_insumos_final), resumen_insumos_final[unidad_confirmada] = TRUE),
    COUNTROWS(resumen_insumos_final)
)
```

## 4. Segmentadores (slicers) a agregar

- **Horizonte** → columna `fact_compras_estimadas[horizonte]` (valores: `7_dias`, `30_dias`, `90_dias`)
- **Escenario de temporada** → columna `fact_compras_estimadas[escenario_temporada]`
- **Sucursal** → columna `dim_sucursal[sucursal]`, conéctalo también a la página de Resumen Ejecutivo

## 5. Layout de páginas (5 páginas, igual que el dashboard D3)

**Página 1 — Resumen Ejecutivo**
- 4 tarjetas KPI: `Ingreso Total`, `Transacciones Totales`, `Tasa Conversion Combo`, conteo de `dim_sucursal`
- Gráfico de líneas: eje `fecha_dia`, valor `ingreso_total_mxn` (tabla `fact_serie_diaria_cadena_estacional`)
- Gráfico de barras: `dim_sucursal[sucursal]` vs. suma de `fact_ventas_diarias[ingreso_total_mxn]`
- Gráfico de líneas: `fecha_dia` vs. `tasa_bebida`

**Página 2 — Módulo 1 · Demanda**
- 2 tarjetas KPI: `MAE Modulo 1 (Seleccionado)`, `R2 Modulo 1 (Seleccionado)`
- Gráfico de barras: `fact_kpis_modulo1_estacional` filtrado a `metrica = MAE_MXN`, eje `modelo`
- Gráfico de barras horizontal: `fact_importancia_variables_m1_estacional`, eje `variable`, valor `importancia`

**Página 3 — Módulo 2 · Venta Cruzada**
- 3 tarjetas KPI: `ROC AUC Modulo 2`, `Recall Solo Bowl`, `F1 Macro`
- Gráfico de barras horizontal: importancia de variables (usa la tabla de importancia del Módulo 2, agrégala como CSV adicional si quieres replicarla — no viene en `data/processed/` porque hoy solo vive en el JSON del dashboard; cópiala desde ahí como tabla manual de 10 filas)
- Matriz o tabla: matriz de confusión (también hay que capturarla manualmente del JSON, 4 valores)

**Página 4 — Estimación de Compras**
- Segmentadores de Horizonte y Escenario arriba
- 3 tarjetas KPI: `Bowls Estimados`, `Kg Arroz Estimado`, `Kg Proteina Estimado`
- Gráfico de barras agrupadas: eje `dim_sucursal[sucursal]`, valores `Kg Arroz Estimado` y `Kg Proteina Estimado`

**Página 5 — Pedidos e Insumos**
- Tabla: `resumen_insumos_final` (categoria_real, producto, unidad_final, cantidad_valor, unidad_confirmada)
- Formato condicional en la columna `unidad_confirmada`: verde si `TRUE`, ámbar si `FALSE`, se modificaron a 1 y 0, ya que no se lograba aplicar el formato condicional en la ultima tabla de pedidos con top 40.
- Tarjeta KPI: `% Unidad Confirmada`

## Nota

Las tablas de importancia de variables y matriz de confusión del Módulo 2
no tienen CSV propio todavía (viven embebidas en el JSON del dashboard
D3).
