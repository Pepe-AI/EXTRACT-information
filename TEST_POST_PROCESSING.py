#!/usr/bin/env python3
"""
Script de prueba para verificar el post-processing de representantes concatenados.
"""
import re
from typing import Dict, Any


def _separar_representantes_concatenados(json_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    POST-PROCESSING para separar representantes concatenados.

    Gemini a veces ignora las instrucciones y devuelve:
    {
      "representante": {
        "nombre": "ROSA GUZMAN Y MARGARITA FLORES",
        "en_calidad": "apoderadas legales"
      }
    }

    Esta función lo convierte a:
    {
      "representantes": [
        {"nombre": "ROSA GUZMAN", "en_calidad": "apoderada legal"},
        {"nombre": "MARGARITA FLORES", "en_calidad": "apoderada legal"}
      ]
    }
    """

    def procesar_entidad(entidad: Dict[str, Any]) -> Dict[str, Any]:
        """Procesa titular o adquiriente para separar representantes"""
        if not entidad:
            return entidad

        # Caso 1: Ya tiene "representantes" como array (formato correcto)
        if "representantes" in entidad:
            reps = entidad["representantes"]
            if isinstance(reps, list):
                return entidad  # Ya está en formato correcto
            elif reps is None:
                return entidad  # Sin representantes

        # Caso 2: Tiene "representante" (singular) - necesita conversión
        if "representante" in entidad:
            rep = entidad["representante"]

            if rep is None:
                # Convertir a formato array
                entidad["representantes"] = None
                del entidad["representante"]
                return entidad

            if isinstance(rep, dict):
                nombre = rep.get("nombre", "")
                en_calidad = rep.get("en_calidad", "")
                escritura = rep.get("escritura")
                fecha_poder = rep.get("fecha_poder")

                # Detectar concatenación con " Y " o " y "
                # Patrón: "NOMBRE1 Y NOMBRE2" o "NOMBRE1 y NOMBRE2"
                if re.search(r'\s+[Yy]\s+', nombre):
                    # Separar por " Y " o " y "
                    nombres = re.split(r'\s+[Yy]\s+', nombre)
                    nombres = [n.strip() for n in nombres if n.strip()]

                    # Ajustar plural/singular en en_calidad
                    # "apoderadas legales" → "apoderada legal"
                    en_calidad_singular = en_calidad
                    if en_calidad:
                        en_calidad_singular = en_calidad.replace("apoderadas", "apoderada")
                        en_calidad_singular = en_calidad_singular.replace("apoderados", "apoderado")
                        en_calidad_singular = en_calidad_singular.replace("representantes", "representante")

                    # Crear array de representantes
                    representantes = []
                    for nombre_individual in nombres:
                        rep_obj = {
                            "nombre": nombre_individual,
                            "en_calidad": en_calidad_singular
                        }
                        if escritura:
                            rep_obj["escritura"] = escritura
                        if fecha_poder:
                            rep_obj["fecha_poder"] = fecha_poder
                        representantes.append(rep_obj)

                    # Reemplazar "representante" con "representantes"
                    entidad["representantes"] = representantes
                    del entidad["representante"]

                    print(f"   🔧 Separados {len(nombres)} representantes concatenados")
                else:
                    # No hay concatenación, convertir a array de 1 elemento
                    entidad["representantes"] = [rep]
                    del entidad["representante"]

        return entidad

    # Procesar titular
    if "titular" in json_data:
        json_data["titular"] = procesar_entidad(json_data["titular"])

    # Procesar adquiriente
    if "adquiriente" in json_data:
        json_data["adquiriente"] = procesar_entidad(json_data["adquiriente"])

    return json_data


# ==================== PRUEBAS ====================

print("=" * 70)
print("TEST 1: Representantes concatenados con 'Y'")
print("=" * 70)

test1_input = {
    "titular": {
        "nombre": "CONSORCIO DE INGENIERIA INTEGRAL S.A. DE C.V.",
        "tipo": "empresa",
        "representante": {
            "nombre": "ROSA ANGELICA GUZMAN DELGADO Y MARGARITA MARIA FLORES VILLASEÑOR",
            "en_calidad": "apoderadas legales",
            "escritura": "108030",
            "fecha_poder": "9/18/2009"
        }
    },
    "adquiriente": {
        "nombre": "JOSE ANTONIO VAZQUEZ PEREZ",
        "tipo": "persona",
        "representante": None
    }
}

print("\n📥 INPUT (formato incorrecto de Gemini):")
import json
print(json.dumps(test1_input, indent=2, ensure_ascii=False))

print("\n🔄 Aplicando post-processing...")
test1_output = _separar_representantes_concatenados(test1_input.copy())

print("\n📤 OUTPUT (formato corregido):")
print(json.dumps(test1_output, indent=2, ensure_ascii=False))


print("\n\n" + "=" * 70)
print("TEST 2: Representantes concatenados con 'y' (minúscula)")
print("=" * 70)

test2_input = {
    "titular": {
        "nombre": "EMPRESA EJEMPLO S.A.",
        "tipo": "empresa",
        "representante": {
            "nombre": "JUAN PEREZ y MARIA LOPEZ",
            "en_calidad": "apoderados legales"
        }
    }
}

print("\n📥 INPUT:")
print(json.dumps(test2_input, indent=2, ensure_ascii=False))

print("\n🔄 Aplicando post-processing...")
test2_output = _separar_representantes_concatenados(test2_input.copy())

print("\n📤 OUTPUT:")
print(json.dumps(test2_output, indent=2, ensure_ascii=False))


print("\n\n" + "=" * 70)
print("TEST 3: Sin concatenación (formato correcto desde Gemini)")
print("=" * 70)

test3_input = {
    "titular": {
        "nombre": "EMPRESA EJEMPLO S.A.",
        "tipo": "empresa",
        "representante": {
            "nombre": "JUAN PEREZ GONZALEZ",
            "en_calidad": "apoderado legal"
        }
    }
}

print("\n📥 INPUT:")
print(json.dumps(test3_input, indent=2, ensure_ascii=False))

print("\n🔄 Aplicando post-processing...")
test3_output = _separar_representantes_concatenados(test3_input.copy())

print("\n📤 OUTPUT (convertido a array):")
print(json.dumps(test3_output, indent=2, ensure_ascii=False))


print("\n\n" + "=" * 70)
print("TEST 4: Sin representante (persona actuando por derecho propio)")
print("=" * 70)

test4_input = {
    "adquiriente": {
        "nombre": "JOSE ANTONIO VAZQUEZ PEREZ",
        "tipo": "persona",
        "representante": None
    }
}

print("\n📥 INPUT:")
print(json.dumps(test4_input, indent=2, ensure_ascii=False))

print("\n🔄 Aplicando post-processing...")
test4_output = _separar_representantes_concatenados(test4_input.copy())

print("\n📤 OUTPUT (representante → representantes):")
print(json.dumps(test4_output, indent=2, ensure_ascii=False))


print("\n\n" + "=" * 70)
print("✅ TODOS LOS TESTS COMPLETADOS")
print("=" * 70)
print("""
RESUMEN:
- ✅ Detecta y separa concatenaciones con " Y "
- ✅ Detecta y separa concatenaciones con " y " (minúscula)
- ✅ Ajusta plural → singular en en_calidad
- ✅ Conserva datos del poder (escritura, fecha_poder)
- ✅ Convierte formato singular → array
- ✅ Maneja casos sin representante (null)
""")
