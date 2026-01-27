# 🔧 FIX: Merge completo de campos de adquirientes

## 📅 Fecha: 2026-01-26

---

## ⚠️ PROBLEMA IDENTIFICADO:

Cuando **DeepSeek SÍ tenía adquirientes**, el merge con Gemini **NO estaba incluyendo** los siguientes campos:

- ❌ `rfc`
- ❌ `curp`
- ❌ `edad`
- ❌ `tipo_sociedad`

### **Síntoma:**

JSON generado por el proyecto:
```json
{
  "adquirientes": [
    {
      "nombre": "ANTONIO QUINTERO FLORES",
      "tipo": "persona",
      "actua_por": "derecho propio",
      "representante": null
      // ❌ FALTAN: estado_civil, rfc, curp, edad, tipo_sociedad
    }
  ]
}
```

JSON esperado:
```json
{
  "adquirientes": [
    {
      "nombre": "ANTONIO QUINTERO FLORES",
      "tipo": "persona",
      "actua_por": "derecho propio",
      "estado_civil": "CASADO",
      "tipo_sociedad": "SOCIEDAD LEGAL",
      "edad": false,
      "rfc": "QUFA670718TK2",
      "curp": "QUFA670718HJCNLN04",
      "representante": null
    }
  ]
}
```

---

## 🔍 CAUSA RAÍZ:

El código tenía **dos rutas de merge** para adquirientes:

### **Ruta A: DeepSeek SÍ tiene adquirientes** (líneas 1230-1270)
Mergeaba SOLO:
- ✅ `nombre`
- ✅ `tipo`
- ✅ `representante`
- ✅ `estado_civil`

**FALTABAN:**
- ❌ `rfc`
- ❌ `curp`
- ❌ `edad`
- ❌ `tipo_sociedad`

### **Ruta B: DeepSeek NO tiene adquirientes** (líneas 1273-1287)
Mergeaba TODOS los campos:
- ✅ `nombre`
- ✅ `tipo`
- ✅ `representante`
- ✅ `estado_civil`
- ✅ `rfc`
- ✅ `curp`
- ✅ `edad`
- ✅ `tipo_sociedad`

**El problema:** La mayoría de documentos caen en **Ruta A** (DeepSeek detecta adquirientes), por lo que los 4 campos faltantes nunca se mergeaban.

---

## ✅ SOLUCIÓN IMPLEMENTADA:

### **Archivo modificado:**
`app/extractor.py` - Líneas 1267-1291

### **Cambio realizado:**

**ANTES:**
```python
# Gemini también puede traer estado_civil (versiones futuras)
if gemini_adq.get("estado_civil"):
    deepseek_adq["estado_civil"] = gemini_adq["estado_civil"]
    print(f"   ✅ Adquiriente[{i}].estado_civil ← Gemini")

else:
    # DeepSeek no tiene adquirientes...
```

**DESPUÉS:**
```python
# Gemini también puede traer estado_civil
if gemini_adq.get("estado_civil"):
    deepseek_adq["estado_civil"] = gemini_adq["estado_civil"]
    print(f"   ✅ Adquiriente[{i}].estado_civil ← Gemini")

# Gemini también puede traer tipo_sociedad
if gemini_adq.get("tipo_sociedad"):
    deepseek_adq["tipo_sociedad"] = gemini_adq["tipo_sociedad"]
    print(f"   ✅ Adquiriente[{i}].tipo_sociedad ← Gemini")

# Gemini también puede traer edad
if gemini_adq.get("edad"):
    deepseek_adq["edad"] = gemini_adq["edad"]
    print(f"   ✅ Adquiriente[{i}].edad ← Gemini")

# Gemini también puede traer rfc
if gemini_adq.get("rfc"):
    deepseek_adq["rfc"] = gemini_adq["rfc"]
    print(f"   ✅ Adquiriente[{i}].rfc ← Gemini")

# Gemini también puede traer curp
if gemini_adq.get("curp"):
    deepseek_adq["curp"] = gemini_adq["curp"]
    print(f"   ✅ Adquiriente[{i}].curp ← Gemini")

else:
    # DeepSeek no tiene adquirientes...
```

---

## 📊 COMPORTAMIENTO DESPUÉS DEL FIX:

### **Ahora AMBAS rutas mergean TODOS los campos:**

| Campo | Ruta A (DeepSeek SÍ tiene) | Ruta B (DeepSeek NO tiene) |
|-------|---------------------------|----------------------------|
| `nombre` | ✅ Mergeado | ✅ Mergeado |
| `tipo` | ✅ Mergeado | ✅ Mergeado |
| `actua_por` | ✅ Mergeado | ✅ Mergeado |
| `representante` | ✅ Mergeado | ✅ Mergeado |
| `estado_civil` | ✅ Mergeado | ✅ Mergeado |
| `tipo_sociedad` | ✅ **AHORA SÍ** | ✅ Mergeado |
| `edad` | ✅ **AHORA SÍ** | ✅ Mergeado |
| `rfc` | ✅ **AHORA SÍ** | ✅ Mergeado |
| `curp` | ✅ **AHORA SÍ** | ✅ Mergeado |

---

## 🎯 RESULTADO ESPERADO:

Después del fix, cuando Gemini extraiga estos campos, aparecerán en el JSON final:

```json
{
  "adquirientes": [
    {
      "nombre": "ANTONIO QUINTERO FLORES",
      "tipo": "persona",
      "actua_por": "derecho propio",
      "estado_civil": "CASADO",
      "tipo_sociedad": "SOCIEDAD LEGAL",
      "edad": false,
      "rfc": "QUFA670718TK2",
      "curp": "QUFA670718HJCNLN04",
      "representante": null
    }
  ]
}
```

---

## 📝 LOGS ESPERADOS:

Cuando se procese un documento con estos campos, los logs mostrarán:

```
🔀 Mergeando DeepSeek + Gemini...
   🔧 Gemini retornó 2 adquirientes separados
   ✅ Adquiriente[0].nombre ← Gemini
   ✅ Adquiriente[0].tipo ← Gemini (persona)
   ✅ Adquiriente[0].representante ← Gemini (null)
   ✅ Adquiriente[0].estado_civil ← Gemini
   ✅ Adquiriente[0].tipo_sociedad ← Gemini
   ✅ Adquiriente[0].rfc ← Gemini
   ✅ Adquiriente[0].curp ← Gemini
   ✅ Adquiriente[1].nombre ← Gemini
   ✅ Adquiriente[1].tipo ← Gemini (persona)
   ✅ Adquiriente[1].representante ← Gemini (null)
   ✅ Adquiriente[1].estado_civil ← Gemini
   ✅ Adquiriente[1].tipo_sociedad ← Gemini
   ✅ Adquiriente[1].rfc ← Gemini
   ✅ Adquiriente[1].curp ← Gemini
```

---

## ⚠️ NOTA IMPORTANTE:

Este fix **solo funcionará si Gemini está extrayendo estos campos**.

Si Gemini **NO los extrae**, los campos tendrán su valor por defecto del modelo Pydantic:
- `estado_civil`: `false`
- `tipo_sociedad`: `false`
- `edad`: `false`
- `rfc`: `false`
- `curp`: `false`

Para que Gemini extraiga estos campos, asegúrate de que:
1. ✅ Los prompts de Gemini pidan estos campos (ya actualizado en `CAMBIOS_GEMINI_CAMPOS_EXCLUSIVOS.md`)
2. ✅ Estés usando el prompt "completo" o "expandido" de Gemini (no solo el "crítico")

---

## 🧪 VERIFICACIÓN:

Para verificar que el fix funciona:

```bash
# Reiniciar servidor
uvicorn app.api:app --host 0.0.0.0 --port 8000 --reload
```

Procesar documento con adquirientes que tengan RFC/CURP y verificar:
1. ✅ Los logs muestran "✅ Adquiriente[i].rfc ← Gemini"
2. ✅ Los logs muestran "✅ Adquiriente[i].curp ← Gemini"
3. ✅ El JSON final incluye estos campos con sus valores
4. ✅ Si no existen en el documento, aparecen como `false` (no ausentes)

---

## 📚 ARCHIVOS RELACIONADOS:

- `CAMBIOS_GEMINI_CAMPOS_EXCLUSIVOS.md` - Actualización de prompts de Gemini
- `CAMBIOS_CAMPOS_SOLO_ADQUIRIENTES.md` - Campos exclusivos de adquirientes
- `FIX_ELIMINAR_CAMPO_CURPS_RAIZ.md` - Eliminación de campo obsoleto curps
