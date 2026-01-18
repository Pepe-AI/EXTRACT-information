#!/usr/bin/env python3
"""
tests/test_01_escritura.py - Prueba de modelos Pydantic

Prueba:
- Modelo ESTRICTO (EscrituraPublica)
- Modelo FLEXIBLE (EscrituraPublicaFlexible)
- Validación flexible con datos incompletos
- Generación de reportes
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from models.escritura import (
    # Modelos estrictos
    EscrituraPublica,
    Notario,
    Titular,
    Adquiriente,
    Representante,

    # Modelos flexibles
    EscrituraPublicaFlexible,
    TitularFlexible,
    AdquirienteFlexible,
    RepresentanteFlexible,
    
    # Funciones
    validar_json_flexible,
    generar_feedback_error,
    get_campos_obligatorios,
    get_campos_no_obligatorios,
    NO_ENCONTRADO
)


def test_modelo_estricto_completo():
    """Prueba 1: Modelo estricto con todos los datos."""
    print("\n" + "="*60)
    print("PRUEBA 1: Modelo ESTRICTO completo")
    print("="*60)
    
    escritura = EscrituraPublica(
        notario=[
            Notario(
                nombre="Lic. Roberto García",
                numero_notario="45",
                municipio="Ciudad de México",
                escritura="3125",
                fecha_documento="15 de mayo de 2024"
            )
        ],
        numero_escritura=3125,
        fecha_documento="15 de mayo de 2024",
        tipo_titular="empresa",
        titulares=[
            Titular(
                nombre="Inmobiliaria ABC S.A. de C.V.",
                actua_por="derecho propio",
                representante=Representante(
                    nombre="Juan Pérez",
                    en_calidad="apoderado legal",
                    escritura="1234",
                    bis=False,
                    fecha_poder="10/01/2020"
                )
            )
        ],
        adquirientes=[
            Adquiriente(
                nombre="Carlos Rodríguez",
                actua_por="derecho propio",
                estado_civil="casado",
                rfc="ROMC790515ABC",
                curp=False
            )
        ],
        monto_operacion="$1,500,000.00"
    )
    
    print(f"\n✅ Escritura creada exitosamente")
    print(f"   Notario: {escritura.notario}")
    print(f"   Número: {escritura.numero_escritura}")
    
    assert escritura.notario == "Lic. Roberto García"
    assert escritura.numero_escritura == 3125


def test_modelo_estricto_falla_sin_campos():
    """Prueba 2: Modelo estricto falla sin campos obligatorios."""
    print("\n" + "="*60)
    print("PRUEBA 2: Modelo ESTRICTO falla sin campos")
    print("="*60)
    
    try:
        escritura = EscrituraPublica(
            notario="Lic. Test"
            # Faltan campos obligatorios
        )
        print("❌ Debería haber fallado")
        assert False
    except Exception as e:
        print(f"\n✅ Error esperado: modelo estricto requiere campos")


def test_modelo_flexible_acepta_incompleto():
    """Prueba 3: Modelo flexible acepta datos incompletos."""
    print("\n" + "="*60)
    print("PRUEBA 3: Modelo FLEXIBLE acepta incompleto")
    print("="*60)
    
    # Solo algunos campos
    escritura = EscrituraPublicaFlexible(
        notario="Lic. María López",
        numero_escritura=1000
    )
    
    print(f"\n✅ Escritura flexible creada")
    print(f"   Notario: {escritura.notario}")
    print(f"   Monto: {escritura.monto_operacion}")  # Debería ser NO_ENCONTRADO
    
    assert escritura.notario == "Lic. María López"
    assert escritura.monto_operacion == NO_ENCONTRADO


def test_validar_json_flexible():
    """Prueba 4: Función validar_json_flexible."""
    print("\n" + "="*60)
    print("PRUEBA 4: Función validar_json_flexible")
    print("="*60)
    
    # JSON incompleto como lo devolvería DeepSeek
    json_incompleto = {
        "titulares": [
            {
                "nombre_titular": "DESARROLLOS S.A. DE C.V.",
                "representante": "Juan Pérez"
            }
        ]
    }
    
    escritura = validar_json_flexible(json_incompleto)
    
    print(f"\n✅ JSON validado flexiblemente")
    print(f"   Titulares: {len(escritura.titulares)}")
    
    # Verificar que normalizó nombre_titular → nombre
    assert len(escritura.titulares) == 1
    assert escritura.titulares[0].nombre == "DESARROLLOS S.A. DE C.V."


def test_generar_reporte():
    """Prueba 5: Generación de reporte."""
    print("\n" + "="*60)
    print("PRUEBA 5: Generación de reporte")
    print("="*60)
    
    json_parcial = {
        "notario": "Lic. Test",
        "numero_escritura": 123,
        "titulares": [{"nombre": "Empresa X", "actua_por": "derecho propio"}]
    }
    
    escritura = validar_json_flexible(json_parcial)
    reporte = escritura.generar_reporte()
    
    print(f"\n📊 Reporte generado:")
    print(f"   Campos encontrados: {reporte['resumen']['campos_encontrados']}/8")
    print(f"   Porcentaje: {reporte['resumen']['porcentaje_exito']}%")
    print(f"   Faltantes: {reporte['campos_faltantes']}")
    
    assert "resumen" in reporte
    assert "datos_encontrados" in reporte
    assert "campos_faltantes" in reporte


def test_get_campos_encontrados():
    """Prueba 6: Método get_campos_encontrados."""
    print("\n" + "="*60)
    print("PRUEBA 6: get_campos_encontrados")
    print("="*60)
    
    escritura = EscrituraPublicaFlexible(
        notario="Lic. García",
        numero_escritura=500,
        monto_operacion="$100,000"
    )
    
    encontrados = escritura.get_campos_encontrados()
    no_encontrados = escritura.get_campos_no_encontrados()
    
    print(f"\n✅ Campos encontrados: {list(encontrados.keys())}")
    print(f"❌ Campos no encontrados: {no_encontrados}")
    
    assert "notario" in encontrados
    assert "numero_escritura" in encontrados
    assert "fecha_documento" in no_encontrados


def test_generar_feedback_error():
    """Prueba 7: Generación de feedback para retry."""
    print("\n" + "="*60)
    print("PRUEBA 7: Generación de feedback INTELIGENTE")
    print("="*60)
    
    # JSON incompleto del intento anterior
    json_anterior = {
        "titulares": [
            {"nombre_titular": "EMPRESA S.A.", "representante": "Juan"}
        ],
        "monto_operacion": "$100,000"
    }
    
    error = "notario: Field required\nnumero_escritura: Field required"
    feedback = generar_feedback_error(error, json_anterior)
    
    print(f"\n✅ Feedback generado:")
    print(f"   Longitud: {len(feedback)} caracteres")
    print(f"   Incluye JSON anterior: {'TU RESPUESTA ANTERIOR' in feedback}")
    print(f"   Incluye campos encontrados: {'CAMPOS QUE YA TIENES' in feedback}")
    print(f"   Incluye campos faltantes: {'CAMPOS QUE FALTAN' in feedback}")
    
    assert "notario" in feedback
    assert len(feedback) > 500  # Feedback debe ser detallado


def test_representante_flexible():
    """Prueba 8: Representante flexible con valores por defecto."""
    print("\n" + "="*60)
    print("PRUEBA 8: Representante flexible")
    print("="*60)
    
    rep = RepresentanteFlexible(nombre="Juan Pérez")
    
    print(f"\n✅ Representante creado:")
    print(f"   Nombre: {rep.nombre}")
    print(f"   En calidad: {rep.en_calidad}")
    print(f"   Bis: {rep.bis}")
    
    assert rep.nombre == "Juan Pérez"
    assert rep.en_calidad == NO_ENCONTRADO
    assert rep.bis == False


def test_campos_obligatorios():
    """Prueba 9: Lista de campos obligatorios."""
    print("\n" + "="*60)
    print("PRUEBA 9: Campos obligatorios")
    print("="*60)
    
    obligatorios = get_campos_obligatorios()
    no_obligatorios = get_campos_no_obligatorios()
    
    print(f"\n📋 Campos obligatorios: {obligatorios}")
    print(f"📋 Campos no obligatorios: {no_obligatorios}")
    
    assert "notario" in obligatorios
    assert "numero_escritura" in obligatorios
    assert "valor_catastral" in no_obligatorios


def test_multiples_titulares_adquirientes():
    """Prueba 10: Múltiples titulares y adquirientes."""
    print("\n" + "="*60)
    print("PRUEBA 10: Múltiples titulares/adquirientes")
    print("="*60)
    
    json_data = {
        "notario": "Lic. Test",
        "numero_escritura": 100,
        "fecha_documento": "01/01/2024",
        "tipo_titular": "persona",
        "titulares": [
            {"nombre": "Persona 1", "actua_por": "derecho propio"},
            {"nombre": "Persona 2", "actua_por": "derecho propio"},
            {"nombre": "Persona 3", "actua_por": "representación"}
        ],
        "adquirientes": [
            {"nombre": "Comprador 1", "estado_civil": "soltero"},
            {"nombre": "Comprador 2", "estado_civil": "casado"}
        ],
        "monto_operacion": "$500,000"
    }
    
    escritura = validar_json_flexible(json_data)
    
    print(f"\n✅ Múltiples participantes:")
    print(f"   Titulares: {len(escritura.titulares)}")
    print(f"   Adquirientes: {len(escritura.adquirientes)}")
    
    assert len(escritura.titulares) == 3
    assert len(escritura.adquirientes) == 2


def test_analizar_json_parcial():
    """Prueba 11: Función analizar_json_parcial."""
    print("\n" + "="*60)
    print("PRUEBA 11: analizar_json_parcial")
    print("="*60)
    
    from models.escritura import analizar_json_parcial
    
    # JSON con problemas típicos
    json_problematico = {
        "titulares": [
            {
                "tipo_titular": "empresa",  # Error: debería estar en raíz
                "nombre_titular": "EMPRESA S.A.",  # Error: debería ser "nombre"
                "representante": "Juan Pérez"  # Error: debería ser objeto
            }
        ],
        "monto_operacion": "$100,000"
    }
    
    analisis = analizar_json_parcial(json_problematico)
    
    print(f"\n📊 Análisis del JSON:")
    print(f"   Campos encontrados: {analisis['campos_encontrados']}")
    print(f"   Campos faltantes: {analisis['campos_faltantes']}")
    print(f"   Porcentaje: {analisis['porcentaje']}%")
    print(f"   Problemas detectados: {len(analisis['problemas_detectados'])}")
    
    for problema in analisis['problemas_detectados']:
        print(f"      - {problema}")
    
    assert "monto_operacion" in analisis['campos_encontrados']
    assert "notario" in analisis['campos_faltantes']
    assert len(analisis['problemas_detectados']) >= 2  # Al menos 2 problemas


def test_adquiriente_empresa_con_representante():
    """Prueba 12: Adquiriente empresa con representante."""
    print("\n" + "="*60)
    print("PRUEBA 12: Adquiriente EMPRESA con representante")
    print("="*60)

    escritura = EscrituraPublica(
        notario=[
            Notario(
                nombre="Lic. Roberto García",
                numero_notario="45",
                municipio="Ciudad de México",
                escritura="3125",
                fecha_documento="15 de mayo de 2024"
            )
        ],
        numero_escritura=3125,
        fecha_documento="15 de mayo de 2024",
        tipo_titular="persona",
        titulares=[
            Titular(
                nombre="Juan Pérez",
                actua_por="derecho propio",
                representante=None
            )
        ],
        adquirientes=[
            Adquiriente(
                nombre="CONSTRUCTORA ABC S.A. DE C.V.",
                actua_por="representación",
                estado_civil="NO SE ENCONTRÓ DATO",
                rfc=False,
                curp=False,
                representante=Representante(
                    nombre="María López García",
                    en_calidad="apoderado legal",
                    escritura="5678",
                    bis=False,
                    fecha_poder="10 de marzo de 2023"
                )
            )
        ],
        monto_operacion="$1,500,000.00"
    )

    print(f"\nAdquiriente empresa creado exitosamente")
    print(f"   Adquiriente: {escritura.adquirientes[0].nombre}")
    print(f"   Representante: {escritura.adquirientes[0].representante.nombre}")
    assert escritura.adquirientes[0].representante is not None


def test_adquiriente_empresa_sin_representante_debe_fallar():
    """Prueba 13: Adquiriente empresa SIN representante debe fallar."""
    print("\n" + "="*60)
    print("PRUEBA 13: Adquiriente EMPRESA sin representante (debe fallar)")
    print("="*60)

    try:
        escritura = EscrituraPublica(
            notario=[
                Notario(
                    nombre="Lic. Roberto García",
                    numero_notario="45",
                    municipio="Ciudad de México",
                    escritura="3125",
                    fecha_documento="15 de mayo de 2024"
                )
            ],
            numero_escritura=3125,
            fecha_documento="15 de mayo de 2024",
            tipo_titular="persona",
            titulares=[
                Titular(
                    nombre="Juan Pérez",
                    actua_por="derecho propio",
                    representante=None
                )
            ],
            adquirientes=[
                Adquiriente(
                    nombre="CONSTRUCTORA ABC S.A. DE C.V.",
                    actua_por="representación",
                    estado_civil="NO SE ENCONTRÓ DATO",
                    rfc=False,
                    curp=False,
                    representante=None
                )
            ],
            monto_operacion="$1,500,000.00"
        )
        print("\nERROR: Debería haber fallado pero no lo hizo")
        assert False, "La validación debería haber fallado"
    except ValueError as e:
        print(f"\nValidación correcta: {e}")
        assert "parece ser EMPRESA" in str(e)
        assert "DEBE tener representante" in str(e)


def main():
    print("\n" + "#"*60)
    print("# PRUEBAS DE MODELOS PYDANTIC")
    print("# (Estricto + Flexible + Retry Inteligente)")
    print("#"*60)

    try:
        test_modelo_estricto_completo()
        test_modelo_estricto_falla_sin_campos()
        test_modelo_flexible_acepta_incompleto()
        test_validar_json_flexible()
        test_generar_reporte()
        test_get_campos_encontrados()
        test_generar_feedback_error()
        test_representante_flexible()
        test_campos_obligatorios()
        test_multiples_titulares_adquirientes()
        test_analizar_json_parcial()
        test_adquiriente_empresa_con_representante()
        test_adquiriente_empresa_sin_representante_debe_fallar()

        print("\n" + "="*60)
        print("✅ TODAS LAS PRUEBAS PASARON (13/13)")
        print("="*60 + "\n")

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
