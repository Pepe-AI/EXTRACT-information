# Análisis de Extracción de Datos - Escritura 2307

## 📊 Comparación JSON Generado vs Esperado

### ✅ CAMPOS CORRECTOS

| Campo | Generado | Esperado | Estado |
|-------|----------|----------|--------|
| `numero_escritura` | `2307` | `2307` | ✅ CORRECTO |
| `numero_notaria` | `35` | `35` | ✅ CORRECTO |
| `nombre_notario` | `"RIGOBERTO OCHOA TORRES"` | `"RIGOBERTO OCHOA TORRES"` (como `notario`) | ✅ CORRECTO (diferente key) |
| `tipo_titular` | `"empresa"` | `"empresa"` | ✅ CORRECTO |
| `titulares[0].nombre` | `"INSTITUTO NACIONAL DEL SUELO SUSTENTABLE (INSUS)"` | `"INSTITUTO NACIONAL DEL SUELO SUSTENTABLE (INSUS)"` | ✅ CORRECTO |
| `adquirientes[0].rfc` | `false` | `false` | ✅ CORRECTO |
| `adquirientes[0].curp` | `false` | `false` | ✅ CORRECTO |

---

### ⚠️ CAMPOS INCORRECTOS

| Campo | Generado | Esperado | Problema |
|-------|----------|----------|----------|
| **MUNICIPIO** | `"Tepic"` | `"TEPIC"` | ❌ Formato: debe estar en MAYÚSCULAS |
| **FECHA_DOCUMENTO** | `"Cinco de mayo de 2023"` | `"5 DE MAYO DE 2023"` | ❌ Formato: debe ser numérico y MAYÚSCULAS |
| **MONTO_OPERACION** | `"$8,654.00"` | `""` (vacío) | ⚠️ Extrae valor incorrecto (debería buscar otro monto) |
| **ADQUIRIENTE - NOMBRE** | `"ANGELBERTA PÉREZ SOTO"` | `"ANGELBERTHA PEREZ SOTO"` | ⚠️ Diferencia ortográfica (con/sin tilde) |
| **ADQUIRIENTE - ESTADO_CIVIL** | `null` | `"CASADA"` | ❌ NO EXTRAE (está en el OCR) |
| **ADQUIRIENTE - ACTUA_POR** | `"representación de su Gestora de Negocios"` | `"GESTOR OFICIOSO"` | ❌ Formato incorrecto, muy descriptivo |
| **ADQUIRIENTE - TIPO_SOCIEDAD** | `null` | `"NO CONSTA"` | ❌ NO EXTRAE |
| **ADQUIRIENTE - REPRESENTANTE** | `null` | Objeto completo | ❌ NO EXTRAE (existe en el OCR) |
| **TITULAR - ACTUA_POR** | `"representación legal"` | `"APODERADO"` | ❌ Formato incorrecto |
| **TITULAR - REPRESENTANTE.NOMBRE** | `"Arquitecto ERNESTO PADILLA ACEVES"` | `"ERNESTO PADILLA ACEVES"` | ⚠️ Incluye título profesional |
| **TITULAR - REPRESENTANTE.EN_CALIDAD** | `"Representante Regional de..."` | `"REPRESENTANTE LEGAL"` | ❌ Muy específico, debería ser genérico |
| **TITULAR - REPRESENTANTE.ESCRITURA** | `"INSUS"` | `"63"` | ❌ INCORRECTO - no extrae número de escritura |
| **TITULAR - REPRESENTANTE.FECHA_PODER** | `""` (vacío) | `"4/15/2020"` | ❌ NO EXTRAE (está en el OCR: "15 de abril del año 2020") |
| **TITULAR - TIPO** | `"persona"` | NO EXISTE | ⚠️ Campo extra innecesario |
| **ADQUIRIENTE - TIPO** | `"persona"` | NO EXISTE | ⚠️ Campo extra innecesario |

---

### ❌ CAMPOS FALTANTES EN EL GENERADO

| Campo Esperado | Estado en Generado |
|----------------|-------------------|
| `tipo_moneda` | ❌ NO EXISTE (debería ser `""` o `null`) |
| `valor_catastral` | ✅ EXISTE pero no en ejemplo generado |

---

### 📝 CAMPOS EXTRA (que están en generado pero no en esperado)

| Campo | Razón |
|-------|-------|
| `curps` (array raíz) | ❌ Innecesario si ya está en personas |
| `titulares[].tipo` | ❌ Redundante con `tipo_titular` |
| `adquirientes[].tipo` | ❌ Innecesario |

---

## 🔍 DATOS DISPONIBLES EN EL OCR QUE NO SE EXTRAEN

### 1. **ADQUIRIENTE - Estado Civil: "CASADA"**
```
casada, empleada doméstica, originaria de la localidad El Trapiche
```

### 2. **ADQUIRIENTE - Representante**
```
MA. GUADALUPE HILDA BERNAL CHAVARIN conocida tambien como
MARIA GUADALUPE HILDA BERNAL CHAVARIN, en su calidad de
gestora de negocios
```

### 3. **TITULAR - Representante - Número de Escritura: "63,550"**
```
exhibe instrumento 63,550 sesenta y tres mil quinientos cincuenta,
de fecha 15 quince del mes de abril del año 2020 dos mil veinte
```

### 4. **TITULAR - Representante - Fecha de Poder: "15/04/2020"**
```
de fecha 15 quince del mes de abril del año 2020 dos mil veinte
```

---

## 📊 RESUMEN DE CALIDAD

### Categorías:
- ✅ **Correctos**: 7 campos (30%)
- ⚠️ **Parcialmente Correctos**: 4 campos (17%)
- ❌ **Incorrectos**: 9 campos (39%)
- ❌ **Faltantes**: 3 campos (13%)

### Calidad General: **~47% de precisión**

---

## 🎯 PRIORIDADES DE CORRECCIÓN

### 🔴 CRÍTICO (Datos disponibles que no se extraen):
1. **Adquiriente - Estado Civil**: "CASADA" → Regex para estado civil
2. **Adquiriente - Representante completo** → LLM no lo detecta
3. **Titular - Representante.escritura**: "63,550" → Regex para número de instrumento
4. **Titular - Representante.fecha_poder**: "15/04/2020" → Regex para fechas

### 🟡 IMPORTANTE (Formato incorrecto):
5. **Fecha**: "Cinco de mayo de 2023" → "5 DE MAYO DE 2023"
6. **Municipio**: "Tepic" → "TEPIC"
7. **actua_por**: Estandarizar valores (APODERADO, GESTOR OFICIOSO, etc.)
8. **Limpiar títulos profesionales** de nombres

### 🟢 MENOR (Campos extra):
9. Eliminar campo `tipo` de titulares/adquirientes
10. Agregar campo `tipo_moneda`
11. Verificar estructura de `monto_operacion`

---

## 🔧 SIGUIENTE PASO RECOMENDADO

**¿Por dónde empezar?**
1. ¿Corregir formatos (fechas, mayúsculas)?
2. ¿Extraer campos faltantes (estado civil, representante del adquiriente)?
3. ¿Mejorar extracción de datos del poder (escritura, fecha)?
4. ¿Estandarizar valores de `actua_por`?
