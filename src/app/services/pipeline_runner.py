from app.models import PipelineEtapa
from app.services.ai_factory import AIFactory

class PipelineRunner:
    @staticmethod
    def ejecutar_pipeline(id_pipeline: int, imagen_inicial: str):
        """
        Recupera las etapas del pipeline de la base de datos,
        y ejecuta secuencialmente los modelos IA correspondientes.
        """
        # 1. Obtener las etapas ordenadas por su campo 'orden'
        etapas = PipelineEtapa.query.filter_by(id_pipeline=id_pipeline).order_by(PipelineEtapa.orden).all()
        
        if not etapas:
            raise ValueError(f"El pipeline con ID {id_pipeline} no tiene etapas o no existe.")

        imagen_actual = imagen_inicial
        resultados = []

        # 2. Iterar sobre la secuencia de etapas
        for etapa in etapas:
            # Obtener los nombres usando las relaciones de SQLAlchemy definidas en models.py
            nombre_modelo = etapa.modelo.nombre       # ej: "yolo"
            nombre_modo = etapa.modo.nombre_modo      # ej: "deteccion"
            
            print(f"--- Ejecutando etapa {etapa.orden}: Modelo={nombre_modelo}, Modo={nombre_modo} ---")
            
            # 3. Pedir el lanzador correspondiente al Factory
            launcher = AIFactory.get_launcher(nombre_modelo)
            
            # 4. Ejecutar el modo específico (la imagen_actual se actualiza en cada paso)
            imagen_actual, datos_json = launcher.ejecutar_modo(nombre_modo, imagen_actual)
            
            # 5. Acumular el resultado para cumplir con el RF-MVP-5.4
            resultados.append({
                "etapa": etapa.orden,
                "ia": nombre_modelo,
                "modo": nombre_modo,
                "datos": datos_json
            })

        # Retornamos la última imagen generada y todo el histórico de datos
        return imagen_actual, resultados