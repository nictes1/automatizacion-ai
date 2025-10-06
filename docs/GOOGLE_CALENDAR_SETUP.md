# 📅 Configuración de Google Calendar

Esta guía explica cómo configurar Google Calendar OAuth2 para agendamiento de turnos.

## 🎯 Objetivo

Permitir que PulpoAI acceda al Google Calendar del negocio para:
- Verificar disponibilidad de horarios
- Crear eventos (turnos) automáticamente
- Enviar invitaciones a empleados y clientes
- Sincronizar calendarios

---

## 📋 Prerequisitos

1. Una cuenta de Gmail para desarrollo (ej: `peluqueriaReina@gmail.com`)
2. Acceso a [Google Cloud Console](https://console.cloud.google.com/)

---

## 🔧 Paso 1: Crear Proyecto en Google Cloud

1. Ir a [Google Cloud Console](https://console.cloud.google.com/)
2. Crear nuevo proyecto:
   - Nombre: `PulpoAI Calendar`
   - ID: `pulpoai-calendar` (o el que prefieras)
3. Seleccionar el proyecto creado

---

## 📚 Paso 2: Habilitar Google Calendar API

1. En el menú lateral → **APIs & Services** → **Library**
2. Buscar "Google Calendar API"
3. Click en "Enable"

---

## 🔑 Paso 3: Crear Credenciales OAuth 2.0

### 3.1 Configurar Consent Screen

1. **APIs & Services** → **OAuth consent screen**
2. Seleccionar **External** (para testing)
3. Completar formulario:
   - **App name**: PulpoAI
   - **User support email**: tu email
   - **Developer contact**: tu email
4. **Scopes**: Agregar scopes
   - `https://www.googleapis.com/auth/calendar`
   - `https://www.googleapis.com/auth/calendar.events`
5. **Test users**: Agregar tu email de desarrollo
6. Guardar

### 3.2 Crear OAuth Client ID

1. **APIs & Services** → **Credentials** → **Create Credentials**
2. Seleccionar **OAuth client ID**
3. Application type: **Web application**
4. Name: `PulpoAI Web Client`
5. **Authorized redirect URIs**: Agregar
   ```
   http://localhost:3000/settings/calendar/callback
   http://localhost:8005/config/calendar/callback
   ```
6. Click **Create**
7. **IMPORTANTE**: Copiar:
   - Client ID
   - Client Secret

---

## ⚙️ Paso 4: Configurar Variables de Entorno

Agregar al `.env` o `docker-compose.yml`:

```bash
GOOGLE_CLIENT_ID=tu-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=tu-client-secret
```

---

## 🔄 Paso 5: Flujo de Autorización (desde la UI o curl)

### Opción A: Desde la UI (Próximamente)

1. En PulpoAI → Settings → Calendar
2. Click en "Conectar Google Calendar"
3. Autorizar acceso
4. Listo!

### Opción B: Con curl (Para desarrollo)

```bash
WORKSPACE_ID="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"

# 1. Obtener URL de autorización
AUTH_URL=$(curl -s -X GET "http://localhost:8005/config/calendar/auth-url?redirect_uri=http://localhost:8005/callback" \
  -H "X-Workspace-Id: $WORKSPACE_ID" | jq -r '.authorization_url')

echo "Abrir en el navegador:"
echo "$AUTH_URL"

# 2. Después de autorizar, Google te redirige a:
# http://localhost:8005/callback?code=CODIGO_AQUI&state=...

# 3. Copiar el código y ejecutar:
AUTHORIZATION_CODE="CODIGO_AQUI"

curl -X POST "http://localhost:8005/config/calendar/connect" \
  -H "Content-Type: application/json" \
  -H "X-Workspace-Id: $WORKSPACE_ID" \
  -d "{
    \"authorization_code\": \"$AUTHORIZATION_CODE\",
    \"redirect_uri\": \"http://localhost:8005/callback\"
  }"
```

---

## ✅ Verificación

```bash
# Verificar configuración
curl -X GET "http://localhost:8005/config/calendar" \
  -H "X-Workspace-Id: aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"

# Respuesta esperada:
{
  "calendar_email": "peluqueriaReina@gmail.com",
  "is_configured": true,
  "calendar_settings": {...}
}
```

---

## 🧪 Probar Agendamiento

```bash
# Crear un turno de prueba
curl -X POST "http://localhost:8006/actions/create-appointment" \
  -H "Content-Type: application/json" \
  -H "X-Workspace-Id: aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa" \
  -d '{
    "service_type_name": "Corte de pelo",
    "client_name": "Juan Test",
    "client_email": "tu-email-de-prueba@gmail.com",
    "appointment_date": "2025-10-06",
    "appointment_time": "14:00"
  }'

# Verificar en:
# - Base de datos: tabla pulpo.appointments
# - Google Calendar: peluqueriaReina@gmail.com
# - Email: invitación enviada a tu-email-de-prueba@gmail.com
```

---

## 🔒 Seguridad

- **Nunca commitear** `GOOGLE_CLIENT_SECRET` al repo
- Usar variables de entorno
- En producción: rotar tokens periódicamente
- Limitar scopes al mínimo necesario

---

## 🐛 Troubleshooting

### Error: "redirect_uri_mismatch"
- Verificar que el redirect_uri en el código coincida EXACTAMENTE con el configurado en Google Cloud Console

### Error: "invalid_grant"
- El authorization_code expiró (válido por 10 minutos)
- Generar nuevo código

### No recibo invitaciones
- Verificar que `business_calendar_email` esté configurado
- Verificar tokens en `workspaces.settings.google_calendar_tokens`
- Revisar logs del servicio

---

## 📚 Referencias

- [Google Calendar API](https://developers.google.com/calendar/api/guides/overview)
- [OAuth 2.0](https://developers.google.com/identity/protocols/oauth2)
