# 🔧 Soluciones para Campos Críticos Faltantes

## 📊 PROBLEMA ACTUAL

**Campos que NO se extraen (pero están en el OCR):**
1. ❌ `adquiriente.estado_civil`: "CASADA"
2. ❌ `adquiriente.representante`: Objeto completo (MA. GUADALUPE HILDA BERNAL CHAVARIN)
3. ❌ `titular.representante.escritura`: "63,550" (número de instrumento)
4. ❌ `titular.representante.fecha_poder`: "15/04/2020"

---

## 🎯 ANÁLISIS DE CAUSAS

### Sistema Actual (Plan Z):
```
1. REGEX (Plan A) → Extrae campos básicos ✅
2. LLM (DeepSeek R1:32b) → Extracción general ⚠️ (falla en campos anidados)
3. Validación Cruzada (Plan B) → Valida contra texto ✅
4. Plan E → Recupera campos individuales ⚠️ (limitado)
```

### ¿Por qué falla?

#### **DeepSeek R1:32b (local):**
- ✅ **Bueno**: Campos de nivel superior (número escritura, fecha, municipio)
- ⚠️ **Regular**: Clasificación de tipos (empresa/persona)
- ❌ **Malo**: Campos anidados complejos (representante del adquiriente)
- ❌ **Malo**: Extracción de fechas/números en poderes

**Evidencia del problema:**
```json
// LLM genera:
"adquiriente": {
  "nombre": "ANGELBERTA PÉREZ SOTO",
  "estado_civil": null,  ❌ No detecta "casada"
  "representante": null   ❌ No detecta a MA. GUADALUPE HILDA BERNAL
}

// OCR contiene:
"casada, empleada doméstica"
"representada por su gestora de negocios la licenciada
MA. GUADALUPE HILDA BERNAL CHAVARIN"
```

---

## 💡 SOLUCIONES PROPUESTAS

### 🥇 **SOLUCIÓN 1: REGEX ESPECIALIZADO (Recomendada)**

**Ventajas:**
- ✅ 100% determinístico
- ✅ Muy rápido (sin costo API)
- ✅ Alta precisión para patrones conocidos
- ✅ Ya funciona bien para otros campos

**Implementación:**
```python
# Nuevas funciones regex en utils/text_processing.py

def extraer_estado_civil(texto: str, nombre_persona: str) -> Optional[str]:
    """
    Extrae estado civil cerca del nombre de la persona.

    Patrón: "NOMBRE, [ser] mexicano/a, mayor de edad, ESTADO_CIVIL"
    """
    patrones = [
        rf'{re.escape(nombre_persona)}.*?(?:mayor de edad|adulto),?\s+(casad[oa]|solter[oa]|divorciad[oa]|viud[oa])',
        rf'(?:casad[oa]|solter[oa]|divorciad[oa]|viud[oa]).*?{re.escape(nombre_persona)}',
    ]
    # ...

def extraer_representante_adquiriente(texto: str, nombre_adquiriente: str) -> Optional[Dict]:
    """
    Extrae representante que actúa por el adquiriente.

    Patrones:
    - "representada por [NOMBRE], en su calidad de [CARGO]"
    - "gestor/a de negocios [NOMBRE]"
    - "apoderado/a [NOMBRE]"
    """
    # ...

def extraer_datos_instrumento_poder(texto: str) -> Optional[Dict]:
    """
    Extrae número de escritura y fecha del instrumento de poder.

    Patrón: "instrumento [NÚMERO], de fecha [FECHA]"
    Ejemplo: "instrumento 63,550 sesenta y tres mil quinientos cincuenta,
              de fecha 15 quince del mes de abril del año 2020"
    """
    # ...
```

**Costo:** 0 USD (sin APIs externas)
**Tiempo implementación:** 2-4 horas
**Precisión esperada:** 85-95%

---

### 🥈 **SOLUCIÓN 2: MODELO GEMINI COMO COMPLEMENTO**

**Estrategia híbrida:**
```
┌─────────────────────────────────────────────────────────┐
│ 1. DeepSeek R1 (local)                                  │
│    → Extracción general + clasificación                 │
├─────────────────────────────────────────────────────────┤
│ 2. REGEX (Plan A)                                       │
│    → Campos básicos (escritura, fecha, municipio)       │
├─────────────────────────────────────────────────────────┤
│ 3. GEMINI (solo campos faltantes)                       │
│    → estado_civil, representantes, fechas_poder         │
│    → Prompt enfocado en 1 campo a la vez               │
└─────────────────────────────────────────────────────────┘
```

**Ventajas:**
- ✅ Mejor comprensión de lenguaje natural (Gemini)
- ✅ Solo se usa para campos críticos (bajo costo)
- ✅ Fallback si REGEX falla

**Desventajas:**
- ⚠️ Costo por llamada API
- ⚠️ Latencia adicional (red)
- ⚠️ Dependencia externa

**Implementación:**
```python
# services/gemini_service.py (nuevo)

class GeminiService:
    """Servicio especializado para campos complejos."""

    async def extraer_campo_individual(
        self,
        texto: str,
        campo: str,
        contexto: Optional[str] = None
    ) -> Optional[str]:
        """
        Extrae UN campo específico con prompt enfocado.

        Ejemplo:
            campo = "estado_civil"
            contexto = "ANGELBERTA PÉREZ SOTO"

            Prompt: "Del siguiente texto, extrae SOLO el estado civil
                     de ANGELBERTA PÉREZ SOTO. Responde con una palabra:
                     casada/soltera/divorciada/viuda o null"
        """
        # ...
```

**Costo estimado:**
- Gemini 2.0 Flash: $0.075 / 1M tokens entrada
- ~500 documentos/mes × 4 campos × 1000 tokens = 2M tokens
- **Costo mensual: ~$0.15 USD**

**Tiempo implementación:** 4-6 horas
**Precisión esperada:** 90-98%

---

### 🥉 **SOLUCIÓN 3: PLAN E MEJORADO (Extracción Individual)**

**Mejora del sistema existente:**

El Plan E actual ya existe pero es limitado. Podríamos expandirlo:

```python
# extraction/plan_e_extractor.py (mejorar existente)

CAMPOS_PLAN_E = {
    "estado_civil": {
        "prompt": "Del texto, extrae SOLO el estado civil de {nombre}...",
        "validacion": ["casada", "soltera", "divorciada", "viuda"],
        "confianza_minima": 0.6
    },
    "representante_adquiriente": {
        "prompt": "¿Quién representa a {nombre}? Extrae nombre y cargo...",
        "validacion": lambda x: "nombre" in x and "en_calidad" in x,
        "confianza_minima": 0.7
    },
    # ...
}
```

**Ventajas:**
- ✅ Usa infraestructura existente
- ✅ No requiere servicios externos

**Desventajas:**
- ⚠️ Sigue usando DeepSeek (que ya falla)
- ⚠️ Múltiples llamadas al LLM local (lento)

**Tiempo implementación:** 2-3 horas
**Precisión esperada:** 60-75% (limitado por DeepSeek)

---

### 🏆 **SOLUCIÓN 4: COMBINACIÓN REGEX + GEMINI (LA MEJOR)**

**Estrategia multi-nivel:**

```
┌─────────────────────────────────────────────────────────┐
│ NIVEL 1: REGEX (Plan A) - Campos estructurados         │
│ ✅ numero_escritura, fecha_documento, numero_notaria    │
│ ✅ nombre_notario, municipio, monto_operacion           │
│ 🆕 estado_civil, numero_instrumento_poder               │
├─────────────────────────────────────────────────────────┤
│ NIVEL 2: DeepSeek R1 - Extracción general              │
│ ✅ Clasificación (empresa/persona)                      │
│ ✅ Nombres de titulares/adquirientes                    │
│ ✅ Estructura básica                                    │
├─────────────────────────────────────────────────────────┤
│ NIVEL 3: Validación Cruzada (Plan B)                   │
│ ✅ Detectar alucinaciones                               │
├─────────────────────────────────────────────────────────┤
│ NIVEL 4: GEMINI FALLBACK (solo si REGEX falla)         │
│ 🆕 Campos anidados complejos                            │
│ 🆕 Representantes con múltiples atributos               │
│ 🆕 Fechas en formato texto                              │
└─────────────────────────────────────────────────────────┘
```

**Flujo de decisión:**
```python
# Pseudocódigo

estado_civil = extraer_estado_civil_regex(texto, nombre)
if not estado_civil:
    estado_civil = gemini_service.extraer_campo(texto, "estado_civil", contexto=nombre)

representante = extraer_representante_regex(texto, nombre)
if not representante or not representante.get("nombre"):
    representante = gemini_service.extraer_representante(texto, nombre)

fecha_poder = extraer_fecha_poder_regex(texto)
if not fecha_poder:
    fecha_poder = gemini_service.extraer_fecha_poder(texto, nombre_titular)
```

**Ventajas:**
- ✅ Mejor de ambos mundos
- ✅ Bajo costo (REGEX primero)
- ✅ Alta precisión (Gemini como fallback)
- ✅ Resiliente (múltiples capas)

**Costos:**
- REGEX: 0 USD
- Gemini (solo fallback): ~$0.05-0.10 USD/mes
- **Total: < $0.15 USD/mes**

**Tiempo implementación:** 6-8 horas
**Precisión esperada:** 95-99%

---

## 📋 COMPARACIÓN DE SOLUCIONES

| Solución | Precisión | Costo/mes | Velocidad | Complejidad | Recomendación |
|----------|-----------|-----------|-----------|-------------|---------------|
| **#1: Solo REGEX** | 85-95% | $0 | ⚡⚡⚡ Muy rápido | 🟢 Baja | ✅ Empezar aquí |
| **#2: Solo Gemini** | 90-98% | ~$0.15 | ⚡ Medio | 🟡 Media | ⚠️ Sobrecosto |
| **#3: Plan E mejorado** | 60-75% | $0 | ⚡ Lento | 🟢 Baja | ❌ Bajo rendimiento |
| **#4: REGEX + Gemini** | 95-99% | ~$0.10 | ⚡⚡ Rápido | 🟡 Media | ✅✅ **MEJOR** |

---

## 🎯 PLAN DE IMPLEMENTACIÓN RECOMENDADO

### **FASE 1: REGEX (Quick Wins)** ⏱️ 3-4 horas

1. **Estado Civil** → Función `extraer_estado_civil()`
   ```python
   # Patrón: "mayor de edad, ESTADO_CIVIL"
   # Precisión esperada: 90%
   ```

2. **Número de Instrumento** → Función `extraer_numero_instrumento_poder()`
   ```python
   # Patrón: "instrumento 63,550"
   # Precisión esperada: 95%
   ```

3. **Fecha de Poder** → Función `extraer_fecha_poder()`
   ```python
   # Patrón: "de fecha 15 de abril del año 2020"
   # Precisión esperada: 85%
   ```

**Resultado esperado:** 70-80% de los campos críticos resueltos

---

### **FASE 2: GEMINI FALLBACK** ⏱️ 4-5 horas

4. **Integrar Gemini Service**
   ```python
   # Solo para campos que REGEX no pudo extraer
   # Prompts hiperespecíficos para cada campo
   ```

5. **Representante del Adquiriente** → Extracción compleja
   ```python
   # Gemini es mejor para relaciones complejas
   # "representada por X, en calidad de Y"
   ```

**Resultado esperado:** 95%+ de campos críticos extraídos

---

### **FASE 3: POST-PROCESAMIENTO** ⏱️ 2 horas

6. **Normalización de formatos**
   - Fechas: "15/04/2020" o "4/15/2020"
   - Estado civil: MAYÚSCULAS
   - Limpiar títulos profesionales

7. **Estandarización de valores**
   - `actua_por`: "APODERADO", "GESTOR OFICIOSO", etc.
   - `en_calidad`: valores canónicos

---

## 🔍 INFORMACIÓN ADICIONAL QUE NECESITO

Para implementar la **Solución #4 (REGEX + Gemini)**:

### 1. **¿Tienes cuenta de Google Cloud?**
   - [ ] Sí → ¿API Key de Gemini disponible?
   - [ ] No → Puedo ayudarte a crearla (5 min)

### 2. **¿Volumen de procesamiento?**
   - Documentos/día: ______
   - Documentos/mes: ______
   - Esto afecta el costo de Gemini

### 3. **¿Prioridad de precisión vs costo?**
   - [ ] Máxima precisión (usar Gemini más)
   - [ ] Balance (REGEX primero, Gemini fallback)
   - [ ] Mínimo costo (solo REGEX)

### 4. **¿Latencia aceptable?**
   - [ ] < 5 segundos (solo REGEX)
   - [ ] 5-15 segundos (REGEX + Gemini fallback)
   - [ ] > 15 segundos (Gemini para todo)

### 5. **¿Frameworks disponibles?**
   - [ ] ¿Puedo instalar `google-generativeai`?
   - [ ] ¿Hay restricciones de red/firewall?

---

## 🚀 ¿QUÉ SOLUCIÓN PREFIERES?

Basándome en tu situación actual, recomiendo:

### **Opción A: RÁPIDA (Solo REGEX)** ⏱️ 3-4 horas
- Implementar funciones regex para los 4 campos críticos
- Sin dependencias externas
- Precisión: 85-90%
- Costo: $0

### **Opción B: COMPLETA (REGEX + Gemini)** ⏱️ 8-10 horas
- REGEX primero, Gemini como fallback
- Requiere API Key de Gemini
- Precisión: 95-99%
- Costo: ~$0.10/mes

### **Opción C: EXPERIMENTAL (Solo Gemini)** ⏱️ 4-6 horas
- Probar qué tal funciona Gemini solo
- Comparar con DeepSeek R1
- Evaluar para decidir estrategia final

---

## 📌 PRÓXIMOS PASOS

**Dime:**
1. ¿Qué solución prefieres? (A, B o C)
2. ¿Tienes acceso a Gemini API?
3. ¿Quieres que empiece con REGEX (Fase 1)?

Puedo empezar AHORA MISMO con la **Opción A** (solo REGEX) si quieres ver resultados rápidos. 🚀
