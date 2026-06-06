<div align="center">

# SmartEye-TFG

### Plataforma web modular para procesamiento de imágenes mediante pipelines de Inteligencia Artificial

![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-Backend-000000?style=for-the-badge&logo=flask&logoColor=white)
![MariaDB](https://img.shields.io/badge/MariaDB-Database-003545?style=for-the-badge&logo=mariadb&logoColor=white)
![OpenCV](https://img.shields.io/badge/OpenCV-Computer%20Vision-5C3EE8?style=for-the-badge&logo=opencv&logoColor=white)
![YOLO](https://img.shields.io/badge/YOLO-Object%20Detection-00FFFF?style=for-the-badge)
![MediaPipe](https://img.shields.io/badge/MediaPipe-Pose%20%26%20Hands-FF6F00?style=for-the-badge)
![Pytest](https://img.shields.io/badge/Tests-Pytest-0A9EDC?style=for-the-badge&logo=pytest&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Reproducible%20Environment-2496ED?style=for-the-badge&logo=docker&logoColor=white)
![JWT](https://img.shields.io/badge/Auth-JWT-000000?style=for-the-badge&logo=jsonwebtokens&logoColor=white)
![SonarQube](https://img.shields.io/badge/SonarQube-Code%20Quality-4E9BCD?style=for-the-badge&logo=sonarqube&logoColor=white)

![Quality Gate](https://img.shields.io/badge/Quality%20Gate-Passed-brightgreen?style=for-the-badge&logo=sonarqube&logoColor=white)
![Security](https://img.shields.io/badge/Security-A-00C853?style=for-the-badge)
![Reliability](https://img.shields.io/badge/Reliability-A-00C853?style=for-the-badge)
![Maintainability](https://img.shields.io/badge/Maintainability-A-00C853?style=for-the-badge)
![Coverage](https://img.shields.io/badge/Coverage-93.0%25-1BA784?style=for-the-badge)
![Duplications](https://img.shields.io/badge/Duplications-1.4%25-1BA784?style=for-the-badge)
![Hotspots](https://img.shields.io/badge/Hotspots%20Reviewed-100%25-1BA784?style=for-the-badge)
![CI](https://img.shields.io/badge/CI-Integrated-2088FF?style=for-the-badge&logo=githubactions&logoColor=white)

**Aplicación web desarrollada como Trabajo de Fin de Grado para ejecutar flujos de visión artificial sobre imágenes, combinando modelos de IA, pipelines configurables, resultados temporales, autenticación, roles, gestión de planes,  y validación automatizada.**

</div>

---

## Vista general

**SmartEye-TFG** es una plataforma web orientada al procesamiento de imágenes mediante modelos de visión por computador. El sistema permite que un usuario autenticado suba una imagen, seleccione un pipeline de análisis y obtenga como resultado una o varias imágenes procesadas junto con información estructurada en formato JSON.

La aplicación no se limita a ejecutar un modelo de IA de forma aislada. Su objetivo es ofrecer una base modular y extensible donde distintos modelos, modos de ejecución y etapas de procesamiento puedan combinarse en flujos reutilizables. Para ello, el proyecto integra una arquitectura basada en **Flask**, **SQLAlchemy**, **JWT**, **MariaDB**, **YOLO**, **MediaPipe** y **OpenCV**.

---

## Funcionalidades principales

* Registro e inicio de sesión de usuarios mediante autenticación JWT.
* Gestión de usuarios, roles y permisos de acceso.
* Selección y ejecución de pipelines de procesamiento de imágenes.
* Integración de modelos YOLO y MediaPipe dentro de una arquitectura común.
* Generación de resultados visuales y datos estructurados en formato JSON.
* Control de acceso a pipelines según planes, suscripciones o alquileres activos.
* Descarga segura de resultados mediante tokens temporales.
* Historial de ejecuciones asociado a cada usuario.
* Panel de administración para gestionar usuarios, ejecuciones y pipelines.
* Pruebas automatizadas para validar el funcionamiento del sistema.

---

## Modelos y modos integrados

| Modelo | Modo | Descripción |
|---|---|---|
| **YOLO** | `deteccion` | Detecta objetos y genera cajas delimitadoras con clase, confianza y coordenadas. |
| **YOLO** | `recortes_personas` | Localiza personas y genera recortes independientes de cada una de ellas. |
| **MediaPipe** | `manos` | Detecta puntos clave de las manos y dibuja landmarks sobre la imagen. |
| **MediaPipe** | `pose` | Estima la pose corporal mediante puntos clave del esqueleto humano. |

Estos modos pueden ejecutarse de forma individual o encadenarse en pipelines más complejos, por ejemplo:

- **Identificación de manos**.
- **Identificación de pose**.
- **Detección de objetos**.
- **Aislamiento de personas**.
- **Detección de objetos + análisis de pose**.
- **Recorte de personas + análisis de pose individual**.
- **Recorte de personas + análisis de manos individual**.

---

## Arquitectura del sistema

El proyecto sigue una arquitectura modular basada en separación de responsabilidades. La lógica de presentación, los controladores HTTP, la persistencia, la ejecución de pipelines y la integración con modelos de IA se mantienen desacopladas para facilitar el mantenimiento y la ampliación del sistema.

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                                  Usuario                                    │
└─────────────────────────────────────┬───────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                             Interfaz web                                    │
│        Templates HTML · panel de usuario · tienda · historial · admin       │
└─────────────────────────────────────┬───────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          Controladores Flask                                │
│      auth_controller · shop_controller · pipeline_controller                │
└───────────────┬────────────────────────────────────────────┬────────────────┘
                │                                            │
                ▼                                            ▼
┌─────────────────────────────────┐            ┌──────────────────────────────┐
│ Seguridad y acceso              │            │ Persistencia                 │
│ JWT · roles · planes · licencias│            │ SQLAlchemy · MariaDB         │
└─────────────────────────────────┘            └──────────────────────────────┘
                │                                            │
                └─────────────────────┬──────────────────────┘
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              PipelineRunner                                 │
│           Orquesta las etapas del pipeline y encadena resultados            │
└─────────────────────────────────────┬───────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                                AIFactory                                    │
│             Selecciona dinámicamente el launcher de IA necesario            │
└───────────────┬────────────────────────────────────────────┬────────────────┘
                │                                            │
                ▼                                            ▼
┌───────────────────────────────┐               ┌─────────────────────────────┐
│ YOLO Launcher                 │               │ MediaPipe Launcher          │
│ detección · recortes personas │               │ manos · pose                │
└───────────────┬───────────────┘               └─────────────┬───────────────┘
                │                                             │
                └──────────────────────┬──────────────────────┘
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Resultados de procesamiento                         │
│        imagen procesada · JSON · archivos temporales · tokens · historial   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Capas principales

| Capa | Responsabilidad |
|---|---|
| **Templates web** | Interfaz HTML para registro, login, panel de usuario, tienda, historial, resultados, perfil y administración. |
| **Controllers** | Exponen endpoints HTTP, validan entradas, aplican permisos y coordinan la lógica principal. |
| **Models** | Representan usuarios, roles, planes, suscripciones, modelos de IA, modos, pipelines, ejecuciones y archivos temporales. |
| **Services** | Contienen la lógica de ejecución de pipelines y la integración con motores de IA. |
| **AIFactory** | Selecciona dinámicamente el launcher correspondiente según el modelo solicitado. |
| **Launchers IA** | Encapsulan la ejecución concreta de YOLO y MediaPipe. |
| **Configs JSON** | Definen parámetros editables por modo de ejecución. |
| **Tests** | Verifican autenticación, tienda, modelos, factoría, launchers, pipelines y controladores. |

---

## Flujo de ejecución de un pipeline

```text
Usuario
  │
  │ 1. Selecciona pipeline, configura parámetros y sube imagen
  ▼
Interfaz web
  │
  │ 2. Envía POST /api/v1/analizar con JWT, imagen y configuración
  ▼
Controlador Flask
  │
  │ 3. Valida entrada, usuario, permisos, pipeline y licencias activas
  ▼
PipelineRunner
  │
  │ 4. Recorre las etapas del pipeline en orden
  ▼
AIFactory
  │
  │ 5. Resuelve el launcher adecuado según modelo y modo
  ▼
Launcher IA
  │
  │ 6. Ejecuta YOLO o MediaPipe sobre la imagen de entrada
  ▼
Resultado
  │
  │ 7. Genera imagen procesada, JSON, tokens temporales e historial
  ▼
Usuario
```

---

## Tecnologías utilizadas

| Tecnología | Uso en el proyecto |
|---|---|
| **Python 3.11** | Lenguaje principal de desarrollo. |
| **Flask** | Framework web para backend, rutas y renderizado de vistas. |
| **SQLAlchemy** | ORM para mapear entidades del dominio a la base de datos. |
| **MariaDB** | Sistema gestor de base de datos relacional. |
| **JWT** | Autenticación mediante tokens de acceso. |
| **OpenCV** | Procesamiento de imágenes, lectura, escritura y dibujo de resultados. |
| **YOLO / Ultralytics** | Detección de objetos y localización de personas. |
| **MediaPipe** | Estimación de pose y detección de manos mediante landmarks. |
| **Pytest** | Pruebas automatizadas del backend y servicios principales. |
| **Docker** | Ejecución reproducible del entorno de aplicación y base de datos. |
| **SonarQube / SonarCloud** | Análisis de calidad, seguridad, mantenibilidad, duplicación y cobertura. |
| **CI** | Automatización de comprobaciones de calidad y validación del proyecto. |

---

## Calidad continua y despliegue reproducible

El proyecto incorpora un flujo de validación automatizada orientado a mantener la calidad del código, controlar la cobertura de pruebas y facilitar una ejecución reproducible del entorno.

```text
Commit / Push
     │
     ▼
Ejecución de pruebas automatizadas
     │
     ▼
Medición de cobertura
     │
     ▼
Análisis de calidad y seguridad con SonarQube / SonarCloud
     │
     ▼
Validación del Quality Gate
     │
     ▼
Ejecución reproducible mediante Docker
```

La aplicación está preparada para ejecutarse mediante Docker, separando el servicio web y la base de datos. Esto permite levantar un entorno limpio, inicializar el esquema, cargar datos de demostración y repetir la ejecución de forma controlada sin depender de configuraciones manuales del sistema anfitrión.

Este enfoque facilita la detección temprana de errores, mejora la trazabilidad del desarrollo y permite que el proyecto evolucione incorporando nuevas funcionalidades, modelos de IA o pipelines sin comprometer la estabilidad del sistema.



## Instalación y ejecución

### Requisitos previos

- Docker y Docker Compose.
- Git.
- Navegador web actualizado.
- Modelos de IA necesarios en las carpetas correspondientes o descarga dinámica habilitada en la primera ejecución.

### Variables de entorno

El proyecto obtiene su configuración desde variables de entorno. Para ello crear el fichero `.env` cogiendo de referencia `.env.example`.

### Ejecución con Docker

Construir y arrancar la base de datos:

```bash
docker compose up -d --build db
```

Inicializar el esquema y cargar los datos de demostración:

```bash
docker compose run --rm web python seed.py
```

Arrancar la aplicación web:

```bash
docker compose up -d web
```

Una vez iniciado el servicio, la aplicación estará disponible en:

```text
http://localhost:5000
```

### Reinicio limpio del entorno

Para eliminar contenedores, red y volúmenes asociados, y reconstruir el entorno desde cero:

```bash
docker compose down -v --remove-orphans
docker compose up -d --build db
docker compose run --rm web python seed.py
docker compose up -d web
```

---

## Datos de demostración

El script `seed.py` genera un entorno inicial con roles, usuarios, modelos de IA, modos, planes, licencias y pipelines de ejemplo.

| Usuario | Email | Contraseña | Rol |
|---|---|---|---|
| Administrador | `admin@tfg.es` | `Admin123` | `admin` |
| Pepe Pérez | `pepe@tfg.es` | `User123` | `usuario` |
| Ramón García | `ramon@tfg.es` | `User123` | `usuario` |

> Estas credenciales están pensadas únicamente para demostración y pruebas locales.

---

## Rutas principales de la interfaz web

| Ruta | Descripción |
|---|---|
| `/` | Página pública inicial. |
| `/registro` | Registro de nuevos usuarios. |
| `/login` | Inicio de sesión. |
| `/dashboard` | Panel principal del usuario autenticado. |
| `/shop` | Tienda de planes y modelos de IA. |
| `/mis-compras` | Servicios contratados por el usuario. |
| `/guia-compra` | Guía de pipelines y modelos necesarios. |
| `/historial` | Historial de ejecuciones del usuario. |
| `/resultados/<id_ejecucion>` | Detalle de resultados de una ejecución. |
| `/perfil` | Gestión del perfil del usuario. |
| `/admin` | Panel de administración (gestión de usuarios y pipelines). |


---

## Pruebas automatizadas

El proyecto incluye pruebas orientadas a validar los bloques principales del backend.

Ejecución de los tests:

```bash
pytest
```

Ejecución con salida detallada:

```bash
pytest -v
```

---

## Decisiones de diseño destacadas

### Arquitectura modular

La aplicación separa controladores, servicios, modelos de datos, vistas y motores de IA. Esta organización evita acoplar la interfaz web con los algoritmos de visión artificial y facilita añadir nuevos modelos o modos de ejecución.

### Patrón Factory

La clase `AIFactory` centraliza la selección del launcher adecuado para cada modelo. De esta forma, `PipelineRunner` no necesita conocer los detalles internos de YOLO o MediaPipe, sino únicamente solicitar el motor correspondiente.

### Pipelines por etapas

Cada pipeline se compone de etapas ordenadas. La salida de una etapa puede convertirse en la entrada de la siguiente, permitiendo flujos simples o ramificados. Por ejemplo, un recorte de personas puede generar varias imágenes y aplicar después pose o manos sobre cada una de ellas.

### Resultados temporales tokenizados

Los archivos generados no se exponen mediante rutas internas del servidor. En su lugar, se registran como recursos temporales asociados a tokens de descarga y fecha de expiración.

### Control de acceso por planes y licencias

El sistema filtra los pipelines disponibles según el estado contractual del usuario, teniendo en cuenta planes activos y alquileres temporales de modelos de IA.

### Calidad, pruebas e integración continua

El proyecto está acompañado por pruebas automatizadas y análisis de calidad, lo que permite detectar regresiones, controlar la cobertura y vigilar aspectos de seguridad, duplicación y mantenibilidad del código.

---

## Autor

**Álvaro Pérez Mella**  
Trabajo de Fin de Grado en Ingeniería Informática  
Universidad de Burgos

---

<div align="center">

**Proyecto académico orientado a visión por computador, desarrollo web, arquitectura modular, calidad de código, seguridad aplicada, validación automatizada y despliegue reproducible.**

</div>
