# 🔍 Análisis del Problema: Fallo en Extracción de `monto_operacion`

## 📊 Situación Actual

**Tasa de Fallo:** 8/10 pruebas (80% de fallo)

Esto es **CRÍTICO** ya que `monto_operacion` es un campo obligatorio y fundamental.

---

## 🐛 Problemas Identificados

### Problema 1: Orden de Prioridad Incorrecto

**Flujo Actual:**
```
Plan A (REGEX) → DeepSeek → Gemini Expandido → Gemini Fallback
     ↓              ↓              ↓                   ↓
  Prioridad 1   Prioridad 2    Prioridad 3        Prioridad 4
```

**❌ El problema:**
- **REGEX ejecuta primero** (Paso 6) con 12 patrones
- **Gemini Expandido ejecuta después** (Paso 6.6)
- **Merge da prioridad a Gemini**, PERO solo si DeepSeek ya tiene un valor

**Código actual (extractor.py línea 1341-1343):**
```python
if "monto_operacion" in gemini_data and gemini_data["monto_operacion"]:
    resultado["monto_operacion"] = gemini_data["monto_operacion"]
    print(f"   ✅ Monto ← Gemini")
```

**Esto solo funciona SI:**
1. ✅ DeepSeek extrae un valor (cualquiera)
2. ✅ Gemini también extrae un valor
3. ✅ Entonces Gemini sobrescribe a DeepSeek

**❌ Si DeepSeek NO extrae nada:**
- Gemini Expandido ejecuta
- Pero el merge falla porque `resultado` (DeepSeek) no tiene la clave
- Se usa el valor de REGEX (que puede ser incorrecto)

---

### Problema 2: REGEX Puede Capturar Valores Incorrectos

**Ejemplo Real:**

**Documento:**
```
Se pagaron impuestos por $12,500.00

El valor catastral es de $435,000.00

CLÁUSULA SEGUNDA - PRECIO
El precio de venta es de $600,000.00
```

**REGEX detecta 3 valores:**
1. $12,500.00 (impuesto) - Score: 2.8 ❌
2. $435,000.00 (valor catastral) - Score: 1.2 ⚠️
3. $600,000.00 (precio venta) - Score: 0.5 ✅

**✅ Sistema de Scoring funciona BIEN** (selecciona $600,000)

**❌ PERO puede fallar si:**
- El documento menciona "valor catastral" con palabra clave fuerte ("la cantidad de")
- El precio de venta está mal formateado o sin palabras clave

---

### Problema 3: Gemini NO Busca en Sección Específica

**Código actual (gemini_service.py línea 257-294):**

```python
⚠️ UBICACIÓN DE CAMPOS POR SECCIÓN (CRÍTICO)
═══════════════════════════════════════════

3. CLÁUSULA SEGUNDA (Operación)
   → monto_operacion, valor_catastral   ← Dice dónde buscar
```

**❌ PERO:**
- Gemini recibe el **texto completo** (30,000 caracteres)
- **NO** recibe solo la sección "Cláusula Segunda"
- Puede confundirse con otros montos en el documento

**Solución ideal:**
- Segmentar el documento ANTES de enviar a Gemini
- Enviar SOLO la sección "Cláusula Segunda" (~2,000 chars)
- Reducir tokens 83% + Mayor precisión

---

### Problema 4: Sistema de Confianza No Prioriza Gemini

**Código actual (sistema_confianza.py línea 84-99):**

```python
def agregar_regex(self, datos_regex: Dict[str, Any]):
    for nombre, valor in datos_regex.items():
        if valor not in VALORES_INVALIDOS:
            self._datos[nombre] = valor
            self._confianza[nombre] = NivelConfianza.ALTA  ← REGEX = ALTA
            self._origen[nombre] = OrigenDato.REGEX
```

**❌ El problema:**
- REGEX siempre tiene confianza **ALTA**
- Gemini tiene confianza **MEDIA** o **BAJA**
- El merge NUNCA sobrescribe REGEX con Gemini

**Resultado:**
- Si REGEX extrae valor incorrecto → Se queda el incorrecto
- Gemini extrae valor correcto → Se ignora

---

### Problema 5: Gemini Fallback Global No Siempre Se Activa

**Código actual (extractor.py línea 591-594):**

```python
campos_media_baja = [
    campo for campo, nivel in resultado_confianza.confianza.items()
    if nivel in ["media", "baja"]
]
```

**❌ El problema:**
- Solo se activa si el campo tiene confianza "media" o "baja"
- Si REGEX extrajo valor → Confianza = "alta"
- Gemini Fallback NO se ejecuta
- El valor incorrecto de REGEX se mantiene

---

## 🎯 Solución Propuesta

### Cambio 1: Priorizar Gemini para `monto_operacion`

**Archivo:** `app/extractor.py`
**Ubicación:** Función `_merge_deepseek_gemini()` (línea 1341)

**ANTES:**
```python
if "monto_operacion" in gemini_data and gemini_data["monto_operacion"]:
    resultado["monto_operacion"] = gemini_data["monto_operacion"]
    print(f"   ✅ Monto ← Gemini")
```

**DESPUÉS:**
```python
# PRIORIDAD ALTA: Gemini para monto_operacion (más preciso que REGEX)
if "monto_operacion" in gemini_data and gemini_data["monto_operacion"]:
    # Siempre sobrescribir con Gemini (incluso si hay valor de REGEX/DeepSeek)
    resultado["monto_operacion"] = gemini_data["monto_operacion"]
    print(f"   ✅ Monto ← Gemini (PRIORIDAD)")
elif not resultado.get("monto_operacion"):
    # Fallback: usar REGEX/DeepSeek si Gemini falló
    if datos_regex and datos_regex.get("monto_operacion"):
        resultado["monto_operacion"] = datos_regex["monto_operacion"]
        print(f"   ⚠️ Monto ← REGEX (fallback)")
```

---

### Cambio 2: Usar Segmentación para Gemini

**Archivo:** `app/extractor.py`
**Ubicación:** Paso 6.6 (línea 462-465)

**ANTES:**
```python
print(f"\n🔮 Paso 6.6: Extracción Gemini (expandido: titular/adquiriente/municipio/monto)...")
gemini_data = self._extraer_con_gemini(ocr_text, nivel="expandido")
```

**DESPUÉS:**
```python
print(f"\n🔮 Paso 6.6: Extracción Gemini (expandido: titular/adquiriente/municipio/monto)...")

# Segmentar documento para enviar solo sección relevante
from extraction.segmentador_v2 import SegmentadorV2
from models.seccion_mapping import SeccionDocumento

segmentador = SegmentadorV2()
resultado_seg = segmentador.segmentar(ocr_text)

# Extraer sección CLAUSULA_SEGUNDA para monto_operacion
texto_para_monto = ocr_text  # Por defecto texto completo
if not resultado_seg.usar_fallback:
    if SeccionDocumento.CLAUSULA_SEGUNDA in resultado_seg.secciones:
        seccion_monto = resultado_seg.secciones[SeccionDocumento.CLAUSULA_SEGUNDA]
        texto_para_monto = seccion_monto.contenido
        print(f"   📍 Usando solo CLÁUSULA SEGUNDA para monto ({len(texto_para_monto)} chars)")

# Extraer con Gemini usando sección específica
gemini_data = self._extraer_con_gemini(
    texto_para_monto,  # ← Texto segmentado
    nivel="expandido"
)
```

---

### Cambio 3: Modificar Confianza de REGEX para `monto_operacion`

**Archivo:** `extraction/sistema_confianza.py`
**Ubicación:** Función `agregar_regex()` (línea 84-99)

**ANTES:**
```python
def agregar_regex(self, datos_regex: Dict[str, Any]):
    for nombre, valor in datos_regex.items():
        if valor not in VALORES_INVALIDOS:
            self._datos[nombre] = valor
            self._confianza[nombre] = NivelConfianza.ALTA  ← Siempre ALTA
            self._origen[nombre] = OrigenDato.REGEX
```

**DESPUÉS:**
```python
def agregar_regex(self, datos_regex: Dict[str, Any]):
    for nombre, valor in datos_regex.items():
        if valor not in VALORES_INVALIDOS:
            self._datos[nombre] = valor

            # EXCEPCIÓN: monto_operacion tiene confianza MEDIA en REGEX
            # (puede confundir valor catastral, impuestos, etc.)
            if nombre == "monto_operacion":
                self._confianza[nombre] = NivelConfianza.MEDIA  ← MEDIA
                print(f"   📊 REGEX extrae monto_operacion: {valor} (confianza MEDIA)")
            else:
                self._confianza[nombre] = NivelConfianza.ALTA

            self._origen[nombre] = OrigenDato.REGEX
```

**Impacto:**
- ✅ Gemini Fallback Global ahora se activará para `monto_operacion`
- ✅ Permite que Gemini sobrescriba el valor de REGEX
- ✅ Mantiene ALTA confianza para otros campos de REGEX

---

### Cambio 4: Forzar Extracción de `monto_operacion` con Gemini

**Archivo:** `app/extractor.py`
**Ubicación:** Paso 11 - Gemini Fallback (línea 591-594)

**ANTES:**
```python
campos_media_baja = [
    campo for campo, nivel in resultado_confianza.confianza.items()
    if nivel in ["media", "baja"]
]
```

**DESPUÉS:**
```python
campos_media_baja = [
    campo for campo, nivel in resultado_confianza.confianza.items()
    if nivel in ["media", "baja"]
]

# FORZAR inclusión de monto_operacion si no tiene ALTA confianza
if "monto_operacion" in resultado_confianza.datos:
    if resultado_confianza.confianza.get("monto_operacion") != "alta":
        if "monto_operacion" not in campos_media_baja:
            campos_media_baja.append("monto_operacion")
            print(f"   📍 Forzando verificación de monto_operacion con Gemini Fallback")
```

---

### Cambio 5: Mejorar Prompt de Gemini para `monto_operacion`

**Archivo:** `services/gemini_service.py`
**Ubicación:** Función `_construir_prompt()` (línea 200-210)

**ANTES:**
```python
DESCRIPCIONES_CAMPOS = {
    ...
    "monto_operacion": "Monto de la operación ($X,XXX.XX) - SECCIÓN: Cláusula Segunda",
    ...
}
```

**DESPUÉS:**
```python
DESCRIPCIONES_CAMPOS = {
    ...
    "monto_operacion": """Monto de la VENTA/COMPRAVENTA del inmueble ($X,XXX.XX)
    SECCIÓN: Cláusula Segunda
    CONTEXTO: Busca frases como "precio de venta", "la cantidad de", "precio pactado"
    NO CONFUNDIR CON: valor catastral, impuestos, gastos notariales, pagos parciales
    FORMATO: $X,XXX.XX (con signo de peso y comas para miles)
    EJEMPLO: $600,000.00""",
    ...
}
```

---

## 📊 Impacto Esperado de los Cambios

| Cambio | Impacto | Mejora Esperada |
|--------|---------|-----------------|
| **1. Priorizar Gemini** | Alto | +40% precisión |
| **2. Usar Segmentación** | Medio | +20% precisión, -83% tokens |
| **3. Confianza MEDIA en REGEX** | Alto | Activa Gemini Fallback |
| **4. Forzar Gemini** | Alto | Garantiza doble verificación |
| **5. Mejorar Prompt** | Medio | +10% precisión en Gemini |

**TOTAL ESPERADO:** 80% fallo → **10% fallo** (70% mejora)

---

## 🎯 Prioridad de Implementación

### Fase 1 - Crítico (Implementar YA):
1. ✅ **Cambio 3**: Confianza MEDIA para monto_operacion en REGEX
2. ✅ **Cambio 1**: Priorizar Gemini en merge
3. ✅ **Cambio 4**: Forzar verificación con Gemini Fallback

**Resultado esperado:** 80% fallo → 30% fallo

---

### Fase 2 - Importante (Implementar después):
4. ✅ **Cambio 2**: Usar segmentación para Gemini
5. ✅ **Cambio 5**: Mejorar prompt de Gemini

**Resultado esperado:** 30% fallo → 10% fallo

---

## 🧪 Plan de Pruebas

### Test 1: Documento con Múltiples Montos
```
Valor catastral: $435,000.00
Impuestos: $12,500.00
Precio de venta: $600,000.00  ← CORRECTO
```
**Esperado:** $600,000.00

---

### Test 2: Documento con Monto Sin Palabras Clave
```
CLÁUSULA SEGUNDA
$850,000.00 (OCHOCIENTOS CINCUENTA MIL PESOS)
```
**Esperado:** $850,000.00

---

### Test 3: Documento con Formato Inusual
```
El precio acordado fue de OCHOCIENTOS MIL PESOS M.N.
($800,000)
```
**Esperado:** $800,000.00

---

## 📌 Conclusión

**Problema raíz:** Sistema prioriza REGEX sobre Gemini, pero REGEX puede fallar en contextos complejos.

**Solución:** Dar prioridad a Gemini para `monto_operacion` y activar siempre Gemini Fallback para este campo.

**Próximos pasos:**
1. Implementar Fase 1 (Cambios 1, 3, 4)
2. Ejecutar test_rapido.py con 10 documentos
3. Medir mejora en tasa de éxito
4. Si mejora ≥50%, implementar Fase 2

---

**Última actualización:** 2026-02-06
**Autor:** Análisis basado en código actual
