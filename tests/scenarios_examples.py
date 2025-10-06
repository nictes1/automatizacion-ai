"""
Ejemplos de escenarios personalizados para tests con Cliente AI

Copia estos ejemplos y agrégalos a SCENARIOS en test_ai_client_scenarios.py
"""

from datetime import datetime, timedelta
from test_ai_client_scenarios import TestScenario, ClientProfile, PersonalityType

# =========================
# SERVICIOS - Peluquería/Spa
# =========================

# Ejemplo: Cliente que quiere cambiar la fecha
ejemplo_cambio_fecha = TestScenario(
    id="servicios_cambio_fecha",
    name="Cliente que Cambia Fecha",
    description="Cliente que primero pide una fecha, luego cambia de opinión",
    vertical="servicios",
    client=ClientProfile(
        name="Patricia Ruiz",
        email="patricia.ruiz@gmail.com",
        phone="+5491145678901",
        personality=PersonalityType.CONVERSATIONAL,
        style_notes="Decide cambiar la fecha después de proponerla inicialmente"
    ),
    objective="Agendar manicura pero cambiar fecha",
    context={
        "service": "Manicura",
        "preferred_date": (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d"),
        "preferred_time": "14:00",
        "when_human": "el miércoles a las 2pm"  # Va a cambiar a jueves
    },
    expected_slots=["service_type", "preferred_date", "preferred_time", "client_name", "client_email"]
)

# Ejemplo: Cliente que pide múltiples servicios
ejemplo_multiples_servicios = TestScenario(
    id="servicios_multiples",
    name="Cliente con Múltiples Servicios",
    description="Cliente que quiere agendar más de un servicio",
    vertical="servicios",
    client=ClientProfile(
        name="Valentina Díaz",
        email="vale.diaz@hotmail.com",
        phone="+5491134567890",
        personality=PersonalityType.EFFICIENT,
        style_notes="Pide corte + coloración juntos"
    ),
    objective="Agendar corte y coloración",
    context={
        "service": "Corte y Coloración",
        "preferred_date": (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d"),
        "preferred_time": "10:00",
        "when_human": "pasado mañana a las 10"
    },
    expected_slots=["service_type", "preferred_date", "preferred_time", "client_name", "client_email"]
)

# Ejemplo: Cliente que pregunta antes de agendar
ejemplo_consulta_previa = TestScenario(
    id="servicios_consulta",
    name="Cliente que Consulta Primero",
    description="Cliente que hace preguntas sobre el servicio antes de agendar",
    vertical="servicios",
    client=ClientProfile(
        name="Martín Torres",
        email="martin.torres@yahoo.com",
        phone="+5491198765432",
        personality=PersonalityType.CONVERSATIONAL,
        style_notes="Pregunta duración y precio antes de decidir"
    ),
    objective="Consultar sobre barbería antes de agendar",
    context={
        "service": "Corte y Barba",
        "preferred_date": (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d"),
        "preferred_time": "16:00",
        "when_human": "mañana a las 4pm"
    },
    expected_slots=["service_type", "preferred_date", "preferred_time", "client_name", "client_email"]
)

# =========================
# GASTRONOMÍA - Restaurante
# =========================

# Ejemplo: Reserva para ocasión especial
ejemplo_ocasion_especial = TestScenario(
    id="gastronomia_cumpleaños",
    name="Reserva para Cumpleaños",
    description="Cliente que reserva para cumpleaños, menciona decoración o torta",
    vertical="gastronomia",
    client=ClientProfile(
        name="Lucía Fernández",
        email="lucia.fernandez@gmail.com",
        phone="+5491156781234",
        personality=PersonalityType.CONVERSATIONAL,
        style_notes="Menciona que es cumpleaños, pregunta si pueden preparar algo especial"
    ),
    objective="Reservar mesa para cumpleaños",
    context={
        "service": "Reserva de Mesa",
        "party_size": 8,
        "preferred_date": (datetime.now() + timedelta(days=5)).strftime("%Y-%m-%d"),
        "preferred_time": "21:00",
        "when_human": "el viernes a las 9 de la noche"
    },
    expected_slots=["party_size", "preferred_date", "preferred_time", "client_name", "client_phone"]
)

# Ejemplo: Cliente con restricciones alimentarias
ejemplo_restricciones = TestScenario(
    id="gastronomia_vegano",
    name="Cliente con Restricción Alimentaria",
    description="Cliente que pregunta por opciones veganas/celíacas",
    vertical="gastronomia",
    client=ClientProfile(
        name="Daniela Moreno",
        email="dani.moreno@outlook.com",
        phone="+5491187654321",
        personality=PersonalityType.CONVERSATIONAL,
        style_notes="Pregunta por opciones veganas antes de confirmar"
    ),
    objective="Reservar consultando opciones veganas",
    context={
        "service": "Reserva de Mesa",
        "party_size": 2,
        "preferred_date": (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d"),
        "preferred_time": "20:30",
        "when_human": "pasado mañana a las 8:30pm"
    },
    expected_slots=["party_size", "preferred_date", "preferred_time", "client_name", "client_phone"]
)

# Ejemplo: Reserva de último momento
ejemplo_urgente = TestScenario(
    id="gastronomia_urgente",
    name="Reserva Urgente (Hoy)",
    description="Cliente que quiere reservar para el mismo día",
    vertical="gastronomia",
    client=ClientProfile(
        name="Federico Ramos",
        email="fede.ramos@gmail.com",
        phone="+5491145678901",
        personality=PersonalityType.BRIEF,
        style_notes="Urgente, respuestas cortas, quiere para hoy"
    ),
    objective="Reservar mesa para hoy",
    context={
        "service": "Reserva de Mesa",
        "party_size": 4,
        "preferred_date": datetime.now().strftime("%Y-%m-%d"),
        "preferred_time": "13:00",
        "when_human": "hoy al mediodía"
    },
    expected_slots=["party_size", "preferred_date", "preferred_time", "client_name", "client_phone"]
)

# =========================
# INMOBILIARIA
# =========================

# Ejemplo: Cliente con presupuesto específico
ejemplo_presupuesto = TestScenario(
    id="inmobiliaria_presupuesto",
    name="Cliente con Presupuesto Límite",
    description="Cliente que menciona rango de precio antes de visitar",
    vertical="inmobiliaria",
    client=ClientProfile(
        name="Andrés Castro",
        email="andres.castro@gmail.com",
        phone="+5491134567890",
        personality=PersonalityType.CONVERSATIONAL,
        style_notes="Menciona presupuesto máximo, pregunta si hay opciones en ese rango"
    ),
    objective="Visitar depto consultando precio",
    context={
        "service": "Visita a Propiedad",
        "property_type": "Departamento 2 ambientes",
        "location": "Villa Crespo",
        "preferred_date": (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d"),
        "preferred_time": "18:00",
        "when_human": "el miércoles a las 6pm"
    },
    expected_slots=["property_type", "preferred_date", "preferred_time", "client_name", "client_email"]
)

# Ejemplo: Cliente que compara propiedades
ejemplo_comparacion = TestScenario(
    id="inmobiliaria_comparacion",
    name="Cliente Comparando Propiedades",
    description="Cliente que pregunta por varias propiedades antes de decidir visita",
    vertical="inmobiliaria",
    client=ClientProfile(
        name="Carolina Vega",
        email="caro.vega@hotmail.com",
        phone="+5491198765432",
        personality=PersonalityType.CONVERSATIONAL,
        style_notes="Pregunta por diferencias entre barrios/propiedades"
    ),
    objective="Comparar y agendar visita",
    context={
        "service": "Visita a Propiedad",
        "property_type": "Departamento 3 ambientes",
        "location": "Palermo o Belgrano",  # Dos opciones
        "preferred_date": (datetime.now() + timedelta(days=4)).strftime("%Y-%m-%d"),
        "preferred_time": "11:00",
        "when_human": "el jueves a la mañana"
    },
    expected_slots=["property_type", "preferred_date", "preferred_time", "client_name", "client_email"]
)

# Ejemplo: Cliente que pregunta por financiación
ejemplo_financiacion = TestScenario(
    id="inmobiliaria_financiacion",
    name="Cliente Pregunta Financiación",
    description="Cliente interesado en opciones de financiamiento",
    vertical="inmobiliaria",
    client=ClientProfile(
        name="Rodrigo Sosa",
        email="rodrigo.sosa@yahoo.com",
        phone="+5491156781234",
        personality=PersonalityType.EFFICIENT,
        style_notes="Directo, pregunta por créditos/planes de pago"
    ),
    objective="Visitar propiedad consultando financiación",
    context={
        "service": "Visita a Propiedad",
        "property_type": "Casa 3 dormitorios",
        "location": "Zona Norte",
        "preferred_date": (datetime.now() + timedelta(days=6)).strftime("%Y-%m-%d"),
        "preferred_time": "15:00",
        "when_human": "el sábado a las 3pm"
    },
    expected_slots=["property_type", "preferred_date", "preferred_time", "client_name", "client_email"]
)

# =========================
# CASOS EDGE / ESPECIALES
# =========================

# Ejemplo: Cliente que se equivoca de negocio
ejemplo_equivocado = TestScenario(
    id="servicios_equivocado",
    name="Cliente en Negocio Equivocado",
    description="Cliente que pregunta por algo que no ofrece el negocio",
    vertical="servicios",
    client=ClientProfile(
        name="Gabriela Núñez",
        email="gabi.nunez@gmail.com",
        phone="+5491145678901",
        personality=PersonalityType.CONVERSATIONAL,
        style_notes="Pregunta por servicio no disponible, se da cuenta del error"
    ),
    objective="Intenta agendar servicio no disponible",
    context={
        "service": "Masajes",  # Si peluquería no ofrece masajes
        "preferred_date": (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d"),
        "preferred_time": "14:00",
        "when_human": "mañana a las 2pm"
    },
    expected_slots=["service_type", "preferred_date", "preferred_time", "client_name", "client_email"]
)

# Ejemplo: Cliente con horario fuera de rango
ejemplo_horario_invalido = TestScenario(
    id="servicios_horario_invalido",
    name="Cliente con Horario Fuera de Horario",
    description="Cliente que pide turno muy temprano/tarde",
    vertical="servicios",
    client=ClientProfile(
        name="Pablo Herrera",
        email="pablo.herrera@outlook.com",
        phone="+5491134567890",
        personality=PersonalityType.BRIEF,
        style_notes="Pide horario tipo 7am o 11pm (fuera de horario comercial)"
    ),
    objective="Agendar en horario no disponible",
    context={
        "service": "Corte de Cabello",
        "preferred_date": (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d"),
        "preferred_time": "07:00",  # Muy temprano
        "when_human": "mañana a las 7 de la mañana"
    },
    expected_slots=["service_type", "preferred_date", "preferred_time", "client_name", "client_email"]
)

# Ejemplo: Cliente que cancela
ejemplo_cancelacion = TestScenario(
    id="servicios_cancelacion",
    name="Cliente que Decide Cancelar",
    description="Cliente que empieza a agendar pero luego cancela",
    vertical="servicios",
    client=ClientProfile(
        name="Mónica Giménez",
        email="monica.gimenez@gmail.com",
        phone="+5491198765432",
        personality=PersonalityType.CONVERSATIONAL,
        style_notes="Da info inicial, luego dice que prefiere llamar más tarde o cancelar"
    ),
    objective="Intenta agendar pero cancela",
    context={
        "service": "Coloración",
        "preferred_date": (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d"),
        "preferred_time": "16:00",
        "when_human": "pasado mañana a las 4pm"
    },
    expected_slots=["service_type", "preferred_date", "preferred_time", "client_name", "client_email"]
)

# =========================
# CÓMO USAR ESTOS EJEMPLOS
# =========================

"""
Para agregar estos escenarios a tus tests:

1. Copia el escenario que te interesa

2. Pégalo en test_ai_client_scenarios.py dentro de la lista SCENARIOS:

    SCENARIOS = [
        # ... escenarios existentes ...

        # Agregar aquí
        ejemplo_cambio_fecha,
        ejemplo_multiples_servicios,
        # etc...
    ]

3. Ejecuta los tests:
    python3 tests/test_ai_client_scenarios.py

4. O selecciona solo algunos:
    runner = TestRunner([ejemplo_cambio_fecha, ejemplo_consulta_previa])
    asyncio.run(runner.run_all())
"""

# Ejemplo de customización completa
ejemplo_custom_completo = TestScenario(
    id="mi_escenario_custom",  # ID único
    name="Mi Escenario Personalizado",  # Nombre descriptivo
    description="Descripción detallada de qué testea este escenario",
    vertical="servicios",  # "servicios", "gastronomia", "inmobiliaria"
    client=ClientProfile(
        name="Nombre Cliente",
        email="email@example.com",
        phone="+5491123456789",
        personality=PersonalityType.CONVERSATIONAL,  # EFFICIENT, CONVERSATIONAL, FORGETFUL, CHAOTIC, BRIEF
        style_notes="Notas sobre cómo se comporta este cliente"
    ),
    objective="Lo que quiere lograr el cliente",
    context={
        # Servicios
        "service": "Nombre del Servicio",
        "preferred_date": (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d"),
        "preferred_time": "15:00",
        "when_human": "mañana a las 3pm",

        # Gastronomía (adicional)
        # "party_size": 4,

        # Inmobiliaria (adicional)
        # "property_type": "Departamento 2 ambientes",
        # "location": "Palermo",
    },
    expected_slots=["service_type", "preferred_date", "preferred_time", "client_name", "client_email"],
    max_turns=10  # Máximo de intercambios antes de fallar
)
