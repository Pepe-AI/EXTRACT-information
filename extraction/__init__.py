"""
extraction/ - Módulo de extracción inteligente (Plan Z)

Este paquete contiene los componentes del sistema de extracción:
- segmentador: Divide el documento en secciones (Plan D)
- validador_cruzado: Valida datos contra texto original (Plan B)
- plan_e_extractor: Extracción individual de campos problemáticos (Plan E)
- sistema_confianza: Consolida y evalúa calidad (Plan F)
"""

from extraction.segmentador import (
    Segmentador,
    segmentar_documento,
)

from extraction.validador_cruzado import (
    ValidadorCruzado,
    validar_campo,
    validar_todos_campos,
)

from extraction.plan_e_extractor import (
    PlanEExtractor,
    ResultadoPlanE,
)

from extraction.sistema_confianza import (
    SistemaConfianza,
    consolidar_extraccion,
)