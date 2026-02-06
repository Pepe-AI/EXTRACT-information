"""
Script simple para probar segmentación V2
"""

import sys
import codecs

# Fix encoding
if sys.platform == "win32":
    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer, "replace")

# Texto de ejemplo de una escritura (simulado)
TEXTO_EJEMPLO = """
ESCRITURA NÚMERO 18226

En la ciudad de Tepic, Nayarit, a veintidós de marzo del año dos mil veinticuatro

NOTARIA PÚBLICA NÚMERO 10

NOTARIO: GUILLERMO LOZA RAMÍREZ

MUNICIPIO: BAHIA DE BANDERAS, NAYARIT

CLÁUSULA PRIMERA - COMPARECENCIA

Comparece el señor ANTONIO QUINTERO FLORES, quien manifiesta que ADQUIERE el inmueble.

Comparece la señora SILVIA SÁNCHEZ SÁNCHEZ, quien manifiesta que ADQUIERE el inmueble.

El TITULAR es DESARROLLO TURISTICO LOS COCOS, SOCIEDAD ANÓNIMA DE CAPITAL VARIABLE,
representado por HECTOR RAMÓN FLORES IBARRA en su calidad de Apoderado General.

CLÁUSULA SEGUNDA - OPERACIÓN

El inmueble se vende por la cantidad de $600,000.00 (SEISCIENTOS MIL PESOS 00/100 M.N.)

El valor catastral es de $435,000.00

PERSONALIDAD

El poder del representante consta en escritura número 63550 de fecha 15 de abril de 2020

GENERALES

DOY FE que identifiqué a los comparecientes:

ANTONIO QUINTERO FLORES, de 56 años de edad, casado, con RFC QUFA670718TK2
y CURP QUFA670718HJCNLN04

SILVIA SÁNCHEZ SÁNCHEZ, de 56 años de edad, casada, con RFC SASS680104FB7
y CURP SASS680104MJCNNL03

Los contratantes manifiestan estar casados bajo el régimen de sociedad conyugal.

FE NOTARIAL - Doy fe que los comparecientes se identificaron con credencial del INE.
"""

def main():
    print("="*80)
    print("PRUEBA DE SEGMENTACIÓN V2 - VERSIÓN SIMPLE")
    print("="*80)
    print()

    from extraction.segmentador_v2 import SegmentadorV2, obtener_seccion_para_campo
    from models.seccion_mapping import SeccionDocumento

    # Segmentar
    print("1. Segmentando documento...")
    segmentador = SegmentadorV2(min_confianza=0.5)
    resultado = segmentador.segmentar(TEXTO_EJEMPLO)

    print(f"   Usar fallback: {resultado.usar_fallback}")
    print(f"   Confianza: {resultado.confianza_general:.2f}")
    print(f"   Secciones: {len(resultado.secciones)}\n")

    # Mostrar secciones
    print("="*80)
    print("SECCIONES DETECTADAS")
    print("="*80)

    for seccion_tipo, seccion in resultado.secciones.items():
        print(f"\n{seccion_tipo.value.upper()}")
        print(f"  Posición: {seccion.inicio}-{seccion.fin}")
        print(f"  Longitud: {len(seccion.contenido)} chars")
        print(f"  Confianza: {seccion.confianza:.2f}")
        print(f"  Contenido: {seccion.contenido[:200]}...\n")

    # Prueba de búsqueda dirigida
    print("="*80)
    print("BÚSQUEDA DIRIGIDA POR CAMPO")
    print("="*80)

    campos_prueba = [
        "numero_escritura",
        "rfc",
        "monto_operacion",
    ]

    for campo in campos_prueba:
        texto = obtener_seccion_para_campo(resultado, campo)
        if texto == resultado.texto_completo:
            origen = "texto completo"
        else:
            origen = f"sección específica ({len(texto)} chars)"

        print(f"\n{campo}: {origen}")

    print("\n" + "="*80)

if __name__ == "__main__":
    main()
