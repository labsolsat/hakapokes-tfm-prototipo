import json
import time
from pathlib import Path

# ---- Rutas relativas al repo (funcionan en cualquier maquina que lo clone) ----
# Este archivo vive en scripts/exploracion_modulo2/, asi que sube TRES niveles
# hasta la raiz del repo.
BASE_DIR = Path(__file__).resolve().parent.parent.parent
RAW_DIR = BASE_DIR / "data" / "raw"
OUT_DIR = BASE_DIR / "data" / "processed"
OUT_DIR.mkdir(parents=True, exist_ok=True)

path = RAW_DIR / "hakapokes_synthetic_transactions.json"

fecha_registro = []
nombre_sucursal = []
tamano = []
precio_base_mxn = []
monto_total_mxn = []
tiene_bebida = []
precio_bebida_mxn = []

t0 = time.time()
n = 0
errors = 0
with open(path, "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line or line in ("[", "]"):
            continue
        if line.endswith(","):
            line = line[:-1]
        if not line:
            continue
        try:
            obj = json.loads(line)
        except Exception:
            errors += 1
            continue
        n += 1
        fecha_registro.append(obj.get("fecha_registro"))
        nombre_sucursal.append(obj.get("nombre_sucursal"))
        prod = obj.get("producto", {}) or {}
        tamano.append(prod.get("tamano"))
        precio_base_mxn.append(prod.get("precio_base_mxn"))
        monto_total_mxn.append(obj.get("monto_total_mxn"))
        comp = obj.get("complementos") or {}
        bebida = comp.get("bebida")
        tiene_bebida.append(1 if bebida else 0)
        precio_bebida_mxn.append(comp.get("precio_bebida_mxn") or 0.0)

        if n % 100000 == 0:
            print(f"  procesados {n:,} registros... ({time.time()-t0:.1f}s)")

print(f"\nTotal registros parseados: {n:,} | errores de parseo: {errors} | tiempo: {time.time()-t0:.1f}s")

import pandas as pd
import numpy as np

df = pd.DataFrame({
    "fecha_registro": pd.to_datetime(fecha_registro, utc=True, errors="coerce"),
    "nombre_sucursal": nombre_sucursal,
    "tamano": tamano,
    "precio_base_mxn": pd.to_numeric(precio_base_mxn, errors="coerce"),
    "monto_total_mxn": pd.to_numeric(monto_total_mxn, errors="coerce"),
    "tiene_bebida": np.array(tiene_bebida, dtype=np.int8),
    "precio_bebida_mxn": pd.to_numeric(precio_bebida_mxn, errors="coerce"),
})

print("\nShape:", df.shape)
print(df.dtypes)
print("\nValores nulos por columna:")
print(df.isna().sum())
print("\nRango de fechas:", df["fecha_registro"].min(), "->", df["fecha_registro"].max())
print("\nSucursales:", df["nombre_sucursal"].value_counts().to_dict())
print("\nTamaños:", df["tamano"].value_counts().to_dict())
print("\nTasa global de conversión a bebida (tiene_bebida=1):", round(df["tiene_bebida"].mean(), 4))
print("\nEstadísticos monto_total_mxn:")
print(df["monto_total_mxn"].describe())

df.to_pickle(OUT_DIR / "hakapokes_clean.pkl")
print(f"\nGuardado en {OUT_DIR / 'hakapokes_clean.pkl'}")
