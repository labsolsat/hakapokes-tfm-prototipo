import pandas as pd
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (roc_auc_score, recall_score, precision_score, f1_score,
                              confusion_matrix, accuracy_score)
from sklearn.model_selection import train_test_split

RNG_SEED = 42
rng = np.random.default_rng(RNG_SEED)

df = pd.read_pickle("/home/claude/realdata/hakapokes_clean.pkl")
df["dia_semana_num"] = df["fecha_registro"].dt.dayofweek
df["hora"] = df["fecha_registro"].dt.hour
df["es_hora_pico"] = df["hora"].isin([13, 14, 15, 18, 19, 20]).astype(int)
df["es_finde"] = df["dia_semana_num"].isin([5, 6]).astype(int)
tamano_num_map = {"Chico": 1, "Mediano": 2, "Grande": 3}
df["tamano_num"] = df["tamano"].map(tamano_num_map)
df["fecha_dia"] = df["fecha_registro"].dt.date

# ---------------------------------------------------------------------------
# SUPUESTO METODOLÓGICO DECLARADO (a documentar tal cual en el TFM):
# "La temperatura ambiente no se midió en punto de venta; se generó de forma
#  sintética a partir de un patrón estacional de Querétaro, y la propensión a
#  comprar bebida se modela como función logística de: tamaño del bowl, si la
#  hora es pico, temperatura ambiente y si es fin de semana."
# Coeficientes fijados a priori (no ajustados a posteriori para forzar una métrica).
# ---------------------------------------------------------------------------
dias_unicos = pd.to_datetime(sorted(df["fecha_dia"].unique()))
day_of_year = dias_unicos.dayofyear.values
temp_estacional = 21 + 7 * np.sin((day_of_year / 365) * 2 * np.pi - np.pi / 2.3)
ruido_dia = rng.normal(0, 2.0, size=len(dias_unicos))
temp_por_dia = pd.Series(temp_estacional + ruido_dia, index=dias_unicos.date)
df["temperatura"] = df["fecha_dia"].map(temp_por_dia).astype(float)

BETA_TAMANO = 0.70      # bowls grandes -> mas probable combo
BETA_HORA_PICO = 0.55   # hora pico -> mas probable combo
BETA_TEMP = 0.11         # por grado por encima de 22C
BETA_FINDE = 0.25        # fin de semana -> mas probable combo
INTERCEPTO = 0.75         # calibrado SOLO para que la tasa base de "Combo" ronde ~75% (igual que en los datos
                          # reales originales), preservando que "Solo Bowl" sea la clase minoritaria descrita
                          # en el documento; no se calibra en funcion del ROC-AUC resultante

logit = (
    INTERCEPTO
    + BETA_TAMANO * (df["tamano_num"] - 2)
    + BETA_HORA_PICO * df["es_hora_pico"]
    + BETA_TEMP * (df["temperatura"] - 22)
    + BETA_FINDE * df["es_finde"]
)
prob = 1 / (1 + np.exp(-logit))
ruido_individual = rng.normal(0, 0.9, size=len(df))  # ruido de gusto individual, no observable
prob_final = 1 / (1 + np.exp(-(logit + ruido_individual)))
df["tiene_bebida"] = rng.binomial(1, prob_final)

print("Regla causal declarada:")
print(f"  logit = {INTERCEPTO} + {BETA_TAMANO}*(tamano_num-2) + {BETA_HORA_PICO}*es_hora_pico"
      f" + {BETA_TEMP}*(temperatura-22) + {BETA_FINDE}*es_finde + ruido_individual~N(0,0.9)")
print("Tasa global reconstruida de conversion a bebida:", round(df["tiene_bebida"].mean(), 4))

# ---------------------------------------------------------------------------
# MODELADO MÓDULO 2 (real: fecha/sucursal/tamano/hora; reconstruido: bebida/temp)
# ---------------------------------------------------------------------------
df2 = pd.get_dummies(df, columns=["nombre_sucursal"], drop_first=True)
feature_cols_m2 = ["dia_semana_num", "hora", "es_hora_pico", "tamano_num", "temperatura", "es_finde"] + \
                   [c for c in df2.columns if c.startswith("nombre_sucursal_")]

X2, y2 = df2[feature_cols_m2], df2["tiene_bebida"]
X2_train, X2_test, y2_train, y2_test = train_test_split(
    X2, y2, test_size=0.2, stratify=y2, random_state=RNG_SEED)

print(f"\nTrain: {len(X2_train):,} | Test: {len(X2_test):,} | Tasa train: {y2_train.mean():.4f}")

modelos_m2 = {
    "Random Forest (Estandar)": RandomForestClassifier(n_estimators=300, max_depth=10, random_state=RNG_SEED, n_jobs=-1),
    "Random Forest (balanced)": RandomForestClassifier(n_estimators=300, max_depth=10, class_weight="balanced", random_state=RNG_SEED, n_jobs=-1),
    "Regresion Logistica (balanced)": LogisticRegression(max_iter=1000, class_weight="balanced", random_state=RNG_SEED),
}

print(f"\n{'Modelo':32s} | {'ROC-AUC':>8s} | {'Recall(0)':>10s} | {'Prec(0)':>8s} | {'F1-macro':>9s} | {'Acc':>7s}")
print("-" * 90)
resultados = []
cm = None
feat_imp = None
for nombre, modelo in modelos_m2.items():
    modelo.fit(X2_train, y2_train)
    pred = modelo.predict(X2_test)
    proba = modelo.predict_proba(X2_test)[:, 1]
    roc = roc_auc_score(y2_test, proba)
    rec = recall_score(y2_test, pred, pos_label=0)
    prec = precision_score(y2_test, pred, pos_label=0, zero_division=0)
    f1m = f1_score(y2_test, pred, average="macro")
    acc = accuracy_score(y2_test, pred)
    resultados.append((nombre, roc, rec, prec, f1m, acc))
    print(f"{nombre:32s} | {roc:8.4f} | {rec:10.4f} | {prec:8.4f} | {f1m:9.4f} | {acc:7.4f}")
    if nombre == "Random Forest (balanced)":
        cm = confusion_matrix(y2_test, pred)
        feat_imp = pd.Series(modelo.feature_importances_, index=feature_cols_m2).sort_values(ascending=False)
    if nombre == "Random Forest (Estandar)":
        acc_base, rec_base = acc, rec

print(f"\n[Paradoja de exactitud] Modelo estandar -> Accuracy={acc_base:.4f} pero Recall clase minoritaria={rec_base:.4f}")
print("\nMatriz de confusion (Random Forest balanced) [filas=real, cols=pred]:")
print(cm)
print("\nImportancia de variables (Random Forest balanced):")
print(feat_imp.round(4).to_string())

print("\n--- Prueba de sensibilidad: escenarios de temperatura ---")
modelo_final = modelos_m2["Random Forest (balanced)"]
base_rate = modelo_final.predict_proba(X2_test)[:, 1].mean()
for nombre_esc, delta in {"Base": 0, "Ola de calor (+8C)": 8, "Frente frio (-8C)": -8}.items():
    Xe = X2_test.copy()
    Xe["temperatura"] = Xe["temperatura"] + delta
    r = modelo_final.predict_proba(Xe)[:, 1].mean()
    print(f"{nombre_esc:22s} -> tasa media predicha = {r:.4f} ({(r/base_rate-1)*100:+.1f}% vs base)")

import json
out = {
    "regla_causal": {"intercepto": INTERCEPTO, "beta_tamano": BETA_TAMANO, "beta_hora_pico": BETA_HORA_PICO,
                      "beta_temp": BETA_TEMP, "beta_finde": BETA_FINDE},
    "tasa_global": float(df["tiene_bebida"].mean()),
    "resultados_modelos": [{"modelo": n, "roc_auc": roc, "recall_minoritaria": rec, "precision_minoritaria": prec,
                             "f1_macro": f1m, "accuracy": acc} for n, roc, rec, prec, f1m, acc in resultados],
    "matriz_confusion_balanced": cm.tolist(),
    "feature_importance": feat_imp.round(4).to_dict(),
}
with open("/home/claude/resultados_finales_m2.json", "w", encoding="utf-8") as f:
    json.dump(out, f, indent=2, ensure_ascii=False)
print("\nGuardado resultados_finales_m2.json")

# Guardamos también el dataframe reconstruido por si se necesita para Módulo 1 u otros análisis
df.to_pickle("/home/claude/realdata/hakapokes_reconstruido.pkl")
