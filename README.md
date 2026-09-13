# HakaPokes — Prototipo analítico (TFM Equipo 4A, Entregable 4)

Trabajo Fin de Máster — *Análisis de Ventas y Pronósticos para la Optimización
de Inventarios y Retención de Clientes*. Este repositorio contiene el código,
los datos procesados y el prototipo (cuadro de mando + notebooks) que
respaldan los resultados presentados en el documento del proyecto.

## Qué hay aquí

| Carpeta | Contenido |
|---|---|
| `data/raw/` | Datos originales: transacciones sintéticas (JSON, no incluido por tamaño, ver abajo) y `Resumen_Inventario_y_Ventas.xlsx` |
| `data/processed/` | Modelo de datos en estrella (dimensiones + hechos) en CSV, listo para Power BI u otra herramienta de BI |
| `notebooks/` | Notebooks ejecutados: generación de datos sintéticos y modelado de los Módulos 1 y 2 |
| `scripts/` | Pipeline de limpieza, modelado y construcción del modelo de datos, en scripts numerados por orden de ejecución |
| `scripts/exploracion_modulo2/` | Proceso de auditoría que llevó a reconstruir honestamente el Módulo 2 (ver Metodología, sección "Supuesto causal declarado") |
| `dashboard/` | Prototipo de cuadro de mando interactivo (D3.js), autocontenido, se alimenta de un único JSON vía `fetch()` |
| `powerbi/` | Guía de medidas DAX y layout de páginas para replicar el cuadro de mando en Power BI Desktop a partir de los CSV de `data/processed/` |
| `docs/` | Documento del TFM (Entregable 4) |

## Cómo correr el pipeline completo

**Requisito:** Python 3.10+, con `pandas`, `numpy`, `scikit-learn`, `openpyxl` instalados
(`pip install pandas numpy scikit-learn openpyxl`).

1. Coloca el archivo `hakapokes_synthetic_transactions.json` (500,000 transacciones)
   dentro de `data/raw/` — no viene incluido en el repo por pesar ~627 MB
   (límite de GitHub: 100 MB/archivo).
2. Ejecuta los scripts en orden:
   ```bash
   cd scripts
   python3 01_limpieza_pedidos.py
   python3 02_asignar_unidades.py
   python3 03_modelo_estrella_powerbi.py
   python3 04_estacionalidad_modulo1.py
   ```
   Esto regenera todos los CSV de `data/processed/` y el JSON consolidado de `dashboard/data/`.
3. Abre el prototipo:
   ```bash
   cd dashboard
   python3 -m http.server 8000
   ```
   y visita `http://localhost:8000`. (`fetch()` no funciona abriendo el archivo con doble clic — los navegadores bloquean peticiones locales por seguridad; por eso se necesita un servidor, aunque sea local.)

## Notebooks

- **`HakaPokes_Pipeline_Modelado.ipynb`** — plantilla metodológica: genera un
  dataset sintético propio replicando las reglas de negocio documentadas, y
  entrena los mismos modelos que el proyecto original, como ejercicio de
  verificación reproducible.
- **`HakaPokes_Notebook_Final_Modulo1y2.ipynb`** — el notebook definitivo:
  corre sobre las 500,000 transacciones reales, documenta explícitamente el
  supuesto causal usado para reconstruir la propensión a combo del Módulo 2
  (ver celda de metodología), y reporta las métricas finales usadas en el
  documento.

## Nota de transparencia metodológica

Durante el desarrollo se detectó que la columna `tiene_bebida` del dataset
original era estadísticamente independiente de cualquier variable de
contexto (ROC-AUC ≈ 0.50 con tres algoritmos distintos). En vez de mantener
cifras no reproducibles, se optó por reconstruir esa variable bajo una regla
causal declarada explícitamente (ver `scripts/exploracion_modulo2/` y la
Sección de Metodología del documento). De la misma forma, la estacionalidad
anual (vacaciones, diciembre, cuesta de enero) no estaba presente en los
datos originales y se añadió como supuesto declarado, documentado en
`scripts/04_estacionalidad_modulo1.py`. Ambas decisiones están documentadas
para que cualquier persona pueda auditarlas y reproducirlas.

## Equipo

Héctor Miguel Silva Garnica · Juan Salvador Rodríguez Aguirre ·
Omar Gaspar Ramírez · María Fernanda Zúniga Arteaga
Máster Universitario en Análisis y Visualización de Datos Masivos — UNIR
