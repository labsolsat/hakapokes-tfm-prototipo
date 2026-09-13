# -*- coding: utf-8 -*-
"""
Cierra el tema de unidades ambiguas en 'Pedidos por Fecha':
 - Asigna una unidad SUPUESTA (no inventada al azar: criterio de compra
   estandar de food-service) a cada producto sin unidad explicita.
 - Marca unidad_confirmada=False en todos estos casos, para que en Power BI
   / el dashboard se pueda filtrar o resaltar lo que falta validar con compras.
 - Reconstruye una 'categoria_real' a partir del PRODUCTO (no de la columna
   'categoria' original, que resulto no ser confiable).
"""
import pandas as pd
import unicodedata

def norm(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii","ignore").decode("ascii")
    return s.lower().strip()

# ---- Grupos de productos -> (categoria_real, unidad_supuesta) ----
GRUPOS = {
    # Bebidas embotelladas/enlatadas listas para servir -> pieza
    "coca-cola": ("Bebidas Embotelladas", "pza"),
    "coca-cola light": ("Bebidas Embotelladas", "pza"),
    "agua natural": ("Bebidas Embotelladas", "pza"),
    "agua de coco": ("Bebidas Embotelladas", "pza"),

    # Concentrados/pulpa para aguas frescas preparadas en sucursal -> litros
    "horchata": ("Insumos para Bebidas Preparadas", "L"),
    "agua de jamaica": ("Insumos para Bebidas Preparadas", "L"),
    "maracuya": ("Insumos para Bebidas Preparadas", "L"),

    # Alimentos solidos / semillas / especias / vegetales / proteinas -> kg
    "arroz blanco": ("Abastos - Granos", "kg"),
    "arroz integral": ("Abastos - Granos", "kg"),
    "quinoa": ("Abastos - Granos", "kg"),
    "jengibre": ("Abastos - Vegetales", "kg"),
    "jengibre sazonado": ("Abastos - Vegetales", "kg"),
    "limon": ("Abastos - Vegetales", "kg"),
    "jicama": ("Abastos - Vegetales", "kg"),
    "pina": ("Abastos - Vegetales", "kg"),
    "mango": ("Abastos - Vegetales", "kg"),
    "fresa": ("Abastos - Vegetales", "kg"),
    "coco": ("Abastos - Vegetales", "kg"),
    "coco rayado": ("Semillas y Toppings", "kg"),
    "cebolla crujiente": ("Semillas y Toppings", "kg"),
    "ajonjoli cremoso": ("Semillas y Toppings", "kg"),
    "alga nori": ("Semillas y Toppings", "kg"),
    "alga nori (seaweed)": ("Semillas y Toppings", "kg"),
    "furikake": ("Semillas y Toppings", "kg"),
    "shichimi": ("Semillas y Toppings", "kg"),
    "sriracha": ("Salsas y Condimentos", "L"),
    "platanitos": ("Semillas y Toppings", "kg"),
    "germen de soya": ("Abastos - Vegetales", "kg"),
    "edamames": ("Mariscos y Proteinas", "kg"),
    "kanikama": ("Mariscos y Proteinas", "kg"),
    "masago": ("Mariscos y Proteinas", "kg"),
    "pulpo": ("Mariscos y Proteinas", "kg"),
    "chipotle": ("Salsas y Condimentos", "kg"),

    # Lacteos / cremosos -> kg o L segun consistencia
    "queso crema": ("Abastos - Lacteos", "kg"),
    "queso philadelphia": ("Abastos - Lacteos", "kg"),
    "leche de coco": ("Abastos - Lacteos", "L"),
    "crema de coco": ("Abastos - Lacteos", "L"),
    "yogurt natural": ("Abastos - Lacteos", "L"),

    # Salsas, aceites, vinagres liquidos -> litros
    "salsa macha": ("Salsas y Condimentos", "L"),
    "salsa maggi": ("Salsas y Condimentos", "L"),
    "salsa de soya": ("Salsas y Condimentos", "L"),
    "salsa inglesa": ("Salsas y Condimentos", "L"),
    "mayonesa": ("Salsas y Condimentos", "L"),
    "mostaza dijon": ("Salsas y Condimentos", "L"),
    "vinagre de arroz": ("Salsas y Condimentos", "L"),
    "aceite vegetal": ("Salsas y Condimentos", "L"),
    "aceite de ajonjoli": ("Salsas y Condimentos", "L"),
    "sake": ("Salsas y Condimentos", "L"),
    "maicena": ("Abastos - Granos", "kg"),
    "sal": ("Abastos - Granos", "kg"),
    "aromatizante": ("Limpieza", "L"),

    # Congelados empacados -> paquete
    "dumpling de pollo": ("Congelados", "paquete"),
    "veggie dumplings": ("Congelados", "paquete"),

    # Quimicos de limpieza liquidos -> litros
    "cloro": ("Limpieza", "L"),
    "lysol": ("Limpieza", "L"),
    "pinol": ("Limpieza", "L"),
    "odoban citricos": ("Limpieza", "L"),
    "limpiador de vidrios": ("Limpieza", "L"),
    "jabon para manos": ("Limpieza", "L"),

    # Papel / desechables por pieza o paquete
    "servilletas": ("Desechables - Papel", "paquete"),
    "papel de bano": ("Desechables - Papel", "paquete"),
    "sanitas": ("Desechables - Papel", "paquete"),
    "toalla en rollo": ("Desechables - Papel", "paquete"),
    "palillos": ("Desechables - Papel", "paquete"),
    "tenedores desechables": ("Desechables - Papel", "paquete"),
    "vitafilm": ("Desechables - Papel", "paquete"),
    "bolsa para basura": ("Desechables - Papel", "paquete"),
    "bolsa de papel to-go": ("Desechables - Papel", "paquete"),
    "bolsa de papel to-go chica": ("Desechables - Papel", "paquete"),
    "rollo bolsas to-go": ("Desechables - Papel", "paquete"),
    "obleas": ("Desechables - Papel", "paquete"),
    "scoop": ("Utensilios", "pza"),
    "guantes grandes": ("Utensilios", "paquete"),
    "guantes medianos": ("Utensilios", "paquete"),
    "trapo amarillo": ("Utensilios", "pza"),
    "fibras": ("Utensilios", "pza"),
    "tuppers para almacenar": ("Utensilios", "pza"),
    "bowl grande c/tapa": ("Utensilios", "pza"),
    "bowl mediano c/tapa": ("Utensilios", "pza"),
    "souffles sin tapa": ("Utensilios", "pza"),
}

def main():
    df = pd.read_csv("/home/claude/entregable4/data/processed/pedidos_limpios.csv")
    df["unidad_confirmada"] = df["cantidad_unidad"].notna()
    df["categoria_real"] = None
    df["unidad_final"] = df["cantidad_unidad"]

    sin_asignar = []
    for i, row in df[df["cantidad_unidad"].isna()].iterrows():
        key = norm(row["producto"])
        if key in GRUPOS:
            cat, unidad = GRUPOS[key]
            df.at[i, "categoria_real"] = cat
            df.at[i, "unidad_final"] = unidad
        else:
            sin_asignar.append(row["producto"])

    # Para las filas que SI tenian unidad explicita, tambien les damos una
    # categoria_real razonable a partir del producto (consistencia del catalogo)
    mask_con_unidad = df["cantidad_unidad"].notna()
    for i, row in df[mask_con_unidad].iterrows():
        key = norm(row["producto"])
        if key in GRUPOS:
            df.at[i, "categoria_real"] = GRUPOS[key][0]
    df["categoria_real"] = df["categoria_real"].fillna(df["categoria"])

    print("Productos sin grupo asignado (revisar manualmente):", sorted(set(sin_asignar)))
    print("\nTotal filas:", len(df))
    print("Unidad confirmada (venia explicita en el Excel):", df.unidad_confirmada.sum())
    print("Unidad supuesta (asignada por criterio de compra estandar):", (~df.unidad_confirmada).sum())

    df.to_csv("/home/claude/entregable4/data/processed/pedidos_limpios_v2.csv", index=False)
    print("\nGuardado: pedidos_limpios_v2.csv")

    # resumen final por producto, con bandera de confianza
    resumen = (df.groupby(["categoria_real","producto","unidad_final","unidad_confirmada"], as_index=False)
                 ["cantidad_valor"].sum()
                 .sort_values("cantidad_valor", ascending=False))
    resumen.to_csv("/home/claude/entregable4/data/processed/resumen_insumos_final.csv", index=False)
    print("Guardado: resumen_insumos_final.csv (", len(resumen), "filas )")

if __name__ == "__main__":
    main()
