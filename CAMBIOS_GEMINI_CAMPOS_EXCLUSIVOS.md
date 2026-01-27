# 🔧 CAMBIOS: Gemini - Campos exclusivos para adquirientes

## 📅 Fecha: 2026-01-26

---

## ⚠️ CAMBIO IMPLEMENTADO:

Actualización de **todos los prompts de Gemini** para que NO extraiga los siguientes campos para **TITULARES**:

1. ❌ `rfc`
2. ❌ `curp`
3. ❌ `edad`
4. ❌ `estado_civil`
5. ❌ `tipo_sociedad`

Estos campos **SOLO se extraen para ADQUIRIENTES**.

---

## 📊 ESTRUCTURA CORRECTA:

### **TITULAR (Vendedor) - Gemini:**
```json
{
  "titular": {
    "nombre": "INSTITUTO NACIONAL DEL SUELO",
    "tipo": "empresa",
    "representante": {
      "nombre": "ERNESTO PADILLA",
      "en_calidad": "apoderado legal",
      "escritura": "63",
      "fecha_poder": "4/15/2020"
    }
  }
}
```

**Campos del titular (Gemini):**
- ✅ `nombre`
- ✅ `tipo`
- ✅ `representante`

**NO incluye:** rfc, curp, edad, estado_civil, tipo_sociedad

---

### **ADQUIRIENTE (Comprador) - Gemini:**
```json
{
  "adquiriente": {
    "nombre": "ANGELBERTA PEREZ SOTO",
    "tipo": "persona",
    "estado_civil": "casada",
    "rfc": false,
    "curp": false,
    "edad": false,
    "tipo_sociedad": false,
    "representante": null
  }
}
```

**Campos del adquiriente (Gemini):**
- ✅ `nombre`
- ✅ `tipo`
- ✅ `representante`
- ✅ `estado_civil` → `false` si no existe
- ✅ `rfc` → `false` si no existe
- ✅ `curp` → `false` si no existe
- ✅ `edad` → `false` si no existe
- ✅ `tipo_sociedad` → `false` si no existe

---

## 🔧 ARCHIVOS MODIFICADOS:

### **utils/gemini_prompts.py**

#### ✅ Prompt crítico (líneas 109-176)

**Cambio 1 - Nueva sección de campos exclusivos:**
```python
⚠️ CAMPOS EXCLUSIVOS POR TIPO DE ENTIDAD:
==========================================

TITULAR (vendedor):
- nombre
- tipo
- representante

ADQUIRIENTE (comprador):
- nombre
- tipo
- representante
- estado_civil (casado/soltero/divorciado/viudo) - SI APARECE
- rfc - SI APARECE
- curp - SI APARECE
- edad - SI APARECE
- tipo_sociedad (separación de bienes/sociedad conyugal) - SI APARECE
```

**Cambio 2 - Plantilla actualizada:**
```python
"adquiriente": {
  "nombre": "NOMBRE COMPLETO DEL COMPRADOR",
  "tipo": "empresa" o "persona",
  "estado_civil": "..." o false,
  "rfc": "..." o false,
  "curp": "..." o false,
  "edad": X o false,
  "tipo_sociedad": "..." o false,
  "representante": null o {...}
}
```

**Cambio 3 - Reglas actualizadas:**
```python
- TITULAR: SOLO extrae nombre, tipo, representante (NO rfc, curp, edad, estado_civil, tipo_sociedad)
- ADQUIRIENTE: Extrae rfc, curp, edad, estado_civil, tipo_sociedad SOLO SI APARECEN (sino usa false)
- Usa null para representante, usa false para campos que no existan
```

---

#### ✅ Prompt expandido (líneas 208-303)

**Cambio 1 - Nueva sección de campos:**
```python
⚠️ CAMPOS POR TIPO DE ENTIDAD:
- TITULAR: nombre, tipo, representante
- ADQUIRIENTE: nombre, tipo, representante, estado_civil, rfc, curp, edad, tipo_sociedad

⚠️ CAMPOS EXCLUSIVOS DE ADQUIRIENTE:
- estado_civil, rfc, curp, edad, tipo_sociedad → SOLO extraer para ADQUIRIENTE
- Si NO aparecen en el documento → usa false (NO null)
```

**Cambio 2 - Plantilla actualizada:**
```python
"adquiriente": {
  "nombre": "NOMBRE COMPRADOR",
  "tipo": "empresa" o "persona",
  "estado_civil": "..." o false,
  "rfc": "..." o false,
  "curp": "..." o false,
  "edad": X o false,
  "tipo_sociedad": "..." o false,
  "representante": null o {...}
}
```

**Cambio 3 - Reglas actualizadas:**
```python
- TITULAR: SOLO extrae nombre, tipo, representante (NO rfc, curp, edad, estado_civil, tipo_sociedad)
- ADQUIRIENTE: Extrae rfc, curp, edad, estado_civil, tipo_sociedad SOLO SI APARECEN (sino usa false)
- Usa null para representante/municipio/monto, usa false para campos de adquiriente que no existan
```

---

#### ✅ Prompt completo (líneas 333-397)

**Cambio 1 - Descripción de campos:**
```python
1. TITULAR (VENDEDOR):
   - Nombre completo
   - Tipo (empresa/persona)
   - Representante (si existe): nombre, en_calidad, escritura, fecha_poder
   ⚠️ NO EXTRAER: rfc, curp, edad, estado_civil, tipo_sociedad

2. ADQUIRIENTE (COMPRADOR):
   - Nombre completo
   - Tipo (empresa/persona)
   - Estado civil (casado/soltero/divorciado/viudo) - SI APARECE
   - RFC - SI APARECE
   - CURP - SI APARECE
   - Edad - SI APARECE
   - Tipo de sociedad (separación de bienes/sociedad conyugal) - SI APARECE
   - Representante (si existe)
```

**Cambio 2 - Reglas:**
```python
- TITULAR: SOLO nombre, tipo, representante (NO rfc, curp, edad, estado_civil, tipo_sociedad)
- ADQUIRIENTE: Incluye rfc, curp, edad, estado_civil, tipo_sociedad → false si no aparecen
```

**Cambio 3 - Plantilla:**
```python
"adquiriente": {
  "nombre": "...",
  "tipo": "empresa" o "persona",
  "estado_civil": "..." o false,
  "rfc": "..." o false,
  "curp": "..." o false,
  "edad": X o false,
  "tipo_sociedad": "..." o false,
  "representante": null o {...}
}
```

---

## 📋 CASOS DE USO:

### ✅ Caso 1: Titular empresa + Adquiriente persona con RFC

**Input (documento):**
```
Comparece INSTITUTO NACIONAL DEL SUELO, representado por ERNESTO PADILLA,
quien VENDE a DARINKA CAMBEROS MARTINEZ, soltera, RFC: CAMD871009DL2,
CURP: CAMD871009MNTMRR08, quien ADQUIERE...
```

**Output esperado:**
```json
{
  "titular": {
    "nombre": "INSTITUTO NACIONAL DEL SUELO",
    "tipo": "empresa",
    "representante": {
      "nombre": "ERNESTO PADILLA",
      "en_calidad": "representante legal",
      "escritura": null,
      "fecha_poder": null
    }
  },
  "adquiriente": {
    "nombre": "DARINKA CAMBEROS MARTINEZ",
    "tipo": "persona",
    "estado_civil": "soltera",
    "rfc": "CAMD871009DL2",
    "curp": "CAMD871009MNTMRR08",
    "edad": false,
    "tipo_sociedad": false,
    "representante": null
  }
}
```

---

### ✅ Caso 2: Titular persona + Adquiriente sin datos adicionales

**Input (documento):**
```
Comparece NORMA CELIS, quien VENDE a GABRIEL VIZCARRA, quien ADQUIERE...
```

**Output esperado:**
```json
{
  "titular": {
    "nombre": "NORMA CELIS",
    "tipo": "persona",
    "representante": null
  },
  "adquiriente": {
    "nombre": "GABRIEL VIZCARRA",
    "tipo": "persona",
    "estado_civil": false,
    "rfc": false,
    "curp": false,
    "edad": false,
    "tipo_sociedad": false,
    "representante": null
  }
}
```

---

## 🎯 BENEFICIOS:

1. ✅ **Alineación completa** - DeepSeek y Gemini usan la misma regla
2. ✅ **Optimización** - Gemini no pierde tokens extrayendo campos innecesarios
3. ✅ **Consistencia** - Mismo comportamiento en los 3 niveles de prompts (crítico, expandido, completo)
4. ✅ **Claridad** - Instrucciones explícitas sobre qué NO extraer para titulares

---

## 🔄 COMPATIBILIDAD:

Estos cambios son **100% compatibles** con:

1. ✅ Modelo Pydantic `TitularFlexible` (ya no tiene esos campos)
2. ✅ Modelo Pydantic `AdquirienteFlexible` (tiene esos campos con `default=False`)
3. ✅ Prompts de DeepSeek (ya actualizados previamente)
4. ✅ Lógica de merge en `extractor.py`

---

## ✅ VERIFICACIÓN:

Para verificar que los cambios funcionen correctamente:

```bash
# Reiniciar servidor
uvicorn app.api:app --host 0.0.0.0 --port 8000 --reload
```

Procesar documento y verificar:

1. ✅ **Titular NO tiene** rfc, curp, edad, estado_civil, tipo_sociedad en el JSON de Gemini
2. ✅ **Adquiriente SÍ tiene** estos campos (con valores extraídos o `false`)
3. ✅ Logs muestran que Gemini retorna formato correcto
4. ✅ Merge funciona correctamente sin errores

---

## 📝 NOTAS IMPORTANTES:

### **Diferencia entre `null` y `false`:**

| Campo | Tipo | Valor cuando NO existe |
|-------|------|------------------------|
| `representante` | Objeto | `null` |
| `municipio` | String | `null` |
| `monto_operacion` | String | `null` |
| `estado_civil` | String/bool | `false` |
| `rfc` | String/bool | `false` |
| `curp` | String/bool | `false` |
| `edad` | Int/bool | `false` |
| `tipo_sociedad` | String/bool | `false` |

**Razón:** Los campos simples de adquiriente usan `false` para indicar ausencia, mientras que objetos/strings opcionales usan `null`.

---

## 📚 ARCHIVOS RELACIONADOS:

- `CAMBIOS_CAMPOS_SOLO_ADQUIRIENTES.md` - Cambios en modelos Pydantic y prompts DeepSeek
- `CAMBIOS_REPRESENTANTE_SINGULAR.md` - Cambios de representantes plural → singular
- `FIX_TITULARES_ADQUIRIENTES_CONCATENADOS.md` - Post-processing de concatenación

---

## 🧪 PRUEBAS RECOMENDADAS:

1. Procesar documento con titular empresa + adquiriente persona con RFC/CURP
2. Procesar documento con titular persona + adquiriente sin datos adicionales
3. Verificar que Gemini NO retorna campos prohibidos en titulares
4. Verificar que adquirientes tienen `false` para campos no encontrados
