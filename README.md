# 🤖 AI Quota Monitor v2.5

> **Monitor flotante en tiempo real de cuotas, tokens y límites de IA (Gemini & Claude) para Antigravity.**  
> Desarrollado por **Darkplayer00**.

![Windows 10/11 Compatible](https://img.shields.io/badge/Windows-10%20%7C%2011%20(64--bit)-0078D6?style=flat&logo=windows)
![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat&logo=python&logoColor=white)
![Licence](https://img.shields.io/badge/License-MIT-green?style=flat)

---

## ✨ Características Principales

* 📊 **Monitoreo Dual de Modelos:** Conmuta entre **Gemini Models** (Flash + Pro) y **Claude / GPT** en 1 clic.
* ⏱️ **Cuentas Regresivas en Vivo:** Visualiza segundo a segundo el tiempo exacto que falta para el reset del **Cupo Semanal** y la **Ventana de 5 Horas**, junto con la fecha y hora exacta programada.
* 📁 **Seguimiento por Proyecto en Tiempo Real:** Detecta automáticamente el workspace activo y desglosa el consumo por proyecto (por ejemplo, *WhiteBoard*, *widgets*, etc.).
* ⚡ **Historial de Prompts Recientes:** Subpestaña `[ ⏱️ Recientes ]` con el gasto exacto de tus últimas 5 consultas y la hora en que se ejecutaron.
* 🟢 **Indicador Inteligente de Ritmo (*Burn Rate*):** Evalúa tu velocidad de gasto y te indica si tu ritmo es seguro (`~X%/día disponible`) o si se agotará antes del reset.
* 💊 **Modo Píldora Flotante Ultra-Compacta:** Pulsa `—` o haz doble clic para reducir el widget a una barrita horizontal discreta de 34px.
* 🎨 **Temas Visuales Modernos:** *Bento Modern Dark*, *OLED Black*, *Bento Clean Light (Claro)* y *Cyberpunk Neon*.
* 🖥️ **Soporte Multi-Monitor Completo:** Compatible con configuraciones de 2 o más pantallas, coordenadas negativas y acoplamiento magnético (*snapping*) inteligente en los bordes de cada monitor.
* ⌨️ **Atajo Global de Teclado:** Presiona `Ctrl + Alt + Q` en cualquier momento para mostrar u ocultar la ventana desde cualquier app o juego.
* 📑 **Exportación de Datos:** Exporta tu historial de consultas a Excel (`.csv` con codificación UTF-8 BOM) o copia un resumen formateado al portapapeles.
* 🔕 **Icono en Bandeja del Sistema:** Minimización limpia a la bandeja con cierre síncrono y sin iconos fantasma residuales.

---

## 🚀 Instalación y Uso

## 📥 Descargas Oficiales (Releases)

| Opción | Archivo | Descripción |
| :--- | :--- | :--- |
| 🚀 **Instalador Oficial de Windows** | [**`AI_Quota_Monitor_Setup.exe`**](https://github.com/darkplayer00/ai-quota-monitor/releases/download/v2.5.0/AI_Quota_Monitor_Setup.exe) | Asistente de instalación clásico (*Siguiente > Siguiente > Instalar*), accesos directos y desinstalador formal. |
| 💼 **Versión Portable** | [**`AI_Quota_Monitor_Portable.zip`**](https://github.com/darkplayer00/ai-quota-monitor/releases/download/v2.5.0/AI_Quota_Monitor_Portable.zip) | Sin instalación. Ejecutable autónomo listo para correr desde cualquier carpeta o pendrive USB (datos en `./data/`). |

---

## 🛠️ Ejecución desde el Código Fuente

Si prefieres ejecutar o modificar el código fuente con Python:

```bash
# 1. Clonar el repositorio
git clone https://github.com/tu-usuario/ai-quota-monitor.git
cd ai-quota-monitor

# 2. Instalar dependencias requeridas
pip install customtkinter pystray Pillow

# 3. Iniciar el widget
python widget_app.py
```

### Compilar el Ejecutable con PyInstaller:
```bash
python -m PyInstaller --noconsole --onefile --icon=icon.ico --name="AI_Quota_Widget" --add-data="icon.ico;." --clean widget_app.py
```

---

## 🔒 Privacidad y Seguridad

* **100% Local:** No se envían datos ni estadísticas a servidores externos.
* **Sin Credenciales Almacenadas:** No requiere ni almacena claves API, contraseñas ni tokens de autenticación de Google o Anthropic.
* **Comunicación Local (127.0.0.1):** Se comunica de forma exclusiva con el Language Server local de Antigravity en tu propia máquina a través de loopback.

---

## 👨‍💻 Autor

Desarrollado con dedicación por **Darkplayer00**.  
Distribuido bajo la licencia [MIT](LICENSE).
