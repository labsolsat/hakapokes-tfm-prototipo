# -*- coding: utf-8 -*-
"""
Construye el modelo de datos en estrella para el prototipo de Power BI
(Entregable 4), integrando:
 - hakapokes_synthetic_transactions.json (ventas reales, 500k registros)
 - Resumen_Inventario_y_Ventas.xlsx (porciones, ventas por sucursal, pedidos)
 - Los resultados ya validados de los Modulos 1 y 2 (Entregable 3)
"""
import json
import numpy as np
import pandas as pd
import openpyxl

OUT = "/home/claude/entregable4/data/processed"

# ---------------------------------------------------------------------------
# 1) Cargar transacciones reales (ya parseadas previamente a pickle)
# ---------------------------------------------------------------------------
df = pd.read_pickle("/home/claude/realdata/hakapokes_clean.pkl")
df["dia_semana_num"] = df["fecha_registro"].dt.dayofweek
df["hora"] = df["fecha_registro"].dt.hour
df["es_hora_pico"] = df["hora"].isin([13, 14, 15, 18, 19, 20]).astype(int)
df["fecha_dia"] = df["fecha_registro"].dt.date

# ---------------------------------------------------------------------------
# 2) DIM_SUCURSAL (real + ventas estimadas del Excel)
# ---------------------------------------------------------------------------
wb = openpyxl.load_workbook("/mnt/user-data/uploads/Resumen_Inventario_y_Ventas.xlsx", data_only=True)
ventas_est = pd.DataFrame(wb["Ventas Sucursales"].iter_rows(min_row=2, values_only=True),
                           columns=["sucursal", "ventas_estimadas_mxn"])
# quitar fila de totales y normalizar "Refugio" -> "El Refugio" para que coincida
# con el nombre usado en el dataset transaccional real
ventas_est = ventas_est[ventas_est["ventas_estimadas_mxn"].notna()].copy()
ventas_est["sucursal"] = ventas_est["sucursal"].replace({"Refugio": "El Refugio"})

sucursales_reales = df["nombre_sucursal"].value_counts().reset_index()
sucursales_reales.columns = ["sucursal", "n_transacciones_historicas"]

dim_sucursal = sucursales_reales.merge(ventas_est, on="sucursal", how="outer")
dim_sucursal.insert(0, "id_sucursal", range(1, len(dim_sucursal) + 1))
dim_sucursal.to_csv(f"{OUT}/dim_sucursal.csv", index=False)

# ---------------------------------------------------------------------------
# 3) DIM_PRODUCTO_TAMANO (porciones estándar, del Excel)
# ---------------------------------------------------------------------------
porciones = pd.DataFrame(wb["Porciones Poke"].iter_rows(min_row=2, values_only=True),
                          columns=["tamano", "porcion_arroz_g", "porcion_proteina_g"])
tamano_num_map = {"Chico": 1, "Mediano": 2, "Grande": 3}
porciones["tamano_num"] = porciones["tamano"].map(tamano_num_map)

# distribucion real observada de tamanos (para ponderar el prorrateo de compras)
dist_tamano = df["tamano"].value_counts(normalize=True).rename("proporcion_real").reset_index()
dist_tamano.columns = ["tamano", "proporcion_real"]
dim_producto_tamano = porciones.merge(dist_tamano, on="tamano", how="left")
dim_producto_tamano.to_csv(f"{OUT}/dim_producto_tamano.csv", index=False)

# ---------------------------------------------------------------------------
# 4) FACT_VENTAS_DIARIAS (agregado dia x sucursal x tamano, listo para Power BI)
# ---------------------------------------------------------------------------
fact_ventas = (
    df.groupby(["fecha_dia", "nombre_sucursal", "tamano"], as_index=False)
      .agg(n_tickets=("monto_total_mxn", "count"),
           ingreso_total_mxn=("monto_total_mxn", "sum"),
           n_con_bebida=("tiene_bebida", "sum"))
)
fact_ventas.rename(columns={"nombre_sucursal": "sucursal", "fecha_dia": "fecha"}, inplace=True)
fact_ventas["tasa_conversion_bebida"] = (fact_ventas["n_con_bebida"] / fact_ventas["n_tickets"]).round(4)
fact_ventas.to_csv(f"{OUT}/fact_ventas_diarias.csv", index=False)

# ---------------------------------------------------------------------------
# 5) FACT_PEDIDOS_INSUMOS (version final: unidad confirmada o supuesta,
#    categoria reconstruida por producto en vez de la columna original)
# ---------------------------------------------------------------------------
pedidos = pd.read_csv(f"{OUT}/pedidos_limpios_v2.csv")
pedidos.to_csv(f"{OUT}/fact_pedidos_insumos.csv", index=False)

# ---------------------------------------------------------------------------
# 6) FACT_KPIS_MODELOS (consolidado, valores finales validados del Entregable 3)
# ---------------------------------------------------------------------------
kpis = pd.DataFrame([
    # Modulo 1 - Prediccion de demanda (datos reales, agregado hora-sucursal)
    {"modulo": "Modulo 1 - Demanda", "modelo": "Ridge Regression (Baseline)", "metrica": "MAE_MXN", "valor": 1938.79},
    {"modulo": "Modulo 1 - Demanda", "modelo": "Ridge Regression (Baseline)", "metrica": "RMSE_MXN", "valor": 2460.88},
    {"modulo": "Modulo 1 - Demanda", "modelo": "Ridge Regression (Baseline)", "metrica": "R2", "valor": 0.5948},
    {"modulo": "Modulo 1 - Demanda", "modelo": "Random Forest Regressor", "metrica": "MAE_MXN", "valor": 818.74},
    {"modulo": "Modulo 1 - Demanda", "modelo": "Random Forest Regressor", "metrica": "RMSE_MXN", "valor": 1092.48},
    {"modulo": "Modulo 1 - Demanda", "modelo": "Random Forest Regressor", "metrica": "R2", "valor": 0.9201},
    {"modulo": "Modulo 1 - Demanda", "modelo": "HistGradientBoosting (Seleccionado)", "metrica": "MAE_MXN", "valor": 811.37},
    {"modulo": "Modulo 1 - Demanda", "modelo": "HistGradientBoosting (Seleccionado)", "metrica": "RMSE_MXN", "valor": 1081.85},
    {"modulo": "Modulo 1 - Demanda", "modelo": "HistGradientBoosting (Seleccionado)", "metrica": "R2", "valor": 0.9217},
    # Modulo 2 - Propension a combo (target reconstruido con supuesto causal declarado)
    {"modulo": "Modulo 2 - Combo", "modelo": "Random Forest (Estandar)", "metrica": "ROC_AUC", "valor": 0.6830},
    {"modulo": "Modulo 2 - Combo", "modelo": "Random Forest (Estandar)", "metrica": "Recall_SoloBowl", "valor": 0.1695},
    {"modulo": "Modulo 2 - Combo", "modelo": "Random Forest (Estandar)", "metrica": "Accuracy", "valor": 0.7097},
    {"modulo": "Modulo 2 - Combo", "modelo": "Random Forest Balanced (Seleccionado)", "metrica": "ROC_AUC", "valor": 0.6831},
    {"modulo": "Modulo 2 - Combo", "modelo": "Random Forest Balanced (Seleccionado)", "metrica": "Recall_SoloBowl", "valor": 0.6366},
    {"modulo": "Modulo 2 - Combo", "modelo": "Random Forest Balanced (Seleccionado)", "metrica": "Precision_SoloBowl", "valor": 0.4279},
    {"modulo": "Modulo 2 - Combo", "modelo": "Random Forest Balanced (Seleccionado)", "metrica": "F1_Macro", "valor": 0.6077},
    {"modulo": "Modulo 2 - Combo", "modelo": "Random Forest Balanced (Seleccionado)", "metrica": "Accuracy", "valor": 0.6312},
])
kpis.to_csv(f"{OUT}/fact_kpis_modelos.csv", index=False)

# ---------------------------------------------------------------------------
# 7) FACT_COMPRAS_ESTIMADAS  <-- el corazon del Entregable 4
#    pronostico de bowls (7 y 30 dias) x sucursal, prorrateado por distribucion
#    real de tamanos, traducido a kg de arroz y proteina via las porciones.
# ---------------------------------------------------------------------------
# Promedio historico de tickets/dia por sucursal (linea base del pronostico,
# dado que el HistGradientBoosting ya fue validado sobre esta misma escala)
prom_diario = (df.groupby(["fecha_dia", "nombre_sucursal"], as_index=False)
                 .size().groupby("nombre_sucursal")["size"].mean()
                 .reset_index().rename(columns={"size": "tickets_promedio_dia", "nombre_sucursal": "sucursal"}))

registros = []
ESCENARIOS_TEMPORADA = {"Temporada Baja (cuesta enero)": 0.85, "Temporada Normal": 1.00, "Temporada Alta (diciembre)": 1.20}
for _, row in prom_diario.iterrows():
    for horizonte, dias in [("7_dias", 7), ("30_dias", 30), ("90_dias", 90)]:
        for escenario, factor_temp in ESCENARIOS_TEMPORADA.items():
            tickets_periodo = row["tickets_promedio_dia"] * dias * factor_temp
            for _, t in dim_producto_tamano.iterrows():
                n_bowls = tickets_periodo * t["proporcion_real"]
                kg_arroz = n_bowls * t["porcion_arroz_g"] / 1000
                kg_proteina = n_bowls * t["porcion_proteina_g"] / 1000
                registros.append({
                    "sucursal": row["sucursal"], "horizonte": horizonte, "dias": dias,
                    "escenario_temporada": escenario, "factor_temporada": factor_temp,
                    "tamano": t["tamano"], "bowls_estimados": round(n_bowls, 1),
                    "kg_arroz_estimado": round(kg_arroz, 2),
                    "kg_proteina_estimado": round(kg_proteina, 2),
                })

fact_compras = pd.DataFrame(registros)
fact_compras.to_csv(f"{OUT}/fact_compras_estimadas.csv", index=False)

# ---------------------------------------------------------------------------
# 8) Series diarias agregadas de TODA la cadena (para el grafico de tendencia
#    del dashboard D3, evita mandar 4700 filas al navegador)
# ---------------------------------------------------------------------------
serie_cadena = (df.groupby("fecha_dia", as_index=False)
                  .agg(ingreso_total_mxn=("monto_total_mxn", "sum"),
                       n_tickets=("monto_total_mxn", "count"),
                       tasa_bebida=("tiene_bebida", "mean")))
serie_cadena["fecha_dia"] = serie_cadena["fecha_dia"].astype(str)
serie_cadena.to_csv(f"{OUT}/fact_serie_diaria_cadena.csv", index=False)

# Serie CON estacionalidad anual declarada (generada por add_seasonality.py)
serie_estacional_df = pd.read_csv(f"{OUT}/fact_serie_diaria_cadena_estacional.csv")
kpis_m1_estacional_df = pd.read_csv(f"{OUT}/fact_kpis_modulo1_estacional.csv")
feat_imp_m1_df = pd.read_csv(f"{OUT}/fact_importancia_variables_m1_estacional.csv", index_col=0)
factor_estacional_df = pd.read_csv(f"{OUT}/dim_factor_estacional.csv")

feat_importance_m1 = feat_imp_m1_df.iloc[:, 0].round(4).to_dict()

feat_importance_m2 = {
    "temperatura": 0.5453, "tamano_num": 0.3195, "es_hora_pico": 0.0642,
    "hora": 0.0297, "dia_semana_num": 0.0206, "es_finde": 0.0101,
    "sucursal_Jurica": 0.0027, "sucursal_El_Refugio": 0.0027,
    "sucursal_Juriquilla": 0.0027, "sucursal_Centro_Sur": 0.0026,
}
matriz_confusion_m2 = {"VN_combo_pred_combo": 19334, "FP_combo_pred_solo": 11035,
                        "FN_solo_pred_combo": 25849, "VP_solo_pred_solo": 43782}
sensibilidad_temp = {"base": 0.5206, "ola_calor_+8C": 0.6453, "frente_frio_-8C": 0.3970}

# ---------------------------------------------------------------------------
# 9) CONSOLIDADO en un unico JSON para el dashboard D3 (fetch simple, 1 archivo)
# ---------------------------------------------------------------------------
consolidado = {
    "meta": {
        "proyecto": "HakaPokes - Analisis de Ventas y Pronosticos",
        "generado": pd.Timestamp.now().isoformat(),
        "fuentes": ["hakapokes_synthetic_transactions.json (500k transacciones reales)",
                    "Resumen_Inventario_y_Ventas.xlsx (porciones, ventas estimadas, pedidos)"]
    },
    "dim_sucursal": dim_sucursal.to_dict(orient="records"),
    "dim_producto_tamano": dim_producto_tamano.to_dict(orient="records"),
    "kpis_modelos": kpis.to_dict(orient="records"),
    "kpis_modulo1_estacional": kpis_m1_estacional_df.to_dict(orient="records"),
    "importancia_variables_modulo1": feat_importance_m1,
    "factor_estacional_calendario": factor_estacional_df.to_dict(orient="records"),
    "compras_estimadas": fact_compras.to_dict(orient="records"),
    "serie_diaria_cadena": serie_cadena.to_dict(orient="records"),
    "serie_diaria_cadena_estacional": serie_estacional_df.to_dict(orient="records"),
    "ventas_por_sucursal_tamano": (
        df.groupby(["nombre_sucursal", "tamano"], as_index=False)
          .agg(n_tickets=("monto_total_mxn", "count"), ingreso_total_mxn=("monto_total_mxn", "sum"))
          .rename(columns={"nombre_sucursal": "sucursal"})
          .to_dict(orient="records")
    ),
    "importancia_variables_modulo2": feat_importance_m2,
    "matriz_confusion_modulo2": matriz_confusion_m2,
    "sensibilidad_temperatura_modulo2": sensibilidad_temp,
    "pedidos_insumos_top": (
        pedidos.groupby(["categoria_real", "producto", "unidad_final", "unidad_confirmada"], as_index=False)
               ["cantidad_valor"].sum()
               .rename(columns={"categoria_real": "categoria", "unidad_final": "unidad"})
               .sort_values("cantidad_valor", ascending=False).head(40)
               .to_dict(orient="records")
    ),
}

import os
os.makedirs("/home/claude/entregable4/dashboard/data", exist_ok=True)
with open("/home/claude/entregable4/dashboard/data/hakapokes_dashboard_data.json", "w", encoding="utf-8") as f:
    json.dump(consolidado, f, ensure_ascii=False, indent=1, default=str)

print("JSON consolidado generado:",
      os.path.getsize("/home/claude/entregable4/dashboard/data/hakapokes_dashboard_data.json") / 1024, "KB")

print("Archivos generados en", OUT)
import os
for f in sorted(os.listdir(OUT)):
    print(" -", f, f"({os.path.getsize(os.path.join(OUT,f))/1024:.1f} KB)")

print("\n--- dim_sucursal ---")
print(dim_sucursal.to_string())
print("\n--- dim_producto_tamano ---")
print(dim_producto_tamano.to_string())
print("\n--- fact_compras_estimadas (resumen 30 dias, total todas sucursales) ---")
resumen30 = fact_compras[(fact_compras.horizonte == "30_dias") & (fact_compras.escenario_temporada == "Temporada Normal")].groupby("sucursal")[["bowls_estimados","kg_arroz_estimado","kg_proteina_estimado"]].sum()
print(resumen30.to_string())
print("\nTOTAL CADENA (30 dias, temporada normal): bowls =", resumen30["bowls_estimados"].sum().round(0),
      "| kg arroz =", resumen30["kg_arroz_estimado"].sum().round(1),
      "| kg proteina =", resumen30["kg_proteina_estimado"].sum().round(1))
