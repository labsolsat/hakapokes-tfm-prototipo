from pathlib import Path

import pandas as pd
import numpy as np
from sklearn.linear_model import Ridge, LogisticRegression
from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier, HistGradientBoostingRegressor
from sklearn.metrics import (mean_absolute_error, mean_squared_error, r2_score,
                              roc_auc_score, recall_score, precision_score, f1_score,
                              confusion_matrix, accuracy_score)
from sklearn.model_selection import train_test_split

RNG_SEED = 42

# ---- Rutas relativas al repo (funcionan en cualquier maquina que lo clone) ----
# Este archivo vive en scripts/exploracion_modulo2/, asi que sube TRES niveles
# hasta la raiz del repo.
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data" / "processed"
SCRIPT_DIR = Path(__file__).resolve().parent  # aqui mismo se guarda el JSON de resultados

df = pd.read_pickle(DATA_DIR / "hakapokes_clean.pkl")
print("Dataset real cargado:", df.shape)

# ---------------------------------------------------------------------------
# FEATURE ENGINEERING sobre datos reales
# ---------------------------------------------------------------------------
df["dia_semana_num"] = df["fecha_registro"].dt.dayofweek  # 0=lunes
df["hora"] = df["fecha_registro"].dt.hour
df["es_hora_pico"] = df["hora"].isin([13, 14, 15, 18, 19, 20]).astype(int)
tamano_num_map = {"Chico": 1, "Mediano": 2, "Grande": 3}
df["tamano_num"] = df["tamano"].map(tamano_num_map)
df["fecha_dia"] = df["fecha_registro"].dt.date

print("\nVariable climática ('temperatura'): NO está presente en el dataset compartido.")
print("-> El Módulo 2 se modelará SOLO con las variables disponibles (sin clima).")
print("-> La 'elasticidad térmica' del dashboard no puede recalcularse con este archivo.")

# ---------------------------------------------------------------------------
# MÓDULO 1: PREDICCIÓN DE DEMANDA (agregado por día-sucursal-hora)
# ---------------------------------------------------------------------------
print("\n" + "=" * 70)
print("MÓDULO 1 (DATOS REALES): PREDICCIÓN DE VENTAS POR HORA-SUCURSAL")
print("=" * 70)

agg = (
    df.groupby(["fecha_dia", "nombre_sucursal", "hora"], as_index=False)
      .agg(venta_hora=("monto_total_mxn", "sum"),
           dia_semana_num=("dia_semana_num", "first"),
           es_hora_pico=("es_hora_pico", "first"),
           n_tickets=("monto_total_mxn", "count"))
)
agg["fecha_dia"] = pd.to_datetime(agg["fecha_dia"])
agg = agg.sort_values("fecha_dia").reset_index(drop=True)
agg = pd.get_dummies(agg, columns=["nombre_sucursal"], drop_first=True)

feature_cols_m1 = [c for c in agg.columns if c not in ["fecha_dia", "venta_hora", "n_tickets"]]
X, y = agg[feature_cols_m1], agg["venta_hora"]

split_idx = int(len(agg) * 0.8)
X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]
print(f"Registros agregados (dia-sucursal-hora): {len(agg):,} | Train: {len(X_train):,} | Test: {len(X_test):,}")
print(f"Rango fechas train: {agg['fecha_dia'].iloc[0].date()} -> {agg['fecha_dia'].iloc[split_idx-1].date()}")
print(f"Rango fechas test:  {agg['fecha_dia'].iloc[split_idx].date()} -> {agg['fecha_dia'].iloc[-1].date()}")

modelos_m1 = {
    "Ridge Regression (Baseline)": Ridge(alpha=1.0, random_state=RNG_SEED),
    "Random Forest Regressor": RandomForestRegressor(n_estimators=200, max_depth=12, random_state=RNG_SEED, n_jobs=-1),
    "HistGradientBoostingRegressor": HistGradientBoostingRegressor(random_state=RNG_SEED),
}

print(f"\n{'Modelo':35s} | {'MAE':>10s} | {'RMSE':>10s} | {'R2':>8s}")
print("-" * 70)
resultados_m1 = []
for nombre, modelo in modelos_m1.items():
    modelo.fit(X_train, y_train)
    pred = modelo.predict(X_test)
    mae = mean_absolute_error(y_test, pred)
    rmse = np.sqrt(mean_squared_error(y_test, pred))
    r2 = r2_score(y_test, pred)
    resultados_m1.append((nombre, mae, rmse, r2))
    print(f"{nombre:35s} | ${mae:9.2f} | ${rmse:9.2f} | {r2:8.4f}")

# También a nivel de TICKET individual (por si el "MAE por hora" del doc se refiere a esta escala)
print("\n--- Variante: modelado a nivel de TICKET individual (monto_total_mxn) ---")
df_ticket = df.copy()
df_ticket = pd.get_dummies(df_ticket, columns=["nombre_sucursal"], drop_first=True)
feat_ticket = ["dia_semana_num", "hora", "es_hora_pico", "tamano_num"] + \
              [c for c in df_ticket.columns if c.startswith("nombre_sucursal_")]
df_ticket = df_ticket.sort_values("fecha_registro").reset_index(drop=True)
Xt, yt = df_ticket[feat_ticket], df_ticket["monto_total_mxn"]
sidx = int(len(df_ticket) * 0.8)
Xt_train, Xt_test = Xt.iloc[:sidx], Xt.iloc[sidx:]
yt_train, yt_test = yt.iloc[:sidx], yt.iloc[sidx:]

hgb_ticket = HistGradientBoostingRegressor(random_state=RNG_SEED)
hgb_ticket.fit(Xt_train, yt_train)
pred_t = hgb_ticket.predict(Xt_test)
print(f"HistGradientBoosting (por TICKET) | MAE=${mean_absolute_error(yt_test, pred_t):.2f} | "
      f"RMSE=${np.sqrt(mean_squared_error(yt_test, pred_t)):.2f} | R2={r2_score(yt_test, pred_t):.4f}")

# ---------------------------------------------------------------------------
# MÓDULO 2: CLASIFICACIÓN - PROPENSIÓN A VENTA CRUZADA (BEBIDA)
# ---------------------------------------------------------------------------
print("\n" + "=" * 70)
print("MÓDULO 2 (DATOS REALES): CLASIFICACIÓN DE PROPENSIÓN A BEBIDA")
print("=" * 70)

df2 = pd.get_dummies(df, columns=["nombre_sucursal"], drop_first=True)
feature_cols_m2 = ["dia_semana_num", "hora", "es_hora_pico", "tamano_num"] + \
                   [c for c in df2.columns if c.startswith("nombre_sucursal_")]

X2, y2 = df2[feature_cols_m2], df2["tiene_bebida"]
print(f"Tasa global de conversión a bebida: {y2.mean():.4f}  (clase minoritaria = SIN bebida = {1-y2.mean():.4f})")

X2_train, X2_test, y2_train, y2_test = train_test_split(
    X2, y2, test_size=0.2, stratify=y2, random_state=RNG_SEED)
print(f"Train: {len(X2_train):,} | Test: {len(X2_test):,}")

modelos_m2 = {
    "Random Forest (Estandar)": RandomForestClassifier(n_estimators=200, max_depth=10, random_state=RNG_SEED, n_jobs=-1),
    "Random Forest (balanced)": RandomForestClassifier(n_estimators=200, max_depth=10, class_weight="balanced", random_state=RNG_SEED, n_jobs=-1),
    "Regresion Logistica (balanced)": LogisticRegression(max_iter=1000, class_weight="balanced", random_state=RNG_SEED),
}

print(f"\n{'Modelo':32s} | {'ROC-AUC':>8s} | {'Recall(SinBeb)':>14s} | {'Prec(SinBeb)':>12s} | {'F1-macro':>9s} | {'Acc':>7s}")
print("-" * 100)
cm = None
feat_importance_final = None
for nombre, modelo in modelos_m2.items():
    modelo.fit(X2_train, y2_train)
    pred = modelo.predict(X2_test)
    proba = modelo.predict_proba(X2_test)[:, 1]
    roc = roc_auc_score(y2_test, proba)
    # Clase minoritaria de interés = "Solo Bowl" = SIN bebida = 0
    rec = recall_score(y2_test, pred, pos_label=0)
    prec = precision_score(y2_test, pred, pos_label=0)
    f1m = f1_score(y2_test, pred, average="macro")
    acc = accuracy_score(y2_test, pred)
    print(f"{nombre:32s} | {roc:8.4f} | {rec:14.4f} | {prec:12.4f} | {f1m:9.4f} | {acc:7.4f}")
    if nombre == "Random Forest (balanced)":
        cm = confusion_matrix(y2_test, pred)
        feat_importance_final = pd.Series(modelo.feature_importances_, index=feature_cols_m2).sort_values(ascending=False)
    if nombre == "Random Forest (Estandar)":
        acc_base = accuracy_score(y2_test, pred)
        rec_base = recall_score(y2_test, pred, pos_label=0)

print(f"\n[Chequeo 'paradoja de exactitud']: Accuracy base del modelo estándar = {acc_base:.4f}"
      f" (≈ tasa de la clase mayoritaria) | Recall clase minoritaria = {rec_base:.4f}")

print("\nMatriz de confusion (Random Forest balanced) [filas=real 0=SinBebida/1=ConBebida , cols=pred]:")
print(cm)
print("\nImportancia de variables (Random Forest balanced), Modulo 2:")
print(feat_importance_final.round(4).to_string())

import json as _json
out = {
    "modulo1_agregado": [{"modelo": n, "mae": mae, "rmse": rmse, "r2": r2} for n, mae, rmse, r2 in resultados_m1],
    "modulo1_ticket_hgb": {"mae": float(mean_absolute_error(yt_test, pred_t)),
                            "rmse": float(np.sqrt(mean_squared_error(yt_test, pred_t))),
                            "r2": float(r2_score(yt_test, pred_t))},
    "tasa_conversion_bebida_global": float(y2.mean()),
    "modulo2_estandar": {"accuracy": float(acc_base), "recall_minoritaria": float(rec_base)},
    "feature_importance_m2": feat_importance_final.round(4).to_dict(),
}
with open(SCRIPT_DIR / "resultados_reales_final.json", "w") as f:
    _json.dump(out, f, indent=2, ensure_ascii=False)
print(f"\nGuardado {SCRIPT_DIR / 'resultados_reales_final.json'}")
