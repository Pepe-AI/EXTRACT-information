"""
tests/test_plan_z.py - Tests para el Plan Z (ABDF + E)

Ejecutar:
    cd extract_info_project
    python -m pytest tests/test_plan_z.py -v
    
O sin pytest:
    python -m tests.test_plan_z
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from models.confianza import (
    evaluar_calidad_extraccion,
    NivelResultado,
    NivelConfianza,
    campo_tiene_valor,
    identificar_campos_para_plan_e,
)
from utils.text_processing import (
    extraer_todos_regex,
    extraer_numero_notaria,
    extraer_nombre_notario,
)
from extraction.segmentador import segmentar_documento
from extraction.validador_cruzado import ValidadorCruzado
from extraction.plan_e_extractor import PlanEExtractor, ResultadoPlanE
from extraction.sistema_confianza import SistemaConfianza


# =============================================================================
# TEXTO DE PRUEBA
# =============================================================================

TEXTO_ESCRITURA_COMPLETA = """
ESCRITURA PÚBLICA NÚMERO 18,226

En la ciudad de Guadalajara, Jalisco, a los veintidós días del mes de marzo
del año dos mil veinticuatro, ante mí, Licenciado GUILLERMO LOZA RAMÍREZ,
Notario Público número 10, comparecen:

COMPARECEN:

PRIMERO.- Como PARTE VENDEDORA: DESARROLLO TURÍSTICO LOS COCOS, S.A. DE C.V.,
representada por el señor HÉCTOR RAMÓN FLORES IBARRA, en su calidad de 
apoderado general, según consta en escritura número 5,432.

SEGUNDO.- Como PARTE COMPRADORA: ANTONIO QUINTERO FLORES, mexicano, casado,
con RFC: QUFA670718TK2 y CURP: QUFA670718HJCNLN04.

ANTECEDENTES DE PROPIEDAD:

El inmueble objeto de esta operación fue adquirido mediante escritura
número 12,345 de fecha 15 de enero de 2020.

CLÁUSULAS:

PRIMERA.- OBJETO. El vendedor transmite la propiedad del inmueble ubicado
en Calle Principal 123, Colonia Centro.

SEGUNDA.- PRECIO. El precio de esta operación fue la cantidad de $600,000.00
(SEISCIENTOS MIL PESOS 00/100 MONEDA NACIONAL), que el comprador paga al
vendedor en este acto.

CERTIFICACIONES:

DOY FE de que los comparecientes tienen capacidad legal para este acto.
"""


# =============================================================================
# TESTS DE EVALUACIÓN DE CALIDAD
# =============================================================================

def test_evaluar_calidad_completa():
    """Test: Documento con todos los campos → COMPLETO"""
    datos = {
        "numero_escritura": 18226,
        "numero_notaria": 10,
        "nombre_notario": "GUILLERMO LOZA RAMÍREZ",
        "fecha_documento": "22 de marzo de 2024",
        "tipo_titular": "empresa",
        "titulares": [{"nombre": "DESARROLLO TURÍSTICO"}],
        "adquirientes": [{"nombre": "ANTONIO QUINTERO"}],
        "monto_operacion": "$600,000.00"
    }
    
    resultado = evaluar_calidad_extraccion(datos)
    
    assert resultado.success == True
    assert resultado.nivel == NivelResultado.COMPLETO
    assert resultado.campos_encontrados == 8
    print(f"✅ Test completo: {resultado.mensaje}")


def test_evaluar_calidad_critico():
    """Test: Documento con 0-1 campos → CRÍTICO"""
    datos = {
        "algo_irrelevante": "valor"
    }
    
    resultado = evaluar_calidad_extraccion(datos)
    
    assert resultado.success == False
    assert resultado.nivel == NivelResultado.CRITICO
    assert "No se pudo detectar datos" in resultado.mensaje
    print(f"✅ Test crítico: {resultado.mensaje}")


# =============================================================================
# TESTS DE PLAN E
# =============================================================================

def test_identificar_campos_para_plan_e():
    """Test: Identificar campos que necesitan Plan E"""
    datos_regex = {
        "numero_escritura": 18226,  # Regex lo encontró
        "monto_operacion": "$600,000.00",  # Regex lo encontró
    }
    
    datos_llm = {
        "numero_notaria": 45,  # LLM lo encontró pero es incorrecto
        "nombre_notario": "JUAN PÉREZ",  # LLM lo encontró
    }
    
    confianza = {
        "numero_escritura": NivelConfianza.ALTA,
        "monto_operacion": NivelConfianza.ALTA,
        "numero_notaria": NivelConfianza.BAJA,  # Baja confianza
        "nombre_notario": NivelConfianza.BAJA,  # Baja confianza
    }
    
    campos = identificar_campos_para_plan_e(datos_regex, datos_llm, confianza)
    
    # Solo debe incluir campos con BAJA confianza que no tiene regex
    assert "numero_notaria" in campos
    assert "nombre_notario" in campos
    assert "numero_escritura" not in campos  # Regex lo tiene
    assert len(campos) <= 3  # Máximo 3
    
    print(f"✅ Campos para Plan E: {campos}")


def test_plan_e_limpieza_respuesta():
    """Test: Limpieza de respuestas del Plan E"""
    from extraction.plan_e_extractor import PlanEExtractor
    
    # Mock del ollama_service (no lo necesitamos para este test)
    class MockOllama:
        pass
    
    extractor = PlanEExtractor(MockOllama())
    
    # Test número
    assert extractor._limpiar_respuesta("El número es 10", "numero_notaria") == 10
    assert extractor._limpiar_respuesta("45", "numero_notaria") == 45
    assert extractor._limpiar_respuesta("<think>pensando</think>10", "numero_notaria") == 10
    
    # Test monto
    assert extractor._limpiar_respuesta("$600,000.00", "monto_operacion") == "$600,000.00"
    assert extractor._limpiar_respuesta("600000", "monto_operacion") == "$600000"
    
    # Test nombre
    assert extractor._limpiar_respuesta("Lic. Juan Pérez García", "nombre_notario") == "JUAN PÉREZ GARCÍA"
    
    # Test no encontrado
    assert extractor._limpiar_respuesta("NO ENCONTRADO", "numero_notaria") is None
    assert extractor._limpiar_respuesta("No se encontró el dato", "numero_notaria") is None
    
    print("✅ Limpieza de respuestas Plan E funciona correctamente")


# =============================================================================
# TESTS DE SISTEMA DE CONFIANZA
# =============================================================================

def test_sistema_confianza_con_plan_e():
    """Test: Sistema de confianza integra Plan E correctamente"""
    
    datos_regex = {
        "numero_escritura": 18226,
        "monto_operacion": "$600,000.00",
    }
    
    datos_llm = {
        "nombre_notario": "JUAN PÉREZ",  # Incorrecto
        "tipo_titular": "empresa",
        "titulares": [{"nombre": "EMPRESA"}],
        "adquirientes": [{"nombre": "COMPRADOR"}],
        "fecha_documento": "22 de marzo",
    }
    
    # Simular resultado de Plan E que corrige el nombre
    resultados_plan_e = {
        "nombre_notario": ResultadoPlanE(
            campo="nombre_notario",
            valor="GUILLERMO LOZA RAMÍREZ",
            exito=True,
            validado_en_texto=True,
            tiempo_segundos=5.0
        )
    }
    
    # Validaciones (simular que nombre no se validó)
    validador = ValidadorCruzado(TEXTO_ESCRITURA_COMPLETA)
    validaciones = validador.validar_todos(datos_llm)
    
    # Consolidar
    sistema = SistemaConfianza()
    sistema.agregar_regex(datos_regex)
    sistema.agregar_llm(datos_llm)
    sistema.agregar_plan_e(resultados_plan_e)
    sistema.aplicar_validacion(validaciones)
    
    resultado = sistema.consolidar()
    
    # Verificar que Plan E corrigió el nombre
    assert resultado.datos.get("nombre_notario") == "GUILLERMO LOZA RAMÍREZ"
    assert resultado.origen.get("nombre_notario") == "plan_e"
    assert resultado.confianza.get("nombre_notario") == "alta"
    assert resultado.plan_e_activado == True
    assert "nombre_notario" in resultado.campos_mejorados_plan_e
    
    print(f"✅ Sistema de confianza con Plan E: OK")
    print(f"   Nombre corregido por Plan E: {resultado.datos.get('nombre_notario')}")


# =============================================================================
# TESTS DE INTEGRACIÓN
# =============================================================================

def test_flujo_completo_sin_plan_e():
    """Test: Flujo completo cuando no se necesita Plan E"""
    
    # Datos perfectos del regex
    datos_regex = extraer_todos_regex(TEXTO_ESCRITURA_COMPLETA)
    
    # Simular datos del LLM
    datos_llm = {
        "tipo_titular": "empresa",
        "titulares": [{"nombre": "DESARROLLO TURÍSTICO"}],
        "adquirientes": [{"nombre": "ANTONIO QUINTERO"}],
    }
    
    # Validar
    validador = ValidadorCruzado(TEXTO_ESCRITURA_COMPLETA)
    validaciones = validador.validar_todos({**datos_regex, **datos_llm})
    
    # Consolidar sin Plan E
    sistema = SistemaConfianza()
    sistema.agregar_regex(datos_regex)
    sistema.agregar_llm(datos_llm)
    sistema.aplicar_validacion(validaciones)
    
    resultado = sistema.consolidar()
    
    assert resultado.success == True
    assert resultado.plan_e_activado == False
    assert resultado.calidad_general >= 60
    
    print(f"✅ Flujo completo sin Plan E: OK")
    print(f"   Calidad: {resultado.calidad_general}%")


# =============================================================================
# EJECUTAR TESTS
# =============================================================================

def main():
    print("\n" + "=" * 60)
    print("TESTS DEL PLAN Z (ABDF + E)")
    print("=" * 60)
    
    tests = [
        # Evaluación de calidad
        test_evaluar_calidad_completa,
        test_evaluar_calidad_critico,
        
        # Plan E
        test_identificar_campos_para_plan_e,
        test_plan_e_limpieza_respuesta,
        
        # Sistema de confianza
        test_sistema_confianza_con_plan_e,
        
        # Integración
        test_flujo_completo_sin_plan_e,
    ]
    
    exitosos = 0
    fallidos = 0
    
    for test in tests:
        try:
            print(f"\n🧪 {test.__name__}...")
            test()
            exitosos += 1
        except AssertionError as e:
            print(f"❌ FALLÓ: {e}")
            fallidos += 1
        except Exception as e:
            print(f"❌ ERROR: {e}")
            fallidos += 1
    
    print("\n" + "=" * 60)
    print(f"RESULTADOS: {exitosos} exitosos, {fallidos} fallidos")
    print("=" * 60)
    
    return 0 if fallidos == 0 else 1


if __name__ == "__main__":
    sys.exit(main())