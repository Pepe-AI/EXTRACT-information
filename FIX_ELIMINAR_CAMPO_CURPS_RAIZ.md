# 🔧 FIX: Eliminar campo obsoleto `curps` de la raíz del JSON

## 📅 Fecha: 2026-01-26

---

## ⚠️ PROBLEMA IDENTIFICADO:

El sistema estaba extrayendo **CURP y RFC de manera incorrecta**:

### ❌ Formato INCORRECTO (antes):
```json
{
  "numero_escritura": 16327,
  "curps": [
    "AURR610917HNTGJB00",
    "BOBI661114MNTRRR07",
    "PAGR781112HNTRRF09"
  ],
  "titulares": [
    {
      "nombre": "RUBÉN AGUIRRE ROJO",
      "tipo": "persona"
    }
  ],
  "adquirientes": [
    {
      "nombre": "RAFAEL PARTIDA GARCÍA",
      "tipo": "persona",
      "estado_civil": null
    }
  ]
}
```

**Problemas:**
1. ❌ Los CURPs están en un **array en la raíz** (`"curps": []`)
2. ❌ No se sabe **a quién pertenece cada CURP**
3. ❌ Los adquirientes **NO tienen** su campo `curp` individual
4. ❌ El campo `estado_civil` es `null` en lugar de `false`

---

## ✅ FORMATO CORRECTO (después):

```json
{
  "numero_escritura": 16327,
  "titulares": [
    {
      "nombre": "RUBÉN AGUIRRE ROJO",
      "tipo": "persona",
      "actua_por": "derecho propio",
      "representante": null
    },
    {
      "nombre": "IRMA YOLANDA BORRAYO BORRAYO",
      "tipo": "persona",
      "actua_por": "derecho propio",
      "representante": null
    }
  ],
  "adquirientes": [
    {
      "nombre": "RAFAEL PARTIDA GARCÍA",
      "tipo": "persona",
      "actua_por": "derecho propio",
      "estado_civil": false,
      "rfc": false,
      "curp": "PAGR781112HNTRRF09",
      "edad": false,
      "tipo_sociedad": false,
      "representante": null
    }
  ]
}
```

**Mejoras:**
1. ✅ Cada adquiriente tiene **su propio campo `curp`**
2. ✅ Los CURPs están **asociados a la persona correcta**
3. ✅ El campo `estado_civil` usa `false` cuando no existe
4. ✅ No hay campo `curps` obsoleto en la raíz

---

## 🔍 CAUSA RAÍZ:

El campo `curps` (array en raíz) era un **campo obsoleto** que estaba:

1. **En el modelo Pydantic** (`models/escritura.py`):
   ```python
   curps: Optional[List[str]] = Field(default_factory=list)
   ```

2. **En los prompts de DeepSeek** (`utils/prompt_builder.py`):
   ```json
   {
     "adquirientes": [...],
     "monto_operacion": "$X,XXX.XX",
     "curps": []  ← CAMPO OBSOLETO
   }
   ```

3. **En la extracción por regex** (`utils/text_processing.py`):
   ```python
   "curps": extraer_curp_todos(texto),  # Extraía TODOS los CURPs en un array
   ```

4. **En campos permitidos** (`utils/prompt_builder.py`):
   ```python
   CAMPOS_RAIZ_PERMITIDOS = {
       ..., "curps"  ← PERMITIDO INCORRECTAMENTE
   }
   ```

**Resultado:** El LLM interpretaba que debía extraer todos los CURPs en un array separado, en lugar de asignar cada CURP a su respectivo adquiriente.

---

## 🔧 CAMBIOS REALIZADOS:

### **1. models/escritura.py**

#### ✅ Línea 102 - Eliminado campo `curps` de EscrituraPublicaFlexible:
```python
# ANTES:
titulares: Optional[List[TitularFlexible]] = Field(default_factory=list)
adquirientes: Optional[List[AdquirienteFlexible]] = Field(default_factory=list)
monto_operacion: Optional[str] = Field(default=NO_ENCONTRADO)
valor_catastral: Optional[str] = Field(default=None)
curps: Optional[List[str]] = Field(default_factory=list)  # ❌ OBSOLETO

# DESPUÉS:
titulares: Optional[List[TitularFlexible]] = Field(default_factory=list)
adquirientes: Optional[List[AdquirienteFlexible]] = Field(default_factory=list)
monto_operacion: Optional[str] = Field(default=NO_ENCONTRADO)
valor_catastral: Optional[str] = Field(default=None)
```

#### ✅ Línea 180-181 - Eliminado de generar_reporte():
```python
# ANTES:
if self.curps:
    encontrados["curps"] = self.curps

# DESPUÉS:
# (eliminado completamente)
```

#### ✅ Línea 294 - Eliminado de EscrituraPublica (modelo estricto):
```python
# ANTES:
monto_operacion: str = Field(..., description="Monto de la operación")
valor_catastral: Optional[str] = Field(default=None)
curps: Optional[List[str]] = Field(default_factory=list)  # ❌ OBSOLETO

# DESPUÉS:
monto_operacion: str = Field(..., description="Monto de la operación")
valor_catastral: Optional[str] = Field(default=None)
```

#### ✅ Línea 421 - Eliminado de get_campos_no_obligatorios():
```python
# ANTES:
return ["valor_catastral", "curps"]

# DESPUÉS:
return ["valor_catastral"]
```

---

### **2. utils/prompt_builder.py**

#### ✅ Línea 36 - Eliminado de CAMPOS_RAIZ_PERMITIDOS:
```python
# ANTES:
CAMPOS_RAIZ_PERMITIDOS = {
    "numero_escritura", "fecha_documento", "numero_notaria",
    "municipio", "nombre_notario", "tipo_titular",
    "titulares", "adquirientes", "monto_operacion", "valor_catastral", "curps"
}

# DESPUÉS:
CAMPOS_RAIZ_PERMITIDOS = {
    "numero_escritura", "fecha_documento", "numero_notaria",
    "municipio", "nombre_notario", "tipo_titular",
    "titulares", "adquirientes", "monto_operacion", "valor_catastral"
}
```

#### ✅ Línea 493 - Agregado a CAMPOS PROHIBIDOS:
```python
CAMPOS PROHIBIDOS (NUNCA LOS USES):
- representante_legal (el representante va DENTRO del objeto "representante")
- notario (como array u objeto)
- rfcs (como array en raíz - el rfc va DENTRO de cada adquiriente)
- curps (como array en raíz - el curp va DENTRO de cada adquiriente)  ← NUEVO
- gestora_negocios
...
```

#### ✅ Líneas 400, 439, 472, 602, 723 - Eliminado de TODOS los ejemplos JSON:
```python
# ANTES:
{
    "adquirientes": [...],
    "monto_operacion": "$X,XXX.XX",
    "valor_catastral": null,
    "curps": []  # ❌ OBSOLETO
}

# DESPUÉS:
{
    "adquirientes": [...],
    "monto_operacion": "$X,XXX.XX",
    "valor_catastral": null
}
```

**Total de ejemplos actualizados:** 5
- EJEMPLO_JSON_EMPRESA_1
- EJEMPLO_JSON_EMPRESA_2
- EJEMPLO_JSON_PERSONA
- Plantilla principal del prompt
- Plantilla del prompt de corrección

---

### **3. utils/text_processing.py**

#### ✅ Línea 1431 - Eliminado del tipo de retorno:
```python
# ANTES:
Returns:
    Dict con todos los campos extraídos:
    {
        "numero_escritura": int | None,
        ...
        "curps": List[str],  # ❌ OBSOLETO
    }

# DESPUÉS:
Returns:
    Dict con todos los campos extraídos:
    {
        "numero_escritura": int | None,
        ...
    }
```

#### ✅ Línea 1449 - Eliminada extracción por regex:
```python
# ANTES:
"municipio": extraer_municipio(texto),

# Listas de identificadores
"curps": extraer_curp_todos(texto),  # ❌ OBSOLETO

# Campos de poder/instrumento

# DESPUÉS:
"municipio": extraer_municipio(texto),

# Campos de poder/instrumento
```

---

### **4. extraction/sistema_confianza.py**

#### ✅ Línea 97-99 - Eliminado manejo especial de listas:
```python
# ANTES:
for nombre, valor in datos_regex.items():
    # Manejar listas especiales
    if nombre in ["curps"]:  # ❌ OBSOLETO
        self._listas[nombre] = valor if isinstance(valor, list) else []
        continue

    # Solo agregar si tiene valor válido

# DESPUÉS:
for nombre, valor in datos_regex.items():
    # Solo agregar si tiene valor válido
```

---

## 📋 NUEVO COMPORTAMIENTO:

### **CURP y RFC ahora se extraen:**

1. ✅ **Por LLM** (DeepSeek o Gemini) → Dentro del campo `curp` de cada **adquiriente**
2. ✅ **Asociados a la persona correcta**
3. ✅ **Valor por defecto:** `false` si no existe (NO `null`)

### **Ejemplo de extracción correcta:**

**Documento:**
```
Comparece RAFAEL PARTIDA GARCÍA, CURP: PAGR781112HNTRRF09, quien ADQUIERE...
```

**JSON resultante:**
```json
{
  "adquirientes": [
    {
      "nombre": "RAFAEL PARTIDA GARCÍA",
      "tipo": "persona",
      "curp": "PAGR781112HNTRRF09",  ← Extraído por LLM
      "rfc": false,
      "estado_civil": false,
      "edad": false,
      "tipo_sociedad": false
    }
  ]
}
```

---

## 🎯 BENEFICIOS:

1. ✅ **Precisión** - Cada CURP/RFC está asociado a la persona correcta
2. ✅ **Simplicidad** - Un solo lugar para buscar CURPs (dentro de adquirientes)
3. ✅ **Consistencia** - Mismo patrón que otros campos (rfc, edad, estado_civil)
4. ✅ **Compatibilidad** - Elimina campo obsoleto que causaba confusión
5. ✅ **Optimización** - No se extraen CURPs innecesarios de titulares

---

## 📝 NOTAS IMPORTANTES:

### **¿Por qué existía el campo `curps` en la raíz?**

Era un **diseño antiguo** donde se pensaba extraer todos los CURPs del documento en un array y luego asignarlos manualmente. Esto causaba:
- Confusión sobre a quién pertenece cada CURP
- Duplicación de datos (CURP en raíz y en adquirientes)
- Complejidad adicional en el post-processing

### **¿Por qué solo se extraen para adquirientes?**

En escrituras públicas mexicanas:
- **CURP/RFC del comprador** → Necesario para efectos fiscales (pago de impuestos)
- **CURP/RFC del vendedor** → NO necesario (ya es propietario registrado)

---

## ✅ VERIFICACIÓN:

Para verificar que los cambios funcionen:

```bash
# Reiniciar servidor
uvicorn app.api:app --host 0.0.0.0 --port 8000 --reload
```

Procesar documento y verificar:

1. ✅ **NO existe** campo `"curps": []` en la raíz del JSON
2. ✅ Cada adquiriente **tiene** campo `"curp"` individual
3. ✅ Si el CURP existe → se extrae el valor
4. ✅ Si el CURP NO existe → valor es `false`
5. ✅ Los titulares **NO tienen** campo `curp`

---

## 📚 ARCHIVOS MODIFICADOS:

1. ✅ `models/escritura.py` (4 cambios)
2. ✅ `utils/prompt_builder.py` (7 cambios)
3. ✅ `utils/text_processing.py` (2 cambios)
4. ✅ `extraction/sistema_confianza.py` (1 cambio)

**Total:** 14 cambios en 4 archivos

---

## 🔗 ARCHIVOS RELACIONADOS:

- `CAMBIOS_CAMPOS_SOLO_ADQUIRIENTES.md` - Cambios de campos exclusivos para adquirientes
- `CAMBIOS_GEMINI_CAMPOS_EXCLUSIVOS.md` - Actualización de prompts de Gemini
- `CAMBIOS_REPRESENTANTE_SINGULAR.md` - Cambios de representantes plural → singular
