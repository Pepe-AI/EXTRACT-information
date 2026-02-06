"""
Prueba rápida de extracción de RFC, CURP, edad, tipo_sociedad
"""
import json
import sys
import codecs

# Fix encoding
if sys.platform == "win32":
    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer, "replace")

from app.extractor import EscrituraExtractor, ExtractionConfig

# Configuración
pdf_path = "ESCRITURA 18226 ANTONIO QUINTERO FLORES NOTARIA 10 NUEVO NAYARIT, NAYARIT_20240611140357 (2).pdf"

print("="*80)
print("PRUEBA RÁPIDA - Extracción de RFC, CURP, edad, tipo_sociedad")
print("="*80)
print(f"\nPDF: {pdf_path}\n")

# Crear extractor
config = ExtractionConfig(
    use_classification=True,
    use_plan_e=True,
    max_retries=3,  # 3 intentos para asegurar buena extracción
    temperature=0.0
)
extractor = EscrituraExtractor(config=config)

# Extraer
result = extractor.extract(pdf_path)

# Mostrar resultado
print("\n" + "="*80)
print("RESULTADO")
print("="*80)

if result.success:
    print(f"Status: EXITOSO")
    print(f"Calidad: {result.calidad_general}%")

    # Mostrar adquirientes
    if result.data and "adquirientes" in result.data:
        print("\n" + "-"*80)
        print("ADQUIRIENTES")
        print("-"*80)
        for i, adq in enumerate(result.data["adquirientes"], 1):
            print(f"\nAdquiriente {i}:")
            print(f"  Nombre: {adq.get('nombre', 'N/A')}")
            print(f"  RFC: {adq.get('rfc', 'N/A')}")
            print(f"  CURP: {adq.get('curp', 'N/A')}")
            print(f"  Edad: {adq.get('edad', 'N/A')}")
            print(f"  Estado civil: {adq.get('estado_civil', 'N/A')}")
            print(f"  Tipo sociedad: {adq.get('tipo_sociedad', 'N/A')}")

    # Validación
    print("\n" + "="*80)
    print("VALIDACIÓN")
    print("="*80)

    campos_validar = ["rfc", "curp", "edad", "tipo_sociedad", "estado_civil"]
    campos_encontrados = []
    campos_faltantes = []

    if result.data and "adquirientes" in result.data:
        for campo in campos_validar:
            encontrado = False
            for adq in result.data["adquirientes"]:
                valor = adq.get(campo)
                if valor not in [None, False, "", "N/A", "no encontrado"]:
                    campos_encontrados.append(f"{campo}={valor}")
                    encontrado = True
                    break
            if not encontrado:
                campos_faltantes.append(campo)

    if campos_encontrados:
        print(f"\nCAMPOS ENCONTRADOS ({len(campos_encontrados)}):")
        for campo in campos_encontrados:
            print(f"  - {campo}")

    if campos_faltantes:
        print(f"\nCAMPOS FALTANTES ({len(campos_faltantes)}):")
        for campo in campos_faltantes:
            print(f"  - {campo}")

    # Mostrar origen
    if result.origen:
        print("\nORIGEN DE LOS DATOS:")
        for campo in campos_validar:
            if campo in result.origen:
                print(f"  {campo}: {result.origen[campo]}")
else:
    print(f"Status: FALLIDO")
    print(f"Error: {result.error}")

print("\n" + "="*80)
print(f"Tiempo: {result.processing_time:.1f}s")
print("="*80)
