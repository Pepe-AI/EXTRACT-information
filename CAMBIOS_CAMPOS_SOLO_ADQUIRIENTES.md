# 🔧 CAMBIOS: Campos exclusivos para adquirientes

## 📅 Fecha: 2026-01-25

---

## ⚠️ CAMBIO IMPLEMENTADO:

Los siguientes campos ahora son **EXCLUSIVOS para adquirientes** y **NO se extraen para titulares**:

1. ✅ `estado_civil`
2. ✅ `tipo_sociedad`
3. ✅ `edad`
4. ✅ `rfc`
5. ✅ `curp`

**Valor por defecto:** Si NO existen en el documento → `false`

---

## 📊 ESTRUCTURA CORRECTA:

### **TITULAR (Vendedor):**
```json
{
  "nombre": "INSTITUTO NACIONAL DEL SUELO",
  "tipo": "empresa",
  "actua_por": "representación",
  "representante": {
    "nombre": "ERNESTO PADILLA",
    "en_calidad": "apoderado legal",
    "escritura": "63",
    "bis": false,
    "fecha_poder": "4/15/2020"
  }
}
```

**Campos del titular:**
- ✅ `nombre` (obligatorio)
- ✅ `tipo` (obligatorio: "empresa" o "persona")
- ✅ `actua_por` (obligatorio)
- ✅ `representante` (obligatorio si empresa, opcional si persona, `null` si no existe)

---

### **ADQUIRIENTE (Comprador):**
```json
{
  "nombre": "ANGELBERTA PEREZ SOTO",
  "tipo": "persona",
  "actua_por": "gestor oficioso",
  "estado_civil": "casada",
  "tipo_sociedad": false,
  "edad": false,
  "rfc": false,
  "curp": false,
  "representante": {
    "nombre": "MARIA GUADALUPE HILDA BERNAL",
    "en_calidad": "gestor",
    "escritura": null,
    "bis": false,
    "fecha_poder": null
  }
}
```

**Campos del adquiriente:**
- ✅ `nombre` (obligatorio)
- ✅ `tipo` (obligatorio: "empresa" o "persona")
- ✅ `actua_por` (obligatorio)
- ✅ `estado_civil` (false si no existe)
- ✅ `tipo_sociedad` (false si no existe)
- ✅ `edad` (false si no existe)
- ✅ `rfc` (false si no existe)
- ✅ `curp` (false si no existe)
- ✅ `representante` (obligatorio si empresa, opcional si persona, `null` si no existe)

---

## 🔧 CAMBIOS REALIZADOS:

### **1. Modelo Pydantic (models/escritura.py)**

#### ✅ TitularFlexible (líneas 56-64):
```python
class TitularFlexible(BaseModel):
    """Titular con todos los campos opcionales."""

    nombre: Optional[str] = Field(default=NO_ENCONTRADO)
    tipo: Optional[str] = Field(default=None)
    actua_por: Optional[str] = Field(default=NO_ENCONTRADO)
    representante: Optional[RepresentanteFlexible] = Field(default=None)

    # ❌ NO tiene: estado_civil, tipo_sociedad, edad, rfc, curp
```

#### ✅ AdquirienteFlexible (líneas 67-80):
```python
class AdquirienteFlexible(BaseModel):
    """Adquiriente con todos los campos opcionales."""

    nombre: Optional[str] = Field(default=NO_ENCONTRADO)
    tipo: Optional[str] = Field(default=None)
    actua_por: Optional[str] = Field(default=NO_ENCONTRADO)
    estado_civil: Optional[Union[str, bool]] = Field(default=False)  # ← false por defecto
    tipo_sociedad: Optional[Union[str, bool]] = Field(default=False)  # ← false por defecto
    edad: Optional[Union[int, bool]] = Field(default=False)  # ← false por defecto
    rfc: Optional[Union[str, bool]] = Field(default=False)  # ← false por defecto
    curp: Optional[Union[str, bool]] = Field(default=False)  # ← false por defecto
    representante: Optional[RepresentanteFlexible] = Field(default=None)  # ← null por defecto
```

**Cambio principal:** Valores por defecto cambiados de `None` → `False` para los 5 campos exclusivos.

---

### **2. Prompts de DeepSeek (utils/prompt_builder.py)**

#### ✅ Plantilla actualizada (líneas 587-598):
```python
"adquirientes": [
    {
        "nombre": "NOMBRE",
        "tipo": "empresa" o "persona",
        "actua_por": "derecho propio" o "representación",
        "estado_civil": false,  // false si no existe
        "tipo_sociedad": false,  // false si no existe
        "edad": false,           // false si no existe
        "rfc": false,            // false si no existe
        "curp": false,           // false si no existe
        "representante": null o {objeto}
    }
]
```

#### ✅ Reglas actualizadas (líneas 605-614):
```
REGLAS IMPORTANTES:
===================
1. TITULARES: Solo necesitan nombre, tipo, actua_por, representante
2. ADQUIRIENTES: Además de lo anterior, incluyen estado_civil, tipo_sociedad, edad, rfc, curp
3. Si titular/adquiriente es EMPRESA → representante es OBLIGATORIO
4. Si titular/adquiriente es PERSONA → representante es OPCIONAL
5. Para campos estado_civil, tipo_sociedad, edad, rfc, curp en adquirientes:
   - Si NO existen en el documento → usa "false"
   - Si SÍ existen → extrae el valor
```

---

## 📋 CASOS DE USO:

### ✅ Caso 1: Titular empresa + Adquiriente persona

```json
{
  "titulares": [
    {
      "nombre": "INSTITUTO NACIONAL DEL SUELO",
      "tipo": "empresa",
      "actua_por": "representación",
      "representante": {
        "nombre": "ERNESTO PADILLA",
        "en_calidad": "representante legal",
        "escritura": "63",
        "bis": false,
        "fecha_poder": "4/15/2020"
      }
    }
  ],
  "adquirientes": [
    {
      "nombre": "ANGELBERTA PEREZ SOTO",
      "tipo": "persona",
      "actua_por": "derecho propio",
      "estado_civil": "casada",
      "tipo_sociedad": false,
      "edad": false,
      "rfc": false,
      "curp": false,
      "representante": null
    }
  ]
}
```

---

### ✅ Caso 2: Dos titulares personas + Adquiriente con RFC

```json
{
  "titulares": [
    {
      "nombre": "NORMA CELIS",
      "tipo": "persona",
      "actua_por": "derecho propio",
      "representante": null
    },
    {
      "nombre": "GABRIEL VIZCARRA",
      "tipo": "persona",
      "actua_por": "derecho propio",
      "representante": null
    }
  ],
  "adquirientes": [
    {
      "nombre": "DARINKA CAMBEROS MARTINEZ",
      "tipo": "persona",
      "actua_por": "derecho propio",
      "estado_civil": "soltera",
      "tipo_sociedad": false,
      "edad": false,
      "rfc": "CAMD871009DL2",
      "curp": "CAMD871009MNTMRR08",
      "representante": null
    }
  ]
}
```

---

## 🎯 BENEFICIOS:

1. ✅ **Optimización** - No se pierden tokens extrayendo campos innecesarios para titulares
2. ✅ **Claridad** - El modelo refleja la realidad: estos datos solo se piden a compradores
3. ✅ **Consistencia** - Valores por defecto claros (`false` vs `null`)
4. ✅ **Simplicidad** - Menos campos en titular = menos confusión

---

## 📝 NOTAS IMPORTANTES:

### **¿Por qué `false` y no `null`?**

| Campo | Valor cuando NO existe |
|-------|------------------------|
| `estado_civil` | `false` |
| `tipo_sociedad` | `false` |
| `edad` | `false` |
| `rfc` | `false` |
| `curp` | `false` |
| `representante` | `null` ← Objeto |

**Razón:** Los campos simples (string/int) usan `false` para indicar ausencia, mientras que objetos anidados como `representante` usan `null` porque representan estructuras completas.

---

### **¿Por qué estos campos solo en adquirientes?**

En el contexto legal de escrituras públicas mexicanas:

1. **RFC/CURP**: Se requieren del **comprador** para efectos fiscales (pago de impuestos)
2. **Estado civil**: Relevante para el **comprador** para determinar régimen patrimonial
3. **Edad**: Se verifica para el **comprador** (mayoría de edad para contratar)
4. **Tipo sociedad**: Relevante para el **comprador** casado (separación/sociedad conyugal)

El **vendedor (titular)** ya es propietario, no necesita esta información en la transacción.

---

## ✅ VERIFICACIÓN:

Para verificar que los cambios funcionen:

```bash
# Reiniciar servidor
uvicorn app.api:app --host 0.0.0.0 --port 8000 --reload
```

Procesar documento y verificar:
- ✅ Titulares NO tienen campos estado_civil, rfc, curp, edad, tipo_sociedad
- ✅ Adquirientes SÍ tienen estos campos
- ✅ Si no existen → valor es `false`
- ✅ Si existen → valor es el extraído del documento
- ✅ `representante` sigue siendo `null` cuando no existe

---

## 📁 ARCHIVOS MODIFICADOS:

1. ✅ `models/escritura.py` (líneas 67-80)
   - Valores por defecto cambiados a `false`
   - Tipos actualizados a `Union[str, bool]` o `Union[int, bool]`

2. ✅ `utils/prompt_builder.py` (líneas 587-614)
   - Plantilla actualizada con comentarios claros
   - Reglas actualizadas para distinguir titular vs adquiriente
