# 🔧 FIX: Representantes concatenados

## 📅 Fecha: 2026-01-23

---

## ⚠️ Problema identificado

Gemini a veces **ignora las instrucciones del prompt** y devuelve representantes concatenados en un solo objeto:

```json
{
  "titular": {
    "nombre": "CONSORCIO DE INGENIERIA INTEGRAL S.A. DE C.V.",
    "tipo": "empresa",
    "representante": {
      "nombre": "ROSA ANGELICA GUZMAN DELGADO Y MARGARITA MARIA FLORES VILLASEÑOR",
      "en_calidad": "apoderadas legales"
    }
  }
}
```

**Problemas:**
1. ❌ Dos nombres concatenados con " Y " en un solo campo
2. ❌ Imposible distinguir representantes individuales
3. ❌ Plural en `en_calidad` indica múltiples personas

---

## ✅ Solución implementada

Agregado **post-processing automático** que detecta y separa representantes concatenados.

### Arquitectura de la solución:

```
Gemini Response
      ↓
parse_gemini_response()  ← Parsea JSON
      ↓
_separar_representantes_concatenados()  ← POST-PROCESSING (NUEVO)
      ↓
JSON corregido
```

### Ubicación del código:

**Archivo:** `app/extractor.py`

**Líneas 890-989:** Función `_separar_representantes_concatenados()`

**Línea 959:** Llamada automática después de parsear JSON
```python
# Parsear respuesta JSON
json_data = parse_gemini_response(response)

# POST-PROCESSING: Separar representantes concatenados
if json_data:
    json_data = self._separar_representantes_concatenados(json_data)
```

---

## 🔍 Cómo funciona el post-processing

### Paso 1: Detección de concatenación

Usa regex para detectar patrón `" Y "` o `" y "`:
```python
if re.search(r'\s+[Yy]\s+', nombre):
    # Hay concatenación
```

### Paso 2: Separación de nombres

Divide el string por " Y " o " y ":
```python
nombres = re.split(r'\s+[Yy]\s+', nombre)
# ["ROSA ANGELICA GUZMAN DELGADO", "MARGARITA MARIA FLORES VILLASEÑOR"]
```

### Paso 3: Ajuste de plural → singular

Convierte `en_calidad` a singular:
```python
"apoderadas legales" → "apoderada legal"
"apoderados legales" → "apoderado legal"
"representantes" → "representante"
```

### Paso 4: Creación de objetos individuales

Crea array con objetos separados:
```python
representantes = [
    {
        "nombre": "ROSA ANGELICA GUZMAN DELGADO",
        "en_calidad": "apoderada legal",
        "escritura": "108030",
        "fecha_poder": "9/18/2009"
    },
    {
        "nombre": "MARGARITA MARIA FLORES VILLASEÑOR",
        "en_calidad": "apoderada legal",
        "escritura": "108030",
        "fecha_poder": "9/18/2009"
    }
]
```

**Nota:** Los datos del poder (escritura, fecha_poder) se copian a **todos** los representantes.

### Paso 5: Conversión de formato

Convierte `representante` (singular) → `representantes` (array):
```python
# ANTES
"representante": {...}

# DESPUÉS
"representantes": [{...}]
```

---

## 📊 Casos de prueba

### ✅ Test 1: Concatenación con " Y " (mayúscula)

**Input:**
```json
{
  "representante": {
    "nombre": "ROSA GUZMAN Y MARGARITA FLORES",
    "en_calidad": "apoderadas legales"
  }
}
```

**Output:**
```json
{
  "representantes": [
    {"nombre": "ROSA GUZMAN", "en_calidad": "apoderada legal"},
    {"nombre": "MARGARITA FLORES", "en_calidad": "apoderada legal"}
  ]
}
```

### ✅ Test 2: Concatenación con " y " (minúscula)

**Input:**
```json
{
  "representante": {
    "nombre": "JUAN PEREZ y MARIA LOPEZ",
    "en_calidad": "apoderados legales"
  }
}
```

**Output:**
```json
{
  "representantes": [
    {"nombre": "JUAN PEREZ", "en_calidad": "apoderado legal"},
    {"nombre": "MARIA LOPEZ", "en_calidad": "apoderado legal"}
  ]
}
```

### ✅ Test 3: Sin concatenación (nombre individual)

**Input:**
```json
{
  "representante": {
    "nombre": "JUAN PEREZ GONZALEZ",
    "en_calidad": "apoderado legal"
  }
}
```

**Output:**
```json
{
  "representantes": [
    {"nombre": "JUAN PEREZ GONZALEZ", "en_calidad": "apoderado legal"}
  ]
}
```

### ✅ Test 4: Sin representante (null)

**Input:**
```json
{
  "representante": null
}
```

**Output:**
```json
{
  "representantes": null
}
```

---

## 📝 Logs esperados

Cuando se detecta y corrige concatenación:
```
🔮 Extrayendo campos con Gemini (nivel: expandido)...
   🔧 Separados 2 representantes concatenados
   ✅ Titular (vendedor): CONSORCIO DE INGENIERIA INTEGRAL...
```

Sin concatenación (no se muestra log especial):
```
🔮 Extrayendo campos con Gemini (nivel: expandido)...
   ✅ Titular (vendedor): CONSORCIO DE INGENIERIA INTEGRAL...
```

---

## 🧪 Probar el fix

### Ejecutar script de prueba:

```bash
cd "C:\Users\Usuari\OneDrive\Desktop\GisNet Proyectos\Extract_information_PDF"
python TEST_POST_PROCESSING.py
```

Este script ejecuta 4 tests que verifican:
- ✅ Separación con " Y " (mayúscula)
- ✅ Separación con " y " (minúscula)
- ✅ Conversión de nombres individuales a array
- ✅ Manejo de representante null

### Probar con documento real:

```bash
# Reiniciar servidor
uvicorn app.api:app --host 0.0.0.0 --port 8000 --reload
```

Procesar un documento y verificar:
- ✅ Los representantes aparecen separados en el JSON final
- ✅ El log muestra "🔧 Separados N representantes concatenados"
- ✅ El campo `en_calidad` está en singular

---

## 🎯 Ventajas del post-processing

### ¿Por qué no confiar solo en el prompt?

1. **Los LLMs no son 100% confiables** - Gemini puede ignorar instrucciones
2. **Post-processing es determinista** - Siempre funciona igual
3. **No aumenta costos** - Se ejecuta localmente, sin tokens adicionales
4. **Más robusto** - Funciona incluso si cambiamos de modelo

### Arquitectura híbrida:

```
PROMPT (instrucciones)
      ↓
   Gemini
      ↓
POST-PROCESSING (garantía)
      ↓
   Resultado correcto
```

---

## 📁 Archivos modificados

### `app/extractor.py`

**Líneas 890-989:** Nueva función `_separar_representantes_concatenados()`

**Línea 959:** Llamada automática al post-processing
```python
# POST-PROCESSING: Separar representantes concatenados
if json_data:
    json_data = self._separar_representantes_concatenados(json_data)
```

### `CAMBIOS_GEMINI_V2.md`

Actualizado con documentación del fix.

### `TEST_POST_PROCESSING.py` (NUEVO)

Script de prueba con 4 casos de prueba.

---

## ✅ Estado actual

- ✅ Post-processing implementado
- ✅ Casos de prueba creados
- ✅ Documentación actualizada
- ⏳ **Pendiente:** Probar con documento real

---

## 🔄 Próximos pasos

1. **Reiniciar servidor** con los cambios
2. **Procesar documento real** que tenga múltiples representantes
3. **Verificar JSON** de salida
4. **Validar logs** para confirmar separación automática

---

## 📚 Referencias

- `CAMBIOS_GEMINI_V2.md` - Changelog completo de v2
- `GEMINI_HYBRID.md` - Arquitectura híbrida
- `TEST_POST_PROCESSING.py` - Script de prueba
