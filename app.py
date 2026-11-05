import streamlit as st
from google import genai
from google.genai import types
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
import time
from datetime import datetime
from zoneinfo import ZoneInfo
import re

st.title("Entrega de tareas - Fundamentos de Programación")

client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_dict(dict(st.secrets["gsheets"]), scope)
gclient = gspread.authorize(creds)
hoja = gclient.open_by_key("178xpm2yswd2wXJ73Xvh50sVxg7h5CeZTjrM6qpLyb10").sheet1

archivo = st.file_uploader("Sube tu archivo .py", type=["py"])

if archivo is not None and st.button("Evaluar Tarea"):
    nombre_base = archivo.name.replace(".py", "")
    zona_horaria = ZoneInfo("Europe/Madrid")
    
    try:
        tarea, alumno = nombre_base.rsplit("_", 1)
        codigo = archivo.getvalue().decode("utf-8")
        tarea_lower = tarea.lower()
        
        es_examen = tarea_lower.startswith("examen")
        es_evaluable = tarea_lower.startswith("tarea_evaluable")
        es_no_evaluable = tarea_lower.startswith("tarea_no_evaluable")
        
        try:
            if not hoja.cell(1, 1).value:
                hoja.update_cell(1, 1, "Alumno")
        except Exception:
            hoja.update_cell(1, 1, "Alumno")

        try:
            celda_alumno = hoja.find(alumno, in_column=1)
        except Exception:
            celda_alumno = None
            
        try:
            celda_tarea = hoja.find(tarea, in_row=1)
        except Exception:
            celda_tarea = None
            
        if es_examen and celda_alumno and celda_tarea:
            valor_actual = hoja.cell(celda_alumno.row, celda_tarea.col).value
            if valor_actual:
                st.error("Ya se ha recibido el examen y no puedes volver a entregarlo.")
                st.stop()

        enunciado = ""
        ruta_txt = f"{tarea}.txt"
        if os.path.exists(ruta_txt):
            with open(ruta_txt, "r", encoding="utf-8") as f:
                contenido = f.read()
                enunciado = f"Enunciado:\n{contenido}\n\n"
                
                if es_evaluable:
                    match = re.search(r"Límite:\s*(\d{2}/\d{2}/\d{4}\s\d{2}:\d{2})", contenido)
                    if match:
                        limite = datetime.strptime(match.group(1), "%d/%m/%Y %H:%M").replace(tzinfo=zona_horaria)
                        if datetime.now(zona_horaria) > limite:
                            st.error("El plazo de entrega ha finalizado.")
                            st.stop()

        if es_examen or es_evaluable:
            instruccion = "Calcula la nota y escribe ÚNICAMENTE el número final. Cero feedback. Cero indicaciones."
        else:
            instruccion = "Indica qué está mal. No des la solución directa ni escribas código correcto. Da una nota orientativa."
        
        prompt_base = f"""Evalúa este código de {alumno} para la tarea {tarea}.
        Asigna puntuaciones parciales y decimales. 
        REGLA ESTRICTA: Si exige una estructura concreta y usa otra, la nota de ese apartado es 0 automáticamente.
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
            prompt = f"Evalúa el código. {enunciado} {instruccion}"
        
        caja_estado = st.empty()
        
        with st.spinner("Procesando..."):
            intentos = 0
            evaluacion = None
            
            while intentos < 3:
                try:
                    caja_estado.info(f"Conectando (Intento {intentos + 1}/3)...")
                    respuesta = client.models.generate_content(
                        model="gemini-3.8-flash",
                        contents=f"{prompt}\n\nCódigo:\n{codigo}",
                        config=types.GenerateContentConfig(temperature=0.0)
                    )
                    evaluacion = respuesta.text
                    caja_estado.empty()
                    break
                except Exception as e:
                    error_str = str(e)
                    if any(err in error_str for err in ["429", "ResourceExhausted", "503", "UNAVAILABLE"]):
                        caja_estado.warning(f"Reintentando en 10s...\n{error_str}")
                        intentos += 1
                        time.sleep(10)
                    else:
                        st.error(f"Fallo crítico de API: {e}")
                        st.stop()
            
            if not evaluacion:
                st.error("Evaluación fallida tras varios intentos.")
                st.stop()
        
        fecha_entrega = datetime.now(zona_horaria).strftime("%d/%m/%Y %H:%M:%S")
        registro_final = f"[{fecha_entrega}]\n{evaluacion}"
        
        if not celda_alumno:
            fila = len(hoja.col_values(1)) + 1
            hoja.update_cell(fila, 1, alumno)
        else:
            fila = celda_alumno.row
            
        if not celda_tarea:
            col = len(hoja.row_values(1)) + 1
            hoja.update_cell(1, col, tarea)
        else:
            col = celda_tarea.col
        
        hoja.update_cell(fila, col, registro_final)
        
        if es_examen or es_evaluable:
            st.success("Recibido correctamente. Se te dará tu nota lo más pronto posible.")
        else:
            st.write(evaluacion)
            
    except ValueError:
        st.error("Formato inválido. Usa: Tarea_Apellido, Nombre.py")
