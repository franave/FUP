import streamlit as st
import google.generativeai as genai
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os

st.title("Entrega de tareas - Fundamentos de Programación")

genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
model = genai.GenerativeModel("gemini-3.8-flash")

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_dict(dict(st.secrets["gsheets"]), scope)
client = gspread.authorize(creds)
hoja = client.open_by_key("178xpm2yswd2wXJ73Xvh50sVxg7h5CeZTjrM6qpLyb10").sheet1

archivo = st.file_uploader("Sube tu archivo .py (ej: examenRA3_Fran.py)", type=["py"])

if archivo is not None and st.button("Evaluar Tarea"):
    nombre_base = archivo.name.replace(".py", "")
    
    try:
        tarea, alumno = nombre_base.rsplit("_", 1)
        codigo = archivo.getvalue().decode("utf-8")
        
        enunciado = ""
        ruta_txt = f"{tarea}.txt"
        if os.path.exists(ruta_txt):
            with open(ruta_txt, "r", encoding="utf-8") as f:
                enunciado = f"Enunciado y puntuaciones:\n{f.read()}\n\n"
        
        tarea_lower = tarea.lower()
        es_evaluable = "examen" in tarea_lower or "evaluable" in tarea_lower
        
        if es_evaluable:
            instruccion = "Genera un texto directo sin saludos, para pegar en Moodle. Muestra nota numérica final y listado preciso de errores. Cero pistas."
        else:
            instruccion = "Señala errores y da pistas técnicas para que el alumno descubra la solución. No escribas el código correcto. Da nota orientativa."
        
        prompt_base = f"""Evalúa este código de {alumno} para la tarea {tarea}.
        Asigna puntuaciones parciales y decimales. 
        REGLA ESTRICTA: Si el enunciado exige usar una estructura concreta y el alumno usa otra, la nota de ese apartado es 0 automáticamente.
        {instruccion}
        {enunciado}Criterios de evaluación aplicados:\n"""
        
        if "ra1" in tarea_lower:
            prompt = prompt_base + "- Variables, métodos de clase, uso correcto, constantes y conversiones."
        elif "ra2" in tarea_lower:
            prompt = prompt_base + "- Métodos, paso de parámetros y librerías.\n- Comentarios."
        elif "ra3" in tarea_lower:
            prompt = prompt_base + "- Estructuras de selección, repetición, sentencias de salto y excepciones."
        elif "ra4" in tarea_lower:
            prompt = prompt_base + "- Consola E/S, formatos, distintos archivos y gestión de ficheros.\n- Comentarios."
        elif "ra5" in tarea_lower:
            prompt = prompt_base + "- Conexiones BD, consultas y operaciones CRUD.\n- Comentarios."
        else:
            prompt = f"Evalúa el código de {alumno}. {enunciado} {instruccion}"
        
        with st.spinner("Evaluando con Gemini..."):
            respuesta = model.generate_content(f"{prompt}\n\nCódigo:\n{codigo}")
            evaluacion = respuesta.text
        
        if es_evaluable:
            if es_evaluable:
                try:
                    celda_alumno = hoja.find(alumno, in_column=1)
                    fila = celda_alumno.row
                except gspread.exceptions.CellNotFound:
                    fila = len(hoja.col_values(1)) + 1
                    hoja.update_cell(fila, 1, alumno)
                    
                try:
                    celda_tarea = hoja.find(tarea, in_row=1)
                    col = celda_tarea.col
                except gspread.exceptions.CellNotFound:
                    col = len(hoja.row_values(1)) + 1
                    hoja.update_cell(1, col, tarea)
                
            hoja.update_cell(fila, col, evaluacion)
            
        st.success("Evaluación completada")
        st.write(evaluacion)
        
    except ValueError:
        st.error("Error de formato. Usa: Tarea_Apellido, Nombre.py")
