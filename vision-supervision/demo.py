"""
Demo de Vision Supervision — detección por color en tiempo real.
"""
import cv2
from vision_supervision import DetectorColor, Anotador


def main():
    print("Vision Supervision — Demo de detección por color")
    print("Presiona 'q' para salir")
    print()

    detector = DetectorColor(
        colores=["rojo", "verde", "azul", "amarillo"],
        area_minima=300,
    )
    anotador = Anotador(grosor_linea=2, tamano_fuente=0.6)

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("No se pudo abrir la cámara")
        return

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        lote = detector.detectar(frame)
        anotada = anotador.anotar(frame, lote)

        # Mostrar conteo
        cv2.putText(
            anotada,
            f"Objetos: {len(lote)}",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.0,
            (255, 255, 255),
            2,
        )

        cv2.imshow("Vision Supervision", anotada)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
