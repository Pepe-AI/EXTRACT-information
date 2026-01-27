# FIX: Gemini retorna adquirientes como array (separados)

## Problema identificado

**Sintoma:**
- DeepSeek separa correctamente 2 adquirientes (Antonio y Silvia)
- Gemini los concatena en 1 solo objeto: "ANTONIO QUINTERO FLORES y SILVIA SÁNCHEZ SÁNCHEZ"
- El merge solo itera 1 vez (para el unico objeto de Gemini)
- Solo el primer adquiriente de DeepSeek recibe RFC/CURP/edad
- El segundo adquiriente queda con `"rfc": false, "curp": false`

**Root cause:**
El prompt de Gemini especificaba:
```json
"adquiriente": {
  "nombre": "NOMBRE COMPRADOR",
  ...
}
```

Esto causaba que Gemini retornara un objeto singular en lugar de un array.

---

## Cambios implementados

### 1. Modificar prompt de Gemini (utils/gemini_prompts.py)

**Archivo:** `utils/gemini_prompts.py`
**Función:** `build_gemini_prompt_expandido()`

#### Cambio 1: Agregar regla de múltiples adquirientes

**Linea ~238-254** - Agregada nueva regla:

```python
⚠️ REGLA MÚLTIPLES ADQUIRIENTES:
- Si detectas MÚLTIPLES ADQUIRIENTES (ejemplo: "ANTONIO QUINTERO FLORES y SILVIA SÁNCHEZ SÁNCHEZ")
- NO los concatenes en un solo objeto
- Crea un objeto SEPARADO para cada adquiriente en el array "adquirientes"
- Extrae el RFC, CURP y edad de CADA PERSONA por separado
- Busca en la sección "FE NOTARIAL" o "COMPARECIENTES" donde se listan los RFC/CURP de cada persona
- Asigna el RFC/CURP correcto a cada persona (busca el RFC/CURP cerca del nombre de cada persona)
```

#### Cambio 2: Cambiar plantilla JSON de singular a array

**Linea ~294-325** - Template actualizado:

**ANTES:**
```json
{
  "titular": {...},
  "adquiriente": {
    "nombre": "NOMBRE COMPRADOR",
    ...
  },
  ...
}
```

**DESPUES:**
```json
{
  "titular": {...},
  "adquirientes": [
    {
      "nombre": "NOMBRE COMPRADOR 1",
      "tipo": "empresa" o "persona",
      "estado_civil": "..." o false,
      "rfc": "..." o false,
      "curp": "..." o false,
      "edad": X o false,
      ...
    }
  ],
  ...
}
```

#### Cambio 3: Actualizar reglas

**Linea ~327-337** - Reglas actualizadas:

```python
- ADQUIRIENTES: SIEMPRE retorna como ARRAY (incluso si es solo 1 persona)
- Si hay MÚLTIPLES ADQUIRIENTES (ejemplo: "ANTONIO y SILVIA") → crea un objeto separado para CADA UNO
- Extrae rfc, curp, edad, estado_civil, tipo_sociedad de CADA adquiriente SOLO SI APARECEN (sino usa false)
```

---

## Verificación

### Test creado

**Archivo:** `test_gemini_adquirientes_array.py`

**Uso:**
```bash
python test_gemini_adquirientes_array.py
```

**Verifica:**
1. Gemini retorna `"adquirientes"` como array (no singular)
2. Hay 2 objetos en el array (Antonio y Silvia)
3. Los nombres están separados (no concatenados con "y")
4. Cada adquiriente tiene su propio RFC/CURP/edad
5. Antonio: RFC=QUFA670718TK2, CURP=QUFA670718HJCNLN04
6. Silvia: RFC=SASS680104FB7, CURP=SASS680104MJCNNL03

---

## Resultado esperado

**Antes del fix (Gemini):**
```json
{
  "adquiriente": {
    "nombre": "ANTONIO QUINTERO FLORES y SILVIA SÁNCHEZ SÁNCHEZ",
    "rfc": "QUFA670718TK2",
    "curp": "QUFA670718HJCNLN04",
    "edad": 56
  }
}
```

**Después del fix (Gemini):**
```json
{
  "adquirientes": [
    {
      "nombre": "ANTONIO QUINTERO FLORES",
      "rfc": "QUFA670718TK2",
      "curp": "QUFA670718HJCNLN04",
      "edad": 56,
      "estado_civil": "casado bajo el régimen de sociedad legal"
    },
    {
      "nombre": "SILVIA SÁNCHEZ SÁNCHEZ",
      "rfc": "SASS680104FB7",
      "curp": "SASS680104MJCNNL03",
      "edad": 55,
      "estado_civil": "casada bajo el régimen de sociedad legal"
    }
  ]
}
```

**Merge final (DeepSeek + Gemini):**
```json
{
  "adquirientes": [
    {
      "nombre": "ANTONIO QUINTERO FLORES",
      "tipo": "persona",
      "rfc": "QUFA670718TK2",       // <- Gemini
      "curp": "QUFA670718HJCNLN04",  // <- Gemini
      "edad": 56,                     // <- Gemini
      "estado_civil": "casado..."     // <- Gemini
    },
    {
      "nombre": "SILVIA SÁNCHEZ SÁNCHEZ",
      "tipo": "persona",
      "rfc": "SASS680104FB7",         // <- Gemini
      "curp": "SASS680104MJCNNL03",   // <- Gemini
      "edad": 55,                      // <- Gemini
      "estado_civil": "casada..."      // <- Gemini
    }
  ]
}
```

---

## Pasos siguientes

1. **Ejecutar test para verificar que Gemini ahora retorna array:**
   ```bash
   python test_gemini_adquirientes_array.py
   ```

2. **Si el test pasa, reiniciar el servidor uvicorn:**
   ```bash
   # Ctrl+C para detener
   uvicorn main:app --reload
   ```

3. **Procesar el documento desde la interfaz web**

4. **Verificar que ambos adquirientes tienen RFC/CURP/edad**

---

## Archivos modificados

1. `utils/gemini_prompts.py` - Prompt expandido ahora usa "adquirientes" array

## Archivos creados

1. `test_gemini_adquirientes_array.py` - Test de verificación de array
2. `FIX_ADQUIRIENTES_ARRAY.md` - Esta documentación

---

## Notas

- El merge logic en `extractor.py` ya soporta arrays (lineas 1218-1291)
- El merge logic ya maneja el caso donde Gemini tiene MÁS adquirientes que DeepSeek
- El fix NO requiere cambios en el merge logic, solo en el prompt de Gemini
