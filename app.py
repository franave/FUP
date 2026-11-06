import streamlit as st
from google import genai
from google.genai import types
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
from datetime import datetime
from zoneinfo import ZoneInfo
import re

st.set_page_config(page_title="Entrega de Tareas - FP", page_icon="💻", layout="centered")

st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    /* Eliminar el icono de enlace ancla (🔗) de las cabeceras */
    .stMarkdown a, a.header-anchor {
        display: none !important;
    }
    .block-container {
        padding-top: 3rem;
        max-width: 45rem;
    }
    /* Estrangular el tamaño del selector de archivos para igualarlo al botón */
    div[data-testid="stFileUploader"] {
        padding-bottom: 0rem;
        margin-bottom: 0rem;
    }
    div[data-testid="stFileUploaderDropzone"] {
        padding: 0.2rem 1rem !important;
        min-height: 0px !important;
        display: flex;
        align-items: center;
    }
    div[data-testid="stFileUploaderDropzone"] section {
        padding: 0rem !important;
        margin: 0rem !important;
    }
    </style>
""", unsafe_allow_html=True)

st.markdown("<h1 style='text-align: center; margin-bottom: 0;'>💻 Fundamentos de Programación</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #a3a8b8; font-size: 1.1rem; margin-bottom: 2.5rem;'>Sube tu script para registrar la entrega.</p>", unsafe_allow_html=True)

@st.cache_resource(ttl=3600)
def conectar_servicios():
    cliente_api = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
    alcance = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    credenciales = ServiceAccountCredentials.from_json_keyfile_dict(dict(st.secrets["gsheets"]), alcance)
    cliente_sheets = gspread.authorize(credenciales)
    documento = cliente_sheets.open_by_key("178xpm2yswd2wXJ73Xvh50sVxg7h5CeZTjrM6qpLyb10")
    return cliente_api, documento

client, doc = conectar_servicios()

@st.cache_resource(ttl=3600)
def preparar_hojas(_doc):
    try:
        h_eval = _doc.worksheet("Programación")
    except gspread.exceptions.WorksheetNotFound:
        h_eval = _doc.sheet1
        h_eval.update_title("Programación")

    try:
        h_no_eval = _doc.worksheet("No Evaluables Prog")
    except gspread.exceptions.WorksheetNotFound:
        try:
            h_no_eval = _doc.add_worksheet(title="No Evaluables Prog", rows=100, cols=20)
            h_no_eval.update_cell(1, 1, "Alumno")
        except Exception:
            h_no_eval = _doc.worksheet("No Evaluables Prog")
    return h_eval, h_no_eval

hoja_eval, hoja_no_eval = preparar_hojas(doc)

ORDEN_COLUMNAS = [
    "Alumno",
    "Tarea Evaluable RA1", "Examen RA1",
    "Tarea Evaluable RA2", "Examen RA2",
    "Tarea Evaluable RA3", "Examen RA3",
    "Tarea Evaluable RA4", "Examen RA4",
    "Tarea Evaluable RA5", "Examen RA5",
    "Tarea Evaluable RA6", "Examen RA6"
]

with st.container(border=True):
    col_izq, col_der = st.columns([3, 1], vertical_alignment="center")
    
    with col_izq:
        archivo = st.file_uploader("Selecciona tu archivo .py", type=["py"], label_visibility="collapsed")
    
    with col_der:
        boton_entrega = st.button("Confirmar Entrega", use_container_width=True)

if archivo is not None and boton_entrega:
    nombre_base = archivo.name.replace(".py", "")
    zona_horaria = ZoneInfo("Europe/Madrid")
    
    try:
        match_tarea = re.match(r'^(.*?[rR][aA]\d+)[_,-]*(.*)$', nombre_base)
        
        if match_tarea:
            tarea = match_tarea.group(1).strip("_")
            resto_nombre = match_tarea.group(2).strip("_")
            
            if "_" in resto_nombre:
                partes_nombre = resto_nombre.rsplit("_", 1)
                apellidos = partes_nombre[0].replace("_", " ")
                nombre = partes_nombre[1]
                alumno = f"{apellidos}, {nombre}"
            else:
                alumno = resto_nombre
        else:
            tarea, alumno = nombre_base.rsplit("_", 1)
            
        codigo = archivo.getvalue().decode("utf-8")
        tarea_lower = tarea.lower()
        
        match_ra = re.search(r'(ra\d+)', tarea_lower)
        ra = match_ra.group(1).upper() if match_ra else ""
        
        es_examen = "examen" in tarea_lower
        es_no_evaluable = "tarea_no_evaluable" in tarea_lower
        es_evaluable = "tarea_evaluable" in tarea_lower and not es_no_evaluable
        
        if es_examen:
            cabecera = f"Examen {ra}".strip()
            hoja_activa = hoja_eval
        elif es_evaluable:
            cabecera = f"Tarea Evaluable {ra}".strip()
            hoja_activa = hoja_eval
        else:
            cabecera = f"No Evaluable {ra}".strip()
            hoja_activa = hoja_no_eval

        cabeceras_existentes = hoja_activa.row_values(1)
        alumnos_existentes = hoja_activa.col_values(1)

        if not cabeceras_existentes:
            hoja_activa.update_cell(1, 1, "Alumno")
            cabeceras_existentes = ["Alumno"]

        try:
            fila_alumno = alumnos_existentes.index(alumno) + 1
            alumno_registrado = True
        except ValueError:
            fila_alumno = len(alumnos_existentes) + 1
            alumno_registrado = False

        if hoja_activa == hoja_eval and cabecera in ORDEN_COLUMNAS:
            col_tarea = ORDEN_COLUMNAS.index(cabecera) + 1
            if len(cabeceras_existentes) < col_tarea or cabeceras_existentes[col_tarea - 1] != cabecera:
                hoja_activa.update_cell(1, col_tarea, cabecera)
        else:
            try:
                col_tarea = cabeceras_existentes.index(cabecera) + 1
            except ValueError:
                col_tarea = len(cabeceras_existentes) + 1
                hoja_activa.update_cell(1, col_tarea, cabecera)

        if es_examen and alumno_registrado:
            fila_datos = hoja_activa.row_values(fila_alumno)
            if len(fila_datos) >= col_tarea and fila_datos[col_tarea - 1].strip():
                st.error("Ya se ha recibido el examen y no puedes volver a entregarlo.")
                st.stop()

        enunciado = ""
        ruta_txt = f"{tarea}.txt"
        if os.path.exists(ruta_txt):
            with open(ruta_txt, "r", encoding="utf-8") as f:
                contenido = f.read()
                enunciado = f"Enunciado:\n{contenido}\n\n"
                
                if es_evaluable or es_examen:
                    ahora = datetime.now(zona_horaria)
                    
                    match_inicio = re.search(r"Inicio:\s*(\d{2}/\d{2}/\d{4}\s\d{2}:\d{2})", contenido)
                    if match_inicio:
                        inicio = datetime.strptime(match_inicio.group(1), "%d/%m/%Y %H:%M").replace(tzinfo=zona_horaria)
                        if ahora < inicio:
                            st.error("El plazo de entrega aún no ha comenzado.")
                            st.stop()
                            
                    match_limite = re.search(r"Límite:\s*(\d{2}/\d{2}/\d{4}\s\d{2}:\d{2})", contenido)
                    if match_limite:
                        limite = datetime.strptime(match_limite.group(1), "%d/%m/%Y %H:%M").replace(tzinfo=zona_horaria)
                        if ahora > limite:
                            st.error("El plazo de entrega ha finalizado.")
                            st.stop()

        if es_examen or es_evaluable:
            instruccion = (
                "Actúa como un corrector automático estricto y determinista. Muestra la nota numérica final matemática. "
                "Desglosa la puntuación exacta por apartados sin variaciones. "
                "Para cada apartado donde el alumno no tenga el 100% de la nota, explica el motivo exacto y objetivo del fallo. "
                "Cero saludos. No des el código correcto. Si tiene un 10, escribe solo '10 - Perfecto'. "
                "REGLA DE FORMATO: PROHIBIDO usar Markdown. No uses asteriscos (*) ni almohadillas (#). "
                "Escribe en texto plano puro. Usa MAYÚSCULAS para resaltar los títulos de los apartados y guiones normales (-) para las listas."
            )
        else:
            instruccion = "Indica qué está mal de forma estricta. No des la solución directa ni escribas código correcto. Da una nota orientativa."
        
        prompt_base = f"""Evalúa este código de {alumno} para la tarea {tarea}.
        REGLA ESTRICTA 1: Si exige una estructura concreta y usa otra, la nota de ese apartado es 0 automáticamente.
        REGLA ESTRICTA 2: Comprueba estrictamente la funcionalidad del código. Penaliza las puntuaciones si el flujo de ejecución carece de sentido lógico o las estructuras están desordenadas.
        {instruccion}
        {enunciado}Criterios aplicados:\n"""
        
        if "ra1" in tarea_lower:
            prompt = prompt_base + "- Variables, métodos de clase, constantes, conversiones."
        elif "ra2" in tarea_lower:
            prompt = prompt_base + "- Métodos, parámetros, librerías, comentarios."
        elif "ra3" in tarea_lower:
            prompt = prompt_base + "- Selección, repetición, saltos, excepciones."
        elif "ra4" in tarea_lower:
            prompt = prompt_base + "- Consola E/S, formatos, ficheros, comentarios."
        elif "ra5" in tarea_lower:
            prompt = prompt_base + "- Conexiones BD, CRUD, comentarios."
        else:
            prompt = f"Evalúa el código de forma determinista. {enunciado} {instruccion}"
        
        with st.spinner("Registrando entrega en el servidor..."):
            try:
                respuesta = client.models.generate_content(
                    model="gemini-3.8-flash",
                    contents=f"{prompt}\n\nCódigo:\n{codigo}",
                    config=types.GenerateContentConfig(
                        temperature=0.0,
                        top_p=0.0,
                        top_k=1
                    )
                )
                evaluacion = respuesta.text
            except Exception as e:
                st.error("Error en la conexión con el servidor. Vuelve a intentarlo.")
                st.stop()
        
        fecha_entrega = datetime.now(zona_horaria).strftime("%d/%m/%Y %H:%M:%S")
        registro_final = f"[{fecha_entrega}]\n{evaluacion}"
        
        if not alumno_registrado:
            hoja_activa.update_cell(fila_alumno, 1, alumno)
            total_filas = len(alumnos_existentes) + 1
        else:
            total_filas = len(alumnos_existentes)
            
        hoja_activa.update_cell(fila_alumno, col_tarea, registro_final)
        
        if total_filas > 1:
            hoja_activa.sort((1, 'asc'), range=f'A2:ZZ{total_filas}')
        
        if es_examen or es_evaluable:
            st.success("Archivo subido. Las calificaciones se publicarán al terminar el plazo.")
        else:
            st.write(evaluacion)
            
    except ValueError:
        st.error("Error en el archivo. Comprueba el formato del nombre.")
