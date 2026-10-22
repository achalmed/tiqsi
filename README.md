# Tiqsi — el contrato para armar una plataforma con módulos independientes

Tiqsi («cimiento» en quechua) es la pieza común con la que proyectos independientes se conectan a un anfitrión: cada
módulo declara un **manifiesto** (sus rutas, lo que ofrece, lo que necesita y lo que aprovecha, sus eventos y sus
referencias) y el anfitrión los monta en orden, sin que un módulo importe el código de otro. Trae el bus de eventos, la
bandeja de salida durable, las referencias entre módulos, un **anfitrión mínimo** (con inicio de sesión) para que cada
módulo funcione solo, su contraparte web (`web/`, `@qillqa/tiqsi`) y el exportador de demos públicas que usan todos.

Es la base de [Qillqa](https://github.com/achalmed/qillqa) y sus módulos (Qillqasqa, la Mediateca, Tareas y Agenda, el
chat, la Mesa de Partes…), cada uno en su repositorio.

```bash
python3 -m venv .venv && .venv/bin/pip install -e '.[pruebas]'
.venv/bin/python -m pytest -q tests
```

Esta es una **versión de demostración**. Licencia: Apache-2.0 (`LICENSE`).
