# Backup del proyecto - 2026-01-19 02:50:51

## Estado del proyecto
- Fecha: 2026-01-19 02:50:52
- Commit actual: 8526290 ahora adquirientes puede tener repesentatntes

## Cambios recientes implementados
1. Implementación completa de representantes para adquirientes
   - Agregados campos actua_por y representante a modelos
   - Validación que requiere representante si adquiriente es empresa
   - Actualización de prompts y ejemplos JSON
   - Tests agregados y validados

2. Eliminación previa de campos estado y tipo_moneda
   - Reducción de longitud de prompts
   - Optimización de recursos

## Archivos incluidos en este backup
- models/
- utils/
- extraction/
- app/
- tests/*.py

## Notas
Este backup se creó antes de realizar modificaciones en la estrategia de extracción del campo monto_operacion.

