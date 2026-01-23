# 🔄 ACTUALIZAR LIBRERÍA DE GEMINI

## ⚠️ Problema detectado

El servidor muestra esta advertencia:
```
FutureWarning: All support for the `google.generativeai` package has ended.
Please switch to the `google.genai` package as soon as possible.
```

## ✅ Solución implementada

Ya actualicé el código para usar la nueva librería `google-genai`. Solo falta instalarla.

---

## 📦 Pasos para actualizar

### 1. Desinstalar librería antigua
```bash
pip uninstall google-generativeai -y
```

### 2. Instalar librería nueva
```bash
pip install google-genai
```

### 3. Reiniciar el servidor
```bash
# Detener servidor (Ctrl+C)
# Volver a iniciar
uvicorn app.api:app --host 0.0.0.0 --port 8000 --reload
```

---

## 🎯 Cambios realizados en el código

### `requirements.txt` (línea 56)
```diff
- google-generativeai>=0.8.0
+ google-genai>=0.2.0
```

### `services/gemini_service.py` (línea 36)
```diff
- import google.generativeai as genai
+ from google import genai
```

### `services/gemini_service.py` (línea 56-58)
```diff
- genai.configure(api_key=self.api_key)
- self.model = genai.GenerativeModel('gemini-2.0-flash-exp')
+ self.client = genai.Client(api_key=self.api_key)
+ self.model_name = 'gemini-2.0-flash-exp'
```

### `services/gemini_service.py` (línea 93-100)
```diff
- response = self.model.generate_content(
-     prompt,
-     generation_config={...}
- )
+ response = self.client.models.generate_content(
+     model=self.model_name,
+     contents=prompt,
+     config={...}
+ )
```

---

## 🔧 Configurar modelo de Gemini

### ¿Dónde cambiar el modelo?

**Archivo:** `services/gemini_service.py:58`

```python
self.model_name = 'gemini-2.0-flash-exp'  # ← Cambiar aquí
```

### Modelos disponibles:

```python
# Rápidos y económicos
'gemini-2.0-flash-exp'    # ← Actual (experimental)
'gemini-2.0-flash'        # Versión estable
'gemini-2.5-flash'        # Más reciente

# Mayor capacidad
'gemini-pro'              # Modelo anterior
'gemini-1.5-pro'          # Mayor contexto (1M tokens)
```

**Recomendación:** Usa `gemini-2.5-flash` para mejor precisión/costo.

### Ejemplo de cambio:

```python
# En services/gemini_service.py línea 58
self.model_name = 'gemini-2.5-flash'  # ← Cambiar a versión más reciente
```

---

## 📊 Comparación de modelos

| Modelo | Velocidad | Costo | Precisión | Contexto |
|--------|-----------|-------|-----------|----------|
| `gemini-2.0-flash-exp` | ⚡⚡⚡ | 💰 | ⭐⭐⭐ | 1M tokens |
| `gemini-2.5-flash` | ⚡⚡ | 💰💰 | ⭐⭐⭐⭐ | 1M tokens |
| `gemini-1.5-pro` | ⚡ | 💰💰💰 | ⭐⭐⭐⭐⭐ | 2M tokens |

**Para escrituras públicas:** `gemini-2.5-flash` es el mejor balance.

---

## ✅ Verificar que funciona

Después de actualizar, el servidor debe iniciar sin warnings:

```bash
INFO:     Started server process [12345]
INFO:     Waiting for application startup.
🚀 Iniciando API de Extracción...
✅ Extractor inicializado
INFO:     Application startup complete.
```

**No debe aparecer:** `FutureWarning` sobre `google.generativeai`

---

## 🐛 Troubleshooting

### Error: "No module named 'google.genai'"
```bash
# Asegúrate de instalar la nueva librería
pip install google-genai
```

### Error: "Client object has no attribute 'models'"
```bash
# Verifica que instalaste la versión correcta
pip show google-genai
# Debe ser >= 0.2.0
```

### Error: "Invalid model name"
```bash
# Verifica que el modelo existe
# Modelos válidos: gemini-2.0-flash-exp, gemini-2.5-flash, gemini-1.5-pro
```

---

## 📝 Notas

- La nueva API es más moderna y mantenida por Google
- Compatible con los mismos modelos que la API anterior
- Sintaxis ligeramente diferente pero más consistente
- El código ya está adaptado, solo falta instalar la librería
