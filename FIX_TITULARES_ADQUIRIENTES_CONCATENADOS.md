# 🔧 FIX: Titulares, Adquirientes y Representantes concatenados

## 📅 Fecha inicial: 2026-01-23
## 🔧 Última actualización: 2026-01-24 (SOPORTE COMPLETO)

---

## ⚠️ Problemas identificados

Gemini a veces **ignora las instrucciones del prompt** y devuelve nombres concatenados en **2 niveles diferentes**:

### 🔴 PROBLEMA 1: Titulares/Adquirientes concatenados (NIVEL SUPERIOR)

**Incorrecto (Gemini retorna):**
```json
{
  "titulares": [
    {
      "nombre": "NORMA ANGELICA CELIS BERMUDEZ y GABRIEL VIZCARRA SALAZAR",
      "tipo": "persona",
      "actua_por": "derecho propio"
    }
  ]
}
```

**Correcto (esperado):**
```json
{
  "titulares": [
    {
      "nombre": "NORMA ANGELICA CELIS BERMUDEZ",
      "tipo": "persona",
      "actua_por": "derecho propio",
      "representante": null
    },
    {
      "nombre": "GABRIEL VIZCARRA SALAZAR",
      "tipo": "persona",
      "actua_por": "derecho propio",
      "representante": null
    }
  ]
}
```

**Impacto:** Si hay 2 vendedores, el sistema solo detecta 1 titular con ambos nombres concatenados.

---

### 🟡 PROBLEMA 2: Representantes concatenados (NIVEL ANIDADO)

**Incorrecto (Gemini retorna):**
```json
{
  "titular": {
    "nombre": "CONSORCIO DE INGENIERIA INTEGRAL S.A.",
    "tipo": "empresa",
    "representante": {
      "nombre": "ROSA GUZMAN Y MARGARITA FLORES",
      "en_calidad": "apoderadas legales"
    }
  }
}
```

**Correcto (esperado):**
```json
{
  "titular": {
    "nombre": "CONSORCIO DE INGENIERIA INTEGRAL S.A.",
    "tipo": "empresa",
    "representantes": [
      {
        "nombre": "ROSA GUZMAN",
        "en_calidad": "apoderada legal"
      },
      {
        "nombre": "MARGARITA FLORES",
        "en_calidad": "apoderada legal"
      }
    ]
  }
}
```

---

## ✅ Solución implementada

Agregado **post-processing automático multinivel** que detecta y separa concatenaciones en ambos niveles.

### Arquitectura de la solución:

```
Gemini Response
      ↓
parse_gemini_response()  ← Parsea JSON
      ↓
_separar_representantes_concatenados()  ← POST-PROCESSING MULTINIVEL
      ├── NIVEL 1: Detecta titular/adquiriente concatenados
      │             "NOMBRE1 y NOMBRE2" → [titular1, titular2]
      │
      └── NIVEL 2: Detecta representantes concatenados
                    "REP1 Y REP2" → [rep1, rep2]
      ↓
JSON corregido con entidades separadas
```

### Ubicación del código:

**Archivo:** `app/extractor.py`

**Líneas 890-1030:** Función `_separar_representantes_concatenados()` (actualizada)

**Línea 1061:** Llamada automática después de parsear JSON
```python
# POST-PROCESSING: Separar representantes concatenados
if json_data:
    json_data = self._separar_representantes_concatenados(json_data)
```

---

## 🔍 Cómo funciona el post-processing

### NIVEL 1: Separar titulares/adquirientes concatenados

#### Detección:
```python
nombre_principal = entidad.get("nombre", "")
if re.search(r'\s+[Yy]\s+', nombre_principal):
    # Detectó concatenación con " Y " o " y "
```

#### Separación:
```python
nombres = re.split(r'\s+[Yy]\s+', nombre_principal)
# ["NORMA CELIS", "GABRIEL VIZCARRA"]

# Crear entidades separadas
for nombre in nombres:
    entidad_copia = entidad.copy()
    entidad_copia["nombre"] = nombre
    entidades_separadas.append(entidad_copia)
```

#### Conversión de formato:
```python
# Gemini retorna "titular" (singular)
json_data["titular"] = {"nombre": "NOMBRE1 y NOMBRE2"}

# Post-processing lo convierte a "titulares" (plural)
json_data["titulares"] = [
    {"nombre": "NOMBRE1"},
    {"nombre": "NOMBRE2"}
]
```

### NIVEL 2: Separar representantes concatenados

#### Detección:
```python
rep_nombre = representante.get("nombre", "")
if re.search(r'\s+[Yy]\s+', rep_nombre):
    # Detectó concatenación
```

#### Separación + ajuste plural/singular:
```python
nombres = re.split(r'\s+[Yy]\s+', rep_nombre)

# Ajustar en_calidad: "apoderadas" → "apoderada"
en_calidad_singular = en_calidad.replace("apoderadas", "apoderada")

# Crear array de representantes
representantes = [
    {"nombre": "ROSA GUZMAN", "en_calidad": "apoderada legal"},
    {"nombre": "MARGARITA FLORES", "en_calidad": "apoderada legal"}
]
```

---

## 📊 Casos de prueba

### ✅ Test 1: Dos titulares concatenados

**Input (de Gemini):**
```json
{
  "titular": {
    "nombre": "NORMA CELIS y GABRIEL VIZCARRA",
    "tipo": "persona"
  }
}
```

**Output (post-processing):**
```json
{
  "titulares": [
    {"nombre": "NORMA CELIS", "tipo": "persona", "actua_por": "derecho propio"},
    {"nombre": "GABRIEL VIZCARRA", "tipo": "persona", "actua_por": "derecho propio"}
  ]
}
```

**Log:**
```
🔧 Separados 2 titulars concatenados
```

---

### ✅ Test 2: Representantes concatenados

**Input (de Gemini):**
```json
{
  "titular": {
    "nombre": "EMPRESA S.A.",
    "tipo": "empresa",
    "representante": {
      "nombre": "ROSA GUZMAN Y MARGARITA FLORES",
      "en_calidad": "apoderadas legales"
    }
  }
}
```

**Output (post-processing):**
```json
{
  "titular": {
    "nombre": "EMPRESA S.A.",
    "tipo": "empresa",
    "representantes": [
      {"nombre": "ROSA GUZMAN", "en_calidad": "apoderada legal"},
      {"nombre": "MARGARITA FLORES", "en_calidad": "apoderada legal"}
    ]
  }
}
```

**Log:**
```
🔧 Separados 2 representantes concatenados
```

---

### ✅ Test 3: Ambos niveles concatenados (CASO COMPLEJO)

**Input (de Gemini):**
```json
{
  "titular": {
    "nombre": "EMPRESA A y EMPRESA B",
    "tipo": "empresa",
    "representante": {
      "nombre": "JUAN LOPEZ Y MARIA GARCIA",
      "en_calidad": "apoderados legales"
    }
  }
}
```

**Output (post-processing):**
```json
{
  "titulares": [
    {
      "nombre": "EMPRESA A",
      "tipo": "empresa",
      "representantes": [
        {"nombre": "JUAN LOPEZ", "en_calidad": "apoderado legal"},
        {"nombre": "MARIA GARCIA", "en_calidad": "apoderado legal"}
      ]
    },
    {
      "nombre": "EMPRESA B",
      "tipo": "empresa",
      "representantes": [
        {"nombre": "JUAN LOPEZ", "en_calidad": "apoderado legal"},
        {"nombre": "MARIA GARCIA", "en_calidad": "apoderado legal"}
      ]
    }
  ]
}
```

**Logs:**
```
🔧 Separados 2 titulars concatenados
🔧 Separados 2 representantes concatenados
```

**Nota:** Los representantes se copian a **ambos titulares** (asumiendo que representan a ambas empresas).

---

## 🔀 Merge con DeepSeek

El merge se actualizó para manejar tanto el formato singular como plural:

```python
# Gemini puede retornar "titular" O "titulares"
gemini_titulares_list = []
if "titulares" in gemini_data:
    gemini_titulares_list = gemini_data["titulares"]  # Múltiples (post-processing)
elif "titular" in gemini_data:
    gemini_titulares_list = [gemini_data["titular"]]  # Singular (original)

# Mergear cada titular
for i, gemini_titular in enumerate(gemini_titulares_list):
    # Actualizar titular[i] en DeepSeek
    # O agregar nuevo si no existe
```

**Logs esperados:**
```
🔧 Gemini retornó 2 titulares separados
✅ Titular[0].nombre ← Gemini
✅ Titular[1].nombre ← Gemini
```

---

## 📝 Logs completos esperados

### Caso con 2 titulares concatenados:

```
🔮 Paso 6.6: Extracción Gemini (expandido: titular/adquiriente/municipio/monto)...

🔮 Extrayendo campos con Gemini (nivel: expandido)...
   🔧 Separados 2 titulars concatenados
   ✅ Titular (vendedor): NORMA ANGELICA CELIS BERMUDEZ...

🔀 Mergeando DeepSeek + Gemini...
   🔧 Gemini retornó 2 titulares separados
   ✅ Titular[0].nombre ← Gemini
   ✅ Titular[0].tipo ← Gemini (persona)
   ✅ Titular[0].representante ← Gemini (null)
   ✅ Titular[1].nombre ← Gemini
   ✅ Titular[1].tipo ← Gemini (persona)
   ✅ Titular[1].representante ← Gemini (null)
   ✅ Municipio ← Gemini
   ✅ Monto ← Gemini
```

---

## 🧪 Probar el fix

### Ejecutar servidor:

```bash
cd "C:\Users\Usuari\OneDrive\Desktop\GisNet Proyectos\Extract_information_PDF"
uvicorn app.api:app --host 0.0.0.0 --port 8000 --reload
```

### Verificar en el JSON de salida:

```json
{
  "titulares": [
    {
      "nombre": "NORMA ANGELICA CELIS BERMUDEZ",
      "tipo": "persona",
      "actua_por": "derecho propio",
      "representante": null
    },
    {
      "nombre": "GABRIEL VIZCARRA SALAZAR",
      "tipo": "persona",
      "actua_por": "derecho propio",
      "representante": null
    }
  ]
}
```

**Criterios de éxito:**
- ✅ Los titulares aparecen como **array de 2 objetos**
- ✅ Cada titular tiene su **nombre individual**
- ✅ El log muestra "🔧 Separados 2 titulars concatenados"

---

## 🎯 Ventajas de esta solución

1. ✅ **Automático** - No requiere cambios manuales
2. ✅ **Robusto** - Funciona incluso si Gemini ignora el prompt
3. ✅ **Sin costo adicional** - Se ejecuta localmente
4. ✅ **Multinivel** - Separa concatenaciones en ambos niveles
5. ✅ **Compatibilidad** - Soporta tanto formato singular como plural
6. ✅ **Preserva datos** - Los representantes se copian a todas las entidades

---

## 📁 Archivos modificados

### `app/extractor.py`

**Líneas 890-1030:** Función `_separar_representantes_concatenados()` (ACTUALIZADA)
- Agregado soporte para separar titulares/adquirientes concatenados
- Mantiene soporte para representantes concatenados
- Retorna listas en lugar de objetos únicos
- Convierte "titular" → "titulares" cuando hay múltiples

**Líneas 1187-1265:** Merge de titulares (ACTUALIZADO)
- Maneja tanto "titular" (singular) como "titulares" (plural)
- Itera sobre todos los titulares de Gemini
- Agrega nuevos titulares si Gemini encontró más que DeepSeek

**Líneas 1266-1350:** Merge de adquirientes (ACTUALIZADO)
- Mismo comportamiento que titulares
- Soporte para múltiples adquirientes

---

## ✅ Estado actual

- ✅ Post-processing implementado para ambos niveles
- ✅ Merge actualizado para formato plural
- ✅ Documentación completa
- ⏳ **Pendiente:** Probar con documento real

---

## 🔄 Próximos pasos

1. **Reiniciar servidor** con los cambios
2. **Procesar documento** con múltiples titulares
3. **Verificar JSON** de salida
4. **Validar logs** para confirmar separación automática

---

## 📚 Referencias

- `CAMBIOS_GEMINI_V2.md` - Changelog completo de v2
- `GEMINI_HYBRID.md` - Arquitectura híbrida
- `FIX_REPRESENTANTES_CONCATENADOS.md` - Documentación original (solo representantes)
