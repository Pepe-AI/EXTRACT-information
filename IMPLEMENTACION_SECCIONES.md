# 📊 Implementación de Extracción por Secciones

## 🎯 Objetivo

Mejorar la precisión del extractor usando el **mapeo oficial de campos → secciones** basado en la estructura estándar de escrituras públicas mexicanas.

---

## ✅ Archivos Creados

### 1. `models/seccion_mapping.py` ⭐ NUEVO
**Propósito:** Mapa autoritativo de qué campos se extraen de qué secciones.

```python
CAMPOS_POR_SECCION = {
    SeccionDocumento.INTRODUCCION: [
        "numero_escritura", "fecha_documento", "numero_notaria",
        "municipio", "nombre_notario"
    ],
    SeccionDocumento.CLAUSULA_PRIMERA: [
        "titulares", "adquirientes", "titular.nombre", ...
    ],
    SeccionDocumento.CLAUSULA_SEGUNDA: [
        "monto_operacion", "valor_catastral"
    ],
    SeccionDocumento.PERSONALIDAD: [
        "representante.escritura", "representante.fecha_poder"
    ],
    SeccionDocumento.GENERALES: [
        "estado_civil", "tipo_sociedad", "edad", "rfc", "curp"
    ],
}
```

**Funciones útiles:**
- `obtener_seccion_de_campo(campo)` → Retorna sección donde buscar
- `validar_campo_en_seccion(campo, seccion)` → Valida si es correcto
- `PATRONES_TITULOS_SECCION` → Regex para detectar títulos

---

### 2. `extraction/segmentador_v2.py` ⭐ NUEVO (reemplazo)
**Propósito:** Segmentador mejorado que usa el mapeo oficial.

**Ventajas vs `segmentador.py` (obsoleto):**
- ✅ Usa patrones oficiales de la tabla
- ✅ Detecta secciones con mayor precisión
- ✅ Retorna `SeccionExtraida` con contenido y confianza
- ✅ Límites de caracteres por sección (evita truncar mal)

**Uso:**
```python
from extraction.segmentador_v2 import SegmentadorV2

segmentador = SegmentadorV2()
resultado = segmentador.segmentar(texto_documento)

if not resultado.usar_fallback:
    # Obtener sección específica
    seccion_generales = resultado.secciones[SeccionDocumento.GENERALES]
    print(seccion_generales.contenido)  # Solo texto de GENERALES
```

---

### 3. `test_segmentacion_simple.py` 🧪 TEST
Script de prueba para validar que la segmentación funciona correctamente.

---

## 🔄 Archivos Modificados

### 1. `services/gemini_service.py` ✏️ MEJORADO
**Cambios:**
1. **Descripciones de campos con ubicación:**
   ```python
   "rfc": "RFC - SECCIÓN: Generales/FE NOTARIAL (AL FINAL)"
   "numero_escritura": "Número escritura - SECCIÓN: Introducción"
   ```

2. **Prompt con mapa de secciones:**
   ```
   ═══════════════════════════════════════════════════════════════
   ⚠️ UBICACIÓN DE CAMPOS POR SECCIÓN (CRÍTICO)
   ═══════════════════════════════════════════════════════════════

   1. INTRODUCCIÓN → numero_escritura, fecha_documento, ...
   2. CLÁUSULA PRIMERA → titulares, adquirientes
   3. CLÁUSULA SEGUNDA → monto_operacion, valor_catastral
   4. PERSONALIDAD → representante.escritura, representante.fecha_poder
   5. GENERALES → RFC, CURP, edad, estado_civil
   ```

3. **Texto completo sin truncar** (ya implementado antes):
   - Antes: `{texto_ocr[:3000]}` → ❌ Perdía RFC/CURP/edad
   - Ahora: `{texto_ocr}` → ✅ Envía todo el documento

---

### 2. `extraction/segmentador.py` ⚠️ DEPRECADO
**Marcado como OBSOLETO** con comentarios claros:
```python
"""
⚠️ OBSOLETO - USAR extraction/segmentador_v2.py INSTEAD
========================================================

DEPRECADO: Reemplazado por segmentador_v2.py
MANTENER: Solo como respaldo temporal
"""
```

**NO ELIMINAR AÚN:** Mantener hasta validar completamente V2.

---

## 🚀 Cómo Usar la Nueva Funcionalidad

### Opción 1: Usar en el Extractor Principal (Futuro)
```python
# En app/extractor.py, usar segmentador_v2 en lugar del antiguo
from extraction.segmentador_v2 import SegmentadorV2

segmentador = SegmentadorV2()
resultado_seg = segmentador.segmentar(texto_limpio)

# Enviar solo sección relevante al LLM
if SeccionDocumento.GENERALES in resultado_seg.secciones:
    texto_para_rfc = resultado_seg.secciones[SeccionDocumento.GENERALES].contenido
    # Extraer RFC/CURP/edad solo de esta sección
```

### Opción 2: Validación de Campos Extraídos
```python
from models.seccion_mapping import validar_campo_en_seccion

# Si extrajimos "rfc" de Introducción → ❌ RECHAZAR (debe ser de Generales)
# Si extrajimos "numero_escritura" de Personalidad → ⚠️ Puede ser del PODER
```

### Opción 3: Búsqueda Dirigida
```python
from extraction.segmentador_v2 import obtener_seccion_para_campo

# Obtener texto específico para un campo
texto_para_rfc = obtener_seccion_para_campo(resultado_seg, "rfc")
# Retorna: contenido de GENERALES (no todo el documento)
```

---

## 📈 Ventajas de Esta Implementación

### 1. ✅ Mayor Precisión
- **Antes:** Buscar "numero_escritura" en todo el documento → ambiguo (¿documento o poder?)
- **Ahora:** Buscar en Introducción (documento) vs Personalidad (poder) → claro

### 2. ✅ Menos Ambigüedad
| Campo | Sección Correcta | Evita Confusión Con |
|-------|------------------|---------------------|
| `numero_escritura` | Introducción | Escritura del poder |
| `rfc` | Generales | RFC del notario (si aparece) |
| `monto_operacion` | Cláusula Segunda | Otros montos (impuestos, etc.) |

### 3. ✅ Eficiencia (Menos Tokens)
- **Antes:** Enviar 30,000 caracteres a Gemini para extraer RFC
- **Ahora:** Enviar solo sección GENERALES (~5,000 chars) → **83% menos tokens**

### 4. ✅ Validación Automática
```python
# Rechazar campos extraídos de secciones incorrectas
if campo == "rfc" and seccion != SeccionDocumento.GENERALES:
    # ❌ RFC no puede estar en Introducción
    rechazar_valor()
```

---

## 🎯 Próximos Pasos (Integración)

### Paso 1: Integrar en `app/extractor.py`
Reemplazar:
```python
from extraction.segmentador import Segmentador
```
Por:
```python
from extraction.segmentador_v2 import SegmentadorV2
```

### Paso 2: Actualizar Gemini Expandido (`utils/gemini_prompts.py`)
Ya tiene instrucciones de sección, pero podría enviar **solo la sección relevante** en lugar del texto completo.

### Paso 3: Agregar Validación en Merge
En `_merge_deepseek_gemini()`:
```python
from models.seccion_mapping import validar_campo_en_seccion

# Validar antes de mergear
if not validar_campo_en_seccion(campo, seccion_origen):
    print(f"   ⚠️ {campo} extraído de sección incorrecta, rechazando")
    continue
```

### Paso 4: Eliminar `segmentador.py` Antiguo
Una vez validado V2, eliminar el archivo obsoleto.

---

## 📊 Tabla de Referencia Completa

| Campo | Sección | Descripción |
|-------|---------|-------------|
| `numero_escritura` | Introducción | Número del documento |
| `fecha_documento` | Introducción | Fecha del otorgamiento |
| `numero_notaria` | Introducción | Número de notaría |
| `municipio` | Introducción | Municipio de la notaría |
| `nombre_notario` | Introducción | Nombre del notario |
| `titulares` | Cláusula Primera | Vendedores |
| `adquirientes` | Cláusula Primera | Compradores |
| `monto_operacion` | Cláusula Segunda | Precio de venta |
| `valor_catastral` | Cláusula Segunda | Valor catastral |
| `representante.escritura` | Personalidad | Número escritura del poder |
| `representante.fecha_poder` | Personalidad | Fecha del poder |
| `estado_civil` | Generales | Estado civil |
| `tipo_sociedad` | Generales | Tipo de sociedad conyugal |
| `edad` | Generales | Edad |
| `rfc` | Generales | RFC |
| `curp` | Generales | CURP |

---

## ✅ Resumen de Implementación

### Archivos Nuevos (3):
1. ✅ `models/seccion_mapping.py` - Mapa oficial
2. ✅ `extraction/segmentador_v2.py` - Segmentador mejorado
3. ✅ `test_segmentacion_simple.py` - Test

### Archivos Modificados (2):
1. ✅ `services/gemini_service.py` - Prompts con mapa de secciones
2. ✅ `extraction/segmentador.py` - Marcado como OBSOLETO

### Archivos Obsoletos (1):
1. ⚠️ `extraction/segmentador.py` - Mantener temporalmente, luego eliminar

---

## 🎉 Estado: IMPLEMENTACIÓN COMPLETA

La nueva funcionalidad de extracción por secciones está **lista para usar**.

**Recomendación:** Probar en paralelo con el sistema actual durante 1-2 semanas antes de reemplazar completamente el segmentador antiguo.
