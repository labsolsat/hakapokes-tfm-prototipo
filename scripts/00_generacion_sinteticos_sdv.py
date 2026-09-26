"""
00_generacion_sinteticos_sdv.py
================================
HakaPokes · TFM Equipo 4A — Generación de transacciones sintéticas

Implementación de referencia de la metodología descrita en el documento
final (sección "Generación de Datos Sintéticos y Análisis exploratorio
de datos (EDA)" → "Herramientas Utilizadas" / "Proceso Metodológico
para la Generación de Datos"), usando:

  - SDV (Synthetic Data Vault) → modela y genera el esqueleto tabular
    (sucursal, tamaño, hora, día, mes) preservando las correlaciones
    observadas en la muestra real disponible (~1 mes de operación).
  - Faker                      → genera metadatos de contexto (folio
    de transacción, timestamp coherente con el horario operativo).
  - Pandas / NumPy             → distribuciones estadísticas, reglas
    causales declaradas y agregaciones.
  - PyMongo                    → persistencia de las transacciones en
    MongoDB (colección `pedidos`), con caída a un archivo JSON local
    si no hay conexión disponible.

IMPORTANTE — TRANSPARENCIA METODOLÓGICA
----------------------------------------
Este script es la implementación documentada de cómo SE GENERARÍA el
conjunto sintético siguiendo las reglas ya declaradas y auditadas en
el resto del proyecto (ver scripts/exploracion_modulo2/ y la sección
"Reflexiones Finales y Aprendizajes" del documento). Ejecutarlo produce
una NUEVA muestra sintética (semilla aleatoria nueva) — no reproduce
bit a bit el archivo ya existente en data/raw/hakapokes_synthetic_
transactions.json, que es el que efectivamente alimenta todos los
resultados reportados (dashboard, Power BI, notebooks). Se publica
como evidencia reproducible del método, no para reemplazar el dataset
ya validado.

Las dos reglas causales declaradas que aplica (documentadas y
reentrenadas en el resto del pipeline):
  1. Variable objetivo "tiene_bebida" (Módulo 2):
     logit = 0.75 + 0.70*(tamano_num-2) + 0.55*es_hora_pico
             + 0.11*(temperatura-22) + 0.25*es_finde + ruido N(0, 0.9)
  2. Factor estacional anual declarado (Módulo 1):
     verano (15-jun a 31-ago) x1.12 · diciembre x1.20
     cuesta de enero (1-15 ene) x0.85 · semana santa (24-30 mar) x1.15
"""

import json
import math
import random
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
from faker import Faker
from sdv.metadata import SingleTableMetadata
from sdv.single_table import GaussianCopulaSynthesizer

# ---------------------------------------------------------------------
# Configuración general
# ---------------------------------------------------------------------
N_TRANSACCIONES = 500_000
SEMILLA = 42
FECHA_INICIO = datetime(2025, 6, 1)
FECHA_FIN = datetime(2026, 5, 31)
OUTPUT_JSON = "data/raw/hakapokes_synthetic_transactions_v2.json"
MONGO_URI = "mongodb://localhost:27017"
MONGO_DB = "hakapokes"
MONGO_COLLECTION = "pedidos"

random.seed(SEMILLA)
np.random.seed(SEMILLA)
fake = Faker("es_MX")
Faker.seed(SEMILLA)

# ---------------------------------------------------------------------
# Paso 1 — Parámetros extraídos de la muestra real (~1 mes de operación)
# ---------------------------------------------------------------------
# Frecuencias relativas por sucursal P(Sucursal), calibradas contra el
# histórico real (ver dim_sucursal en data/processed/).
SUCURSALES = {
    "Campanario": {"id": "SUC-CAMPANARIO", "peso": 0.2503},
    "Juriquilla": {"id": "SUC-JURIQUILLA", "peso": 0.2511},
    "El Refugio":  {"id": "SUC-REFUGIO",    "peso": 0.2007},
    "Centro Sur":  {"id": "SUC-CENTROSUR",  "peso": 0.1487},
    "Jurica":      {"id": "SUC-JURICA",     "peso": 0.1492},
}

# Distribución de tamaño de poke — Mediano domina (>50%), consistente
# con el EDA (Bloque 2).
TAMANOS = {
    "Chico":   {"num": 1, "peso": 0.30, "g_base": 150, "g_proteina": 30,
                "precio_solo": 135.0, "precio_combo": 170.0},
    "Mediano": {"num": 2, "peso": 0.52, "g_base": 200, "g_proteina": 60,
                "precio_solo": 185.0, "precio_combo": 220.0},
    "Grande":  {"num": 3, "peso": 0.18, "g_base": 300, "g_proteina": 90,
                "precio_solo": 235.0, "precio_combo": 270.0},
}

# Distribución horaria (peso relativo) — picos declarados en 13-15h y
# 18h, ventana operativa 10:00-21:00.
HORAS_OPERATIVAS = list(range(10, 22))
PESO_HORA = {
    10: 0.03, 11: 0.05, 12: 0.09, 13: 0.16, 14: 0.19, 15: 0.09,
    16: 0.05, 17: 0.05, 18: 0.12, 19: 0.07, 20: 0.06, 21: 0.04,
}
HORAS_PICO = {13, 14, 15, 18}

# Distribución por día de la semana — Lunes, Miércoles y Jueves lideran.
PESO_DIA_SEMANA = {
    0: 0.165, 1: 0.14, 2: 0.16, 3: 0.16, 4: 0.135, 5: 0.12, 6: 0.10,
}  # 0=Lunes ... 6=Domingo

# Catálogo simplificado de ingredientes por categoría (para bases,
# proteínas, toppings y salsas) — solo para poblar el documento anidado.
BASES = ["Arroz Blanco", "Arroz Integral", "Quinoa"]
PROTEINAS = ["Salmón", "Atún Aleta Azul", "Camarón", "Pollo Teriyaki", "Tofu"]
TOPPINGS = ["Aguacate", "Mango", "Edamame", "Pepino", "Jícama", "Zanahoria"]
SALSAS = ["Spicy Mayo", "Salsa de Soya", "Aceite de Ajonjolí", "Sriracha"]


def factor_estacional(fecha: datetime) -> float:
    """Factor estacional anual DECLARADO (misma regla usada para
    reentrenar el Módulo 1 — ver scripts/04_estacionalidad_modulo1.py).
    """
    mes, dia = fecha.month, fecha.day
    if (mes == 6 and dia >= 15) or mes in (7, 8):
        return 1.12  # verano
    if mes == 12:
        return 1.20  # diciembre
    if mes == 1 and dia <= 15:
        return 0.85  # cuesta de enero
    if mes == 3 and 24 <= dia <= 30:
        return 1.15  # semana santa (ilustrativo)
    return 1.00


def temperatura_sintetica(fecha: datetime) -> float:
    """Temperatura ambiente sintética para Querétaro: estacionalidad
    anual suave (más calor en verano, más frío en invierno) + ruido
    diario. Alimenta la regla causal declarada del Módulo 2.
    """
    dia_del_anio = fecha.timetuple().tm_yday
    media_anual = 19.0
    amplitud = 6.5
    # pico de calor a mediados de año (hemisferio norte)
    estacional = amplitud * math.sin(2 * math.pi * (dia_del_anio - 80) / 365)
    ruido = np.random.normal(0, 2.0)
    return round(media_anual + estacional + ruido, 1)


# ---------------------------------------------------------------------
# Paso 2 — SDV: modelar y generar el esqueleto tabular
# ---------------------------------------------------------------------
def construir_muestra_semilla(n: int = 5_000) -> pd.DataFrame:
    """Construye una muestra 'semilla' con las frecuencias relativas
    reales (Paso 1) para que SDV aprenda las correlaciones entre
    sucursal, tamaño, hora y día — en vez de generar cada variable de
    forma independiente.
    """
    sucursales = list(SUCURSALES.keys())
    pesos_suc = np.array([SUCURSALES[s]["peso"] for s in sucursales])
    pesos_suc = pesos_suc / pesos_suc.sum()
    tamanos = list(TAMANOS.keys())
    pesos_tam = np.array([TAMANOS[t]["peso"] for t in tamanos])
    pesos_tam = pesos_tam / pesos_tam.sum()
    horas = list(PESO_HORA.keys())
    pesos_hora = np.array(list(PESO_HORA.values()))
    pesos_hora = pesos_hora / pesos_hora.sum()
    dias = list(PESO_DIA_SEMANA.keys())
    pesos_dia = np.array(list(PESO_DIA_SEMANA.values()))
    pesos_dia = pesos_dia / pesos_dia.sum()

    filas = []
    for _ in range(n):
        sucursal = np.random.choice(sucursales, p=pesos_suc)
        tamano = np.random.choice(tamanos, p=pesos_tam)
        hora = int(np.random.choice(horas, p=pesos_hora))
        dia_semana = int(np.random.choice(dias, p=pesos_dia))
        # correlación real observada: Mediano/Grande pesan más en hora pico
        if hora in HORAS_PICO and tamano == "Chico" and np.random.rand() < 0.35:
            tamano = np.random.choice(["Mediano", "Grande"], p=[0.75, 0.25])
        filas.append({
            "sucursal": sucursal, "tamano": tamano,
            "hora": hora, "dia_semana": dia_semana,
        })
    return pd.DataFrame(filas)


def generar_esqueleto_sdv(n_transacciones: int) -> pd.DataFrame:
    """Entrena un GaussianCopulaSynthesizer de SDV sobre la muestra
    semilla y genera n_transacciones filas sintéticas que preservan
    las correlaciones sucursal↔tamaño↔hora↔día.
    """
    muestra = construir_muestra_semilla()

    metadata = SingleTableMetadata()
    metadata.detect_from_dataframe(muestra)
    metadata.update_column(column_name="sucursal", sdtype="categorical")
    metadata.update_column(column_name="tamano", sdtype="categorical")
    metadata.update_column(column_name="hora", sdtype="numerical")
    metadata.update_column(column_name="dia_semana", sdtype="numerical")

    sintetizador = GaussianCopulaSynthesizer(metadata)
    sintetizador.fit(muestra)
    esqueleto = sintetizador.sample(num_rows=n_transacciones)

    # SDV puede generar valores continuos para hora/día; se redondean
    # y se acotan a los dominios válidos.
    esqueleto["hora"] = esqueleto["hora"].round().clip(10, 21).astype(int)
    esqueleto["dia_semana"] = esqueleto["dia_semana"].round().clip(0, 6).astype(int)
    return esqueleto


# ---------------------------------------------------------------------
# Paso 3 — Reglas de negocio deterministas (receta y precio) +
# Paso 4 — Variable objetivo "tiene_bebida" bajo la regla causal declarada
# ---------------------------------------------------------------------
def aplicar_reglas_de_negocio(esqueleto: pd.DataFrame) -> pd.DataFrame:
    df = esqueleto.copy()

    # Fecha: se sortea un día del rango operativo ponderado por el
    # factor estacional declarado (Paso 5 se apoya en esta columna).
    rango_dias = (FECHA_FIN - FECHA_INICIO).days
    candidatos = [FECHA_INICIO + timedelta(days=i) for i in range(rango_dias + 1)]
    pesos_fecha = np.array([factor_estacional(f) for f in candidatos])
    pesos_fecha = pesos_fecha / pesos_fecha.sum()
    fechas_elegidas = np.random.choice(candidatos, size=len(df), p=pesos_fecha)
    df["fecha"] = fechas_elegidas
    df["mes"] = df["fecha"].apply(lambda f: f.month)
    df["temperatura"] = df["fecha"].apply(temperatura_sintetica)
    df["es_finde"] = df["dia_semana"].isin([5, 6]).astype(int)
    df["es_hora_pico"] = df["hora"].isin(HORAS_PICO).astype(int)

    # Receta estándar y descuento de inventario (determinista por tamaño)
    df["tamano_num"] = df["tamano"].map(lambda t: TAMANOS[t]["num"])
    df["gramos_base"] = df["tamano"].map(lambda t: TAMANOS[t]["g_base"])
    df["gramos_proteina"] = df["tamano"].map(lambda t: TAMANOS[t]["g_proteina"])

    # Regla causal declarada — Módulo 2 (idéntica a la usada para
    # reentrenar el clasificador real, ver exploracion_modulo2/03_
    # reconstruccion_causal_declarada.py)
    ruido = np.random.normal(0, 0.9, size=len(df))
    logit = (
        0.75
        + 0.70 * (df["tamano_num"] - 2)
        + 0.55 * df["es_hora_pico"]
        + 0.11 * (df["temperatura"] - 22)
        + 0.25 * df["es_finde"]
        + ruido
    )
    prob_bebida = 1 / (1 + np.exp(-logit))
    df["tiene_bebida"] = (np.random.rand(len(df)) < prob_bebida).astype(int)

    # Precio: base por tamaño + combo si tiene bebida
    df["precio_mxn"] = df.apply(
        lambda r: TAMANOS[r["tamano"]]["precio_combo"] if r["tiene_bebida"]
        else TAMANOS[r["tamano"]]["precio_solo"],
        axis=1,
    )
    return df


# ---------------------------------------------------------------------
# Paso 6 — Faker: folio, timestamp y ensamblado del documento JSON anidado
# ---------------------------------------------------------------------
def construir_documento(fila: pd.Series) -> dict:
    """Ensambla un documento JSON anidado idéntico en estructura al
    ejemplo documentado en la sección 'Formateo y Almacenamiento NoSQL
    (MongoDB)' del TFM.
    """
    fecha = fila["fecha"]
    hora = int(fila["hora"])
    minuto = random.randint(0, 59)
    segundo = random.randint(0, 59)
    timestamp = datetime(fecha.year, fecha.month, fecha.day, hora, minuto, segundo)

    folio = f"TXN-{timestamp:%Y%m%d}-{fake.unique.random_number(digits=6, fix_len=True)}"

    n_proteinas = int(np.random.choice([1, 2], p=[0.55, 0.45]))
    proteinas_elegidas = random.sample(PROTEINAS, k=n_proteinas)
    gramos_por_proteina = round(fila["gramos_proteina"] / n_proteinas, 1)

    n_toppings = np.random.randint(1, 4)
    toppings_elegidos = random.sample(TOPPINGS, k=n_toppings)

    sucursal_info = SUCURSALES[fila["sucursal"]]

    doc = {
        "id_transaccion": folio,
        "fecha_registro": timestamp.isoformat(),
        "id_sucursal": sucursal_info["id"],
        "nombre_sucursal": fila["sucursal"],
        "producto": {
            "categoria": "Poke Bowl",
            "tamano": fila["tamano"],
            "precio_mxn": float(fila["precio_mxn"]),
            "base": {
                "id_insumo": "BAS-001",
                "nombre": random.choice(BASES),
                "gramos_descuento": int(fila["gramos_base"]),
            },
            "proteinas": [
                {
                    "id_insumo": f"PRO-{i+1:03d}",
                    "nombre": p,
                    "categoria": "Mariscos" if p in ("Salmón", "Atún Aleta Azul", "Camarón") else "Proteína",
                    "gramos_descuento": gramos_por_proteina,
                }
                for i, p in enumerate(proteinas_elegidas)
            ],
            "num_proteinas_seleccionadas": n_proteinas,
            "gramos_totales_proteina": int(fila["gramos_proteina"]),
            "toppings": [
                {"id_insumo": f"TOP-{i+1:03d}", "nombre": t, "gramos_descuento": random.choice([20, 30, 35, 40])}
                for i, t in enumerate(toppings_elegidos)
            ],
            "salsas": (
                [{"id_insumo": "SAU-001", "nombre": random.choice(SALSAS), "mililitros_descuento": 30}]
                if fila["tiene_bebida"] or random.random() < 0.6 else []
            ),
        },
        # variable objetivo del Módulo 2, guardada explícitamente para
        # trazabilidad — generada bajo la regla causal declarada, no
        # de forma independiente.
        "tiene_bebida": bool(fila["tiene_bebida"]),
        "temperatura_c": float(fila["temperatura"]),
    }
    return doc


# ---------------------------------------------------------------------
# Paso 7 — Persistencia: MongoDB (PyMongo) con caída a JSON local
# ---------------------------------------------------------------------
def persistir(documentos: list[dict]) -> None:
    try:
        from pymongo import MongoClient

        cliente = MongoClient(MONGO_URI, serverSelectionTimeoutMS=2000)
        cliente.admin.command("ping")  # fuerza la validación de conexión
        coleccion = cliente[MONGO_DB][MONGO_COLLECTION]
        BATCH = 5_000
        for i in range(0, len(documentos), BATCH):
            coleccion.insert_many(documentos[i:i + BATCH])
        print(f"[MongoDB] {len(documentos):,} documentos insertados en "
              f"{MONGO_DB}.{MONGO_COLLECTION}")
    except Exception as err:  # sin MongoDB disponible -> respaldo a archivo
        print(f"[MongoDB no disponible: {err}] Guardando en {OUTPUT_JSON} …")
        with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
            json.dump(documentos, f, ensure_ascii=False, default=str)
        print(f"[Archivo] {len(documentos):,} documentos escritos en {OUTPUT_JSON}")


# ---------------------------------------------------------------------
# Orquestación principal
# ---------------------------------------------------------------------
def main():
    print(f"Generando {N_TRANSACCIONES:,} transacciones sintéticas "
          f"(SDV + Faker, semilla={SEMILLA}) …")

    esqueleto = generar_esqueleto_sdv(N_TRANSACCIONES)
    print(f"[SDV] Esqueleto tabular generado: {len(esqueleto):,} filas, "
          f"columnas {list(esqueleto.columns)}")

    df = aplicar_reglas_de_negocio(esqueleto)
    tasa_bebida = df["tiene_bebida"].mean()
    print(f"[Reglas causales] tasa de conversión a combo simulada: "
          f"{tasa_bebida:.2%} (referencia real: 75.02%)")

    print("[Faker] Ensamblando documentos JSON anidados …")
    documentos = [construir_documento(fila) for _, fila in df.iterrows()]

    persistir(documentos)
    print("Listo.")


if __name__ == "__main__":
    main()
