# HakaPokes — Prototipo analítico (TFM Equipo 4A, Entregable 4)

Trabajo Fin de Máster — *Análisis de Ventas y Pronósticos para la Optimización
de Inventarios y Retención de Clientes*. Este repositorio contiene el código,
los datos procesados y el prototipo (cuadro de mando + notebooks) que
respaldan los resultados presentados en el documento del proyecto.

## Qué hay aquí

| Carpeta                        | Contenido                                                                                                                             |
| ------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------- |
| `data/raw/`                    | Datos originales: transacciones sintéticas (JSON, no incluido por tamaño, ver abajo) y `Resumen_Inventario_y_Ventas.xlsx`             |
| `data/processed/`              | Modelo de datos en estrella (dimensiones + hechos) en CSV, listo para Power BI u otra herramienta de BI                               |
| `notebooks/`                   | Notebooks ejecutados: generación de datos sintéticos y modelado de los Módulos 1 y 2                                                  |
| `scripts/`                     | Pipeline de limpieza, modelado y construcción del modelo de datos, en scripts numerados por orden de ejecución                        |
| `scripts/exploracion_modulo2/` | Proceso de auditoría que llevó a reconstruir honestamente el Módulo 2 (ver Metodología, sección "Supuesto causal declarado")          |
| `dashboard/`                   | Prototipo de cuadro de mando interactivo (D3.js), autocontenido, se alimenta de un único JSON vía `fetch()`                           |
| `powerbi/`                     | Prototipo del cuadro de mando en Power BI Desktop (`.pbix`) más la guía de medidas DAX y layout de páginas, construido a partir de los CSV de `data/processed/` |
| `docs/`                        | Documento del TFM (Entregable 4)                                                                                                      |

## Cómo correr el pipeline completo

**Requisito:** Python 3.10+, con `pandas`, `numpy`, `scikit-learn`, `openpyxl` instalados
(`pip install pandas numpy scikit-learn openpyxl`).

1. Asegúrate de tener ambos archivos en `data/raw/`:
   - `hakapokes_synthetic_transactions.json` (500,000 transacciones, ~627 MB).
     Este archivo **sí está incluido en el repo**, pero versionado con
     [Git LFS](https://git-lfs.com/) (supera el límite de GitHub de 100 MB/archivo
     para un blob normal). Para que se descargue correctamente al clonar:

     ```
     git lfs install
     git clone https://github.com/labsolsat/hakapokes-tfm-prototipo.git
     ```

     Si ya tenías el repo clonado antes de que se subiera por LFS, corre
     `git lfs pull` dentro de la carpeta del repo para traer el contenido real
     del archivo (de lo contrario `data/raw/hakapokes_synthetic_transactions.json`
     quedará como un archivo apuntador de unos cuantos KB, no el JSON completo,
     y los scripts fallarán al intentar leerlo).
   - `Resumen_Inventario_y_Ventas.xlsx` (no versionado por LFS, colócalo
     manualmente en `data/raw/`).

2. Ejecuta los scripts **en este orden** (los de `exploracion_modulo2/` van
   primero: generan el pickle de transacciones limpias y la reconstrucción
   causal del Módulo 2 que usan los scripts principales más adelante):

   ```
   cd scripts/exploracion_modulo2
   python 01_parseo_json_real.py
   python 03_reconstruccion_causal_declarada.py
   cd ..
   python 01_limpieza_pedidos.py
   python 02_asignar_unidades.py
   python 04_estacionalidad_modulo1.py
   python 03_modelo_estrella_powerbi.py
   ```

   > **Nota sobre el orden:** `04_estacionalidad_modulo1.py` debe correr
   > *antes* que `03_modelo_estrella_powerbi.py`, porque este último lee los
   > CSV de estacionalidad (`fact_serie_diaria_cadena_estacional.csv`,
   > `fact_kpis_modulo1_estacional.csv`, `dim_factor_estacional.csv`,
   > `fact_importancia_variables_m1_estacional.csv`) que genera `04`. El
   > número en el nombre de archivo indica el módulo temático que trabaja
   > cada script, no su posición en la secuencia de ejecución.

   `02_auditoria_modelos_reales.py` (dentro de `exploracion_modulo2/`) es solo
   diagnóstico — no es requerido por el pipeline principal, pero puede
   ejecutarse en cualquier momento después de `01_parseo_json_real.py`.

   Esto regenera todos los CSV de `data/processed/` y el JSON consolidado de
   `dashboard/data/`.

3. Abre el prototipo:

   ```
   cd dashboard
   python3 -m http.server 8000
   ```

   y visita `http://localhost:8000`. (`fetch()` no funciona abriendo el
   archivo con doble clic — los navegadores bloquean peticiones locales por
   seguridad; por eso se necesita un servidor, aunque sea local.)

   > **Alternativa en Power BI:** el mismo prototipo también está disponible
   > como archivo `.pbix` dentro de `powerbi/`, replicando las mismas páginas
   > y métricas del dashboard D3 a partir de los CSV de `data/processed/`.
   > Solo necesitas Power BI Desktop instalado — no requiere levantar un
   > servidor local. Consulta `powerbi/README.md` para la guía de medidas DAX
   > y el layout de páginas.

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

**Importante:** el JSON consolidado que alimenta el dashboard D3 combina dos
fuentes distintas para todo lo relacionado con "bebida": la tasa de
conversión real (`tiene_bebida` original) se usa en los agregados de ventas
(`fact_ventas_diarias`, serie diaria de la cadena), mientras que las métricas
del Módulo 2 (ROC-AUC, matriz de confusión, importancia de variables,
sensibilidad a temperatura) provienen de la versión reconstruida bajo el
supuesto causal declarado. Ambas series no son directamente comparables entre
sí — cada una responde a una pregunta distinta y está identificada como tal
en el código y en el documento.

## Equipo

Héctor Miguel Silva Garnica · Juan Salvador Rodríguez Aguirre ·
Omar Gaspar Ramírez · María Fernanda Zúniga Arteaga
Máster Universitario en Análisis y Visualización de Datos Masivos — UNIR
