# -*- coding: utf-8 -*-
"""
Limpieza y estandarizacion de 'Pedidos por Fecha' (Resumen_Inventario_y_Ventas.xlsx)
Aplica las mismas reglas de calidad descritas en la seccion 2.2 del TFM
(Homogeneizacion de unidades, Estandarizacion de nombres/categorias,
Tratamiento de valores faltantes/desplazados, Validacion de consistencia).
"""
import re
import unicodedata
import openpyxl
import pandas as pd

WJ = "\u2060"  # word joiner invisible que aparece pegado a varios nombres

def strip_invisible(s):
    if s is None:
        return s
    return str(s).replace(WJ, "").strip()

def norm_key(s):
    """clave sin acentos/mayusculas para hacer match robusto"""
    s = strip_invisible(s).lower()
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    return s.strip()

# ---- Catalogo de categorias: clave normalizada -> categoria estandar ----
CAT_MAP = {
    "mariscos": "Mariscos",
    "abastos": "Abastos",
    "semillas": "Semillas",
    "desechables": "Desechables",
    "jarceria": "Limpieza",
    "otros": "Otros",
    "brownie": "Postres",
    "brownies": "Postres",
    "jugo de naranja": "Bebidas",
    "jugo naranja": "Bebidas",
    "happy water": "Bebidas",
}

# ---- Catalogo de productos: clave normalizada -> nombre estandar ----
PROD_MAP = {
    "atun nacional": "Atún Nacional", "atun importado": "Atún Importado",
    "camaron": "Camarón", "salmon": "Salmón", "pulpo": "Pulpo",
    "kanikama": "Kanikama", "masago": "Masago",
    "limon": "Limón", "pepino": "Pepino", "aguacate": "Aguacate",
    "cebolla": "Cebolla", "cebolla crujiente": "Cebolla Crujiente", "cebolla crunch": "Cebolla Crujiente",
    "chile de arbol": "Chile de Árbol", "chile jalapeno": "Chile Jalapeño", "chiles jalapeno": "Chile Jalapeño",
    "chipotle": "Chipotle", "cilantro": "Cilantro", "jengibre": "Jengibre",
    "jengibre sazonado": "Jengibre Sazonado", "jicama": "Jícama", "mango": "Mango",
    "pina": "Piña", "platanitos": "Platanitos", "zanahoria": "Zanahoria",
    "betabel": "Betabel", "fresa": "Fresa", "perejil": "Perejil",
    "arroz blanco": "Arroz Blanco", "arroz integral": "Arroz Integral", "quinoa": "Quinoa",
    "huevo": "Huevo", "germen": "Germen de Soya", "germen de soya": "Germen de Soya",
    "edamames": "Edamames", "alga nori": "Alga Nori", "seaweed": "Alga Nori (Seaweed)",
    "ajonjoli negro": "Ajonjolí Negro", "ajonjoli blanco": "Ajonjolí Blanco",
    "ajonjoli cremoso": "Ajonjolí Cremoso", "ajonjoli garapinado": "Ajonjolí Garapiñado",
    "girasol": "Girasol", "girasol garapinado": "Girasol Garapiñado",
    "almendra molida": "Almendra Molida", "furikake": "Furikake", "shichimi": "Shichimi",
    "coco": "Coco", "coco rayado": "Coco Rayado", "crema de coco": "Crema de Coco",
    "leche de coco": "Leche de Coco", "queso philadelphia": "Queso Philadelphia",
    "queso crema": "Queso Crema", "maracuya": "Maracuyá", "agua de coco": "Agua de Coco",
    "mayonesa": "Mayonesa", "mostaza dijon": "Mostaza Dijón", "miel": "Miel",
    "salsa macha": "Salsa Macha", "salsa maggie": "Salsa Maggi", "salsa de anguila": "Salsa de Anguila",
    "salsa de soya": "Salsa de Soya", "salsa inglesa": "Salsa Inglesa", "siracha": "Sriracha",
    "vinagre de arroz": "Vinagre de Arroz", "sake": "Sake", "sal": "Sal", "azucar": "Azúcar",
    "maicena": "Maicena", "aceite vegetal": "Aceite Vegetal", "aceite de ajonjoli": "Aceite de Ajonjolí",
    "aromatizante": "Aromatizante",
    "dumplig de pollo": "Dumpling de Pollo", "dumpling de pollo": "Dumpling de Pollo",
    "veggie dumpligs": "Veggie Dumplings", "veggie dumplings": "Veggie Dumplings",
    "yogurt natural": "Yogurt Natural", "yourt natural": "Yogurt Natural",
    "agua natural": "Agua Natural", "coca": "Coca-Cola", "coca light": "Coca-Cola Light",
    "horchata": "Horchata", "jamaica": "Agua de Jamaica",
    "obleas": "Obleas",
    "bowl": "Bowl (empaque)", "bowls grandes c/tapa": "Bowl Grande c/Tapa",
    "bowls medianos c/tapa": "Bowl Mediano c/Tapa", "suffles sin tapas": "Souflés sin Tapa",
    "tuppers para almacenar": "Tuppers para Almacenar", "vitafilm": "Vitafilm",
    "bolsa de papel to-go": "Bolsa de Papel To-Go", "bolsa de papel to-go chica": "Bolsa de Papel To-Go Chica",
    "rollo bolsas to-go": "Rollo Bolsas To-Go", "bolsa para basura flex-tech": "Bolsa para Basura",
    "servilletas": "Servilletas", "palillos": "Palillos", "tenedores desechables": "Tenedores Desechables",
    "scoop": "Scoop", "scoops": "Scoop",
    "cloro": "Cloro", "lysol": "Lysol", "pinol": "Pinol", "odoban citricos": "Odoban Cítricos",
    "limpiador de vidrios": "Limpiador de Vidrios", "jabon para manos": "Jabón para Manos",
    "papel de bano": "Papel de Baño", "sanitas": "Sanitas", "toalla en rollo": "Toalla en Rollo",
    "trapo amarillo": "Trapo Amarillo", "fibras": "Fibras",
    "guantes grandes": "Guantes Grandes", "guantes medianos": "Guantes Medianos",
}

QTY_RE = re.compile(r"([\d.,]+)\s*([a-zA-Zñíóá/]+)?")

def parse_qty(spec):
    spec = strip_invisible(spec)
    if not spec:
        return None, None
    m = QTY_RE.match(spec.replace(",", "."))
    if not m:
        return None, spec
    val = float(m.group(1)) if m.group(1) else None
    unit = (m.group(2) or "").lower().strip()
    unit_map = {"kg": "kg", "kgs": "kg", "l": "L", "litros": "L", "lts": "L", "lonjas": "lonjas",
                "pz": "pz", "pzas": "pz", "piezas": "pz", "ml": "ml", "g": "g", "gr": "g"}
    unit_std = unit_map.get(unit, unit if unit else None)
    return val, unit_std

def main():
    wb = openpyxl.load_workbook("/mnt/user-data/uploads/Resumen_Inventario_y_Ventas.xlsx", data_only=True)
    ws = wb["Pedidos por Fecha"]
    rows = list(ws.iter_rows(min_row=2, values_only=True))

    out = []
    fixes_desplazados = 0
    for fecha, categoria, producto, spec in rows:
        if fecha is None:
            continue
        cat_raw = strip_invisible(categoria)
        prod_raw = strip_invisible(producto)
        spec_raw = strip_invisible(spec)
        cat_key = norm_key(cat_raw)
        cat_std = CAT_MAP.get(cat_key, cat_raw)

        # Caso de columnas desplazadas: producto contiene una cantidad/talla en vez de un nombre
        prod_key = norm_key(prod_raw)
        if prod_key in ("15 pz", "15pz"):
            prod_std = "Brownies (paquete)"
            val, unit = 15.0, "pz"
            fixes_desplazados += 1
        elif prod_key in ("5.5 l", "5.5 litros", "5.5l"):
            prod_std = "Jugo de Naranja (garrafa)"
            val, unit = 5.5, "L"
            fixes_desplazados += 1
        else:
            prod_std = PROD_MAP.get(prod_key, prod_raw.title() if prod_raw else prod_raw)
            val, unit = parse_qty(spec_raw)

        out.append({
            "fecha": fecha,
            "categoria": cat_std,
            "producto": prod_std,
            "cantidad_valor": val,
            "cantidad_unidad": unit,
            "especificacion_original": spec_raw,
        })

    df = pd.DataFrame(out)
    df["fecha"] = pd.to_datetime(df["fecha"], format="%d %B %Y", errors="coerce")
    # fallback para locale en español si el parseo directo falla
    if df["fecha"].isna().any():
        meses = {"enero":1,"febrero":2,"marzo":3,"abril":4,"mayo":5,"junio":6,"julio":7,
                 "agosto":8,"septiembre":9,"octubre":10,"noviembre":11,"diciembre":12}
        def parse_es(s):
            try:
                d, m, y = s.split()
                return pd.Timestamp(year=int(y), month=meses[m.lower()], day=int(d))
            except Exception:
                return pd.NaT
        mask = df["fecha"].isna()
        raw_dates = [r["fecha"] for r in out]
        df.loc[mask, "fecha"] = [parse_es(raw_dates[i]) for i in df[mask].index]

    print("Filas totales:", len(df))
    print("Filas con columnas desplazadas corregidas:", fixes_desplazados)
    print("Categorias estandarizadas:", sorted(df["categoria"].unique()))
    print("Productos unicos tras estandarizar:", df["producto"].nunique(), "(antes: 137)")
    print("Fechas unicas:", df["fecha"].nunique(), "rango:", df["fecha"].min(), "->", df["fecha"].max())
    print("\nFilas con cantidad_valor nulo (revisar manualmente):")
    print(df[df["cantidad_valor"].isna()][["fecha","categoria","producto","especificacion_original"]].to_string())

    df.to_csv("/home/claude/entregable4/data/processed/pedidos_limpios.csv", index=False)
    print("\nGuardado: data/processed/pedidos_limpios.csv")

if __name__ == "__main__":
    main()
