import requests
import json
import time


def get_nutrition_data(food_name):
    """
    Busca informacion nutricional de un alimento usando OpenFoodFacts.
    Devuelve un dict con nombre, calorias, proteinas, carbohidratos, grasas, etc.
    """
    headers = {
        "User-Agent": "EntrenadorAI/1.0 (alberto@arochal.dev)",
        "Accept": "application/json",
    }
    url = "https://world.openfoodfacts.org/cgi/search.pl"
    params = {
        "search_terms": food_name,
        "json": 1,
        "page_size": 2,
        "fields": "product_name,nutriments",
    }
    for attempt in range(3):
        try:
            resp = requests.get(url, params=params, headers=headers, timeout=20)
            if resp.status_code == 503 and attempt < 2:
                time.sleep(3 ** attempt)
                continue
            resp.raise_for_status()
            data = resp.json()
            break
        except Exception as e:
            if attempt < 2:
                time.sleep(3 ** attempt)
                continue
            return {"error": f"Error consultando OpenFoodFacts: {e}"}

    products = data.get("products", [])
    if not products:
        return {"error": f"No se encontro informacion para: {food_name}"}

    results = []
    for p in products[:2]:
        n = p.get("nutriments", {})
        per_100 = {
            "energia_kcal": round(n.get("energy-kcal_100g", 0)),
            "proteinas": round(n.get("proteins_100g", 0), 1),
            "carbohidratos": round(n.get("carbohydrates_100g", 0), 1),
            "azucares": round(n.get("sugars_100g", 0), 1),
            "grasas": round(n.get("fat_100g", 0), 1),
            "grasas_saturadas": round(n.get("saturated-fat_100g", 0), 1),
            "fibra": round(n.get("fiber_100g", 0), 1),
            "sal": round(n.get("salt_100g", 0), 2),
        }
        results.append({
            "nombre": p.get("product_name", "Desconocido"),
            "porcion_referencia": "100g",
            "nutrientes_por_100g": per_100,
        })

    return {"alimentos": results}


if __name__ == "__main__":
    import sys
    name = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "manzana"
    result = get_nutrition_data(name)
    print(json.dumps(result, indent=2, ensure_ascii=False))
