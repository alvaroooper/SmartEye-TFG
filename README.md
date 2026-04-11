# AI Image Processing Platform

## Descripción

Este proyecto consiste en el desarrollo de una aplicación web para el procesamiento de imágenes mediante distintos modelos de Inteligencia Artificial. El sistema permite al usuario subir una imagen, seleccionar un pipeline con distintos modelos y modos dentro del mismo, y obtener como resultado una imagen procesada junto con información estructurada en formato JSON.

La aplicación está diseñada con un enfoque modular y extensible, permitiendo la incorporación de nuevos modelos, modos de procesamiento y pipelines sin necesidad de modificar la arquitectura base.

## Funcionalidades principales

- Subida de imágenes a través de la interfaz web o la API.
- Procesamiento mediante diferentes modelos de IA.
- Soporte para múltiples modos por modelo.
- Ejecución de pipelines de procesamiento encadenado.
- Generación de resultados en formato imagen y JSON.
- Gestión de usuarios, roles y planes de acceso.
- Persistencia de datos mediante base de datos relacional.

## Arquitectura

El sistema sigue una arquitectura basada en separación de responsabilidades:

- Backend desarrollado con Flask.
- Servicios de Inteligencia Artificial encapsulados por modelo.
- Uso del patrón Factory para la selección dinámica de tareas.
- Base de datos relacional para la persistencia de información.
- Interfaz web para demostración del sistema.

Esta estructura permite desacoplar la lógica de negocio del procesamiento de IA, facilitando la escalabilidad y el mantenimiento.


## Tecnologías utilizadas

- Python 3
- Flask
- OpenCV
- YOLO
- MediaPipe
- MariaDB
- Debian (entorno de desarrollo)
