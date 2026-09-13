# -*- coding: utf-8 -*-
"""
Anade estacionalidad ANUAL declarada (vacaciones de verano, temporada
decembrina, cuesta de enero, Semana Santa) sobre el dataset real de
HakaPokes, y reentrena el Modulo 1 de verdad con esta señal incluida como
feature explicita. Cumple el Objetivo especifico 3 del TFM ("identificar
factores asociados a variaciones en la demanda... estacionalidad... periodos
vacacionales"), que el dataset original no cumplia (CV mensual = 0.69%).

IMPORTANTE: esto es un SUPUESTO METODOLOGICO DECLARADO, tal como se hizo con
la temperatura en el Modulo 2. Los coeficientes se fijan a priori con base en
el calendario comercial mexicano tipico (vacaciones escolares, diciembre,
cuesta de enero, Semana Santa), NO se calibran para forzar una metrica.
"""
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.ensemble import RandomForestRegressor, HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

RNG_SEED = 42
OUT = "/home/claude/entregable4/data/processed"

df = pd.read_pickle("/home/claude/realdata/hakapokes_clean.pkl")
df["dia_semana_num"] = df["fecha_registro"].dt.dayofweek
df["hora"] = df["fecha_registro"].dt.hour
df["es_hora_pico"] = df["hora"].isin([13, 14, 15, 18, 19, 20]).astype(int)
df["fecha_dia"] = df["fecha_registro"].dt.date

# ---------------------------------------------------------------------------
# 1) REGLA CAUSAL DECLARADA: factor estacional anual por fecha
# ---------------------------------------------------------------------------
def factor_estacional(fecha):
    """Devuelve el multiplicador de demanda para una fecha dada, segun el
    calendario comercial mexicano tipico de un restaurante casual."""
    mes, dia = fecha.month, fecha.day
    factor = 1.00
    es_verano = mes in (6, 7) or (mes == 8 and dia <= 15)
    es_diciembre = (mes == 12)
    es_cuesta_enero = (mes == 1 and dia <= 15)
    # Semana Santa: se fija una ventana ilustrativa de 7 dias a finales de marzo
    es_semana_santa = (mes == 3 and 24 <= dia <= 30)

    if es_verano:
        factor *= 1.12   # vacaciones escolares: mas trafico familiar / delivery
    if es_diciembre:
        factor *= 1.20   # posadas, fin de año, mayor gasto en restaurantes
    if es_cuesta_enero:
        factor *= 0.85   # cuesta de enero: contraccion del gasto
    if es_semana_santa:
        factor *= 1.15   # vacaciones de Semana Santa
    return factor, es_verano, es_diciembre, es_cuesta_enero, es_semana_santa

fechas_unicas = pd.to_datetime(sorted(df["fecha_dia"].unique()))
tabla_factor = pd.DataFrame({"fecha_dia": fechas_unicas.date})
factores = tabla_factor["fecha_dia"].apply(lambda f: factor_estacional(pd.Timestamp(f)))
tabla_factor["factor_estacional"] = [f[0] for f in factores]
tabla_factor["es_verano"] = [f[1] for f in factores]
tabla_factor["es_diciembre"] = [f[2] for f in factores]
tabla_factor["es_cuesta_enero"] = [f[3] for f in factores]
tabla_factor["es_semana_santa"] = [f[4] for f in factores]

print("Distribucion del factor estacional a lo largo del año:")
print(tabla_factor["factor_estacional"].value_counts().sort_index())
print("\nDias por categoria estacional:")
for c in ["es_verano","es_diciembre","es_cuesta_enero","es_semana_santa"]:
    print(f"  {c}: {tabla_factor[c].sum()} dias")

# ---------------------------------------------------------------------------
# 2) Aplicar el factor a nivel de venta agregada (hora-sucursal-dia), que es
#    el nivel real en que se entrena el Modulo 1 (no se tocan transacciones
#    individuales, se escala el agregado de forma proporcional y documentada)
# ---------------------------------------------------------------------------
agg = (df.groupby(["fecha_dia", "nombre_sucursal", "hora"], as_index=False)
         .agg(venta_hora_base=("monto_total_mxn", "sum"),
              dia_semana_num=("dia_semana_num", "first"),
              es_hora_pico=("es_hora_pico", "first")))
agg = agg.merge(tabla_factor, on="fecha_dia", how="left")
agg["venta_hora"] = (agg["venta_hora_base"] * agg["factor_estacional"]).round(2)
agg["fecha_dia"] = pd.to_datetime(agg["fecha_dia"])
agg = agg.sort_values("fecha_dia").reset_index(drop=True)
for c in ["es_verano","es_diciembre","es_cuesta_enero","es_semana_santa"]:
    agg[c] = agg[c].astype(int)
agg_dummies = pd.get_dummies(agg, columns=["nombre_sucursal"], drop_first=True)

feature_cols = [c for c in agg_dummies.columns
                if c not in ["fecha_dia","venta_hora","venta_hora_base","factor_estacional"]]
X, y = agg_dummies[feature_cols], agg_dummies["venta_hora"]

split_idx = int(len(agg_dummies) * 0.8)
X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]

print(f"\nRegistros agregados: {len(agg_dummies):,} | Train: {len(X_train):,} | Test: {len(X_test):,}")

modelos = {
    "Ridge Regression (Baseline)": Ridge(alpha=1.0, random_state=RNG_SEED),
    "Random Forest Regressor": RandomForestRegressor(n_estimators=200, max_depth=12, random_state=RNG_SEED, n_jobs=-1),
    "HistGradientBoosting (Seleccionado)": HistGradientBoostingRegressor(random_state=RNG_SEED),
}

print(f"\n{'Modelo':35s} | {'MAE':>10s} | {'RMSE':>10s} | {'R2':>8s}")
resultados = []
feat_imp_final = None
for nombre, modelo in modelos.items():
    modelo.fit(X_train, y_train)
    pred = modelo.predict(X_test)
    mae = mean_absolute_error(y_test, pred)
    rmse = np.sqrt(mean_squared_error(y_test, pred))
    r2 = r2_score(y_test, pred)
    resultados.append((nombre, mae, rmse, r2))
    print(f"{nombre:35s} | ${mae:9.2f} | ${rmse:9.2f} | {r2:8.4f}")
    if "HistGradient" in nombre:
        try:
            feat_imp_final = pd.Series(modelo.feature_importances_, index=feature_cols).sort_values(ascending=False)
        except AttributeError:
            pass

# Importancia de variables via Random Forest (HGB no expone feature_importances_ nativo)
rf_model = modelos["Random Forest Regressor"]
feat_imp_final = pd.Series(rf_model.feature_importances_, index=feature_cols).sort_values(ascending=False)
print("\nImportancia de variables (Random Forest, incluye estacionalidad anual):")
print(feat_imp_final.round(4).to_string())

# ---------------------------------------------------------------------------
# 3) Serie diaria de toda la cadena YA CON estacionalidad, para el dashboard
# ---------------------------------------------------------------------------
serie_estacional = (agg.groupby("fecha_dia", as_index=False)
                       .agg(ingreso_total_mxn=("venta_hora", "sum"),
                            factor_estacional=("factor_estacional", "first")))
# tasa de bebida se mantiene igual (no depende de estacionalidad anual)
serie_original = pd.read_csv(f"{OUT}/fact_serie_diaria_cadena.csv")
serie_original["fecha_dia"] = pd.to_datetime(serie_original["fecha_dia"])
serie_estacional = serie_estacional.merge(
    serie_original[["fecha_dia", "n_tickets", "tasa_bebida"]], on="fecha_dia", how="left")
serie_estacional["fecha_dia"] = serie_estacional["fecha_dia"].astype(str)
serie_estacional.to_csv(f"{OUT}/fact_serie_diaria_cadena_estacional.csv", index=False)

print("\nIngreso total ORIGINAL (365 dias):", round(serie_original['ingreso_total_mxn'].sum(), 0))
print("Ingreso total CON estacionalidad declarada (365 dias):", round(serie_estacional['ingreso_total_mxn'].sum(), 0))
print("Diferencia:", round((serie_estacional['ingreso_total_mxn'].sum()/serie_original['ingreso_total_mxn'].sum()-1)*100, 2), "%")

# ---------------------------------------------------------------------------
# 4) Guardar KPIs actualizados del Modulo 1 (con estacionalidad)
# ---------------------------------------------------------------------------
kpis_m1_estacional = pd.DataFrame([
    {"modulo": "Modulo 1 - Demanda (con estacionalidad anual)", "modelo": n, "metrica": m, "valor": v}
    for n, mae, rmse, r2 in resultados
    for m, v in [("MAE_MXN", mae), ("RMSE_MXN", rmse), ("R2", r2)]
])
kpis_m1_estacional.to_csv(f"{OUT}/fact_kpis_modulo1_estacional.csv", index=False)
tabla_factor.to_csv(f"{OUT}/dim_factor_estacional.csv", index=False)
feat_imp_final.to_csv(f"{OUT}/fact_importancia_variables_m1_estacional.csv")

print("\nArchivos guardados:")
print(" - fact_serie_diaria_cadena_estacional.csv")
print(" - fact_kpis_modulo1_estacional.csv")
print(" - dim_factor_estacional.csv")
print(" - fact_importancia_variables_m1_estacional.csv")
