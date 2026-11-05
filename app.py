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

doc = gclient.open_by_key("178xpm2yswd2wXJ73Xvh50sVxg7h5CeZTjrM6qpLyb10")

# Gestión limpia y segura de pestañas
try:
    hoja_eval = doc.worksheet("Programación")
except gspread.exceptions.WorksheetNotFound:
    hoja_eval = doc.sheet1
    hoja_eval.update_title("Programación")

try:
    hoja_no_eval = doc.worksheet("No Evaluables Prog")
except gspread.exceptions.WorksheetNotFound:
    try:
        hoja_no_eval = doc.add_worksheet(title="No Evaluables Prog", rows=100, cols=20)
        hoja_no_eval.update_cell(1, 1, "Alumno")
    except Exception:
        hoja_no_eval = doc.worksheet("No Evaluables Prog")

ORDEN_COLUMNAS = [
    "Alumno",
    "Tarea Evaluable RA1", "Examen RA1",
    "Tarea Evaluable RA2", "Examen RA2",
    "Tarea Evaluable RA3", "Examen RA3",
    "Tarea Evaluable RA4", "Examen RA4",
    "Tarea Evaluable RA5", "Examen RA5",
    "Tarea Evaluable RA6", "Examen RA6"
]

archivo = st.file_uploader("Sube tu archivo .py", type=["py"])

if archivo is not None and st.button("Evaluar Tarea"):
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
            
        try:
            if not hoja_activa.cell(1, 1).value:
                hoja_activa.update_cell(1, 1, "Alumno")
        except Exception:
            hoja_activa.update_cell(1, 1, "Alumno")

        try:
            celda_alumno = hoja_activa.find(alumno, in_column=1)
        except Exception:
            celda_alumno = None
            
        if hoja_activa == hoja_eval and cabecera in ORDEN_COLUMNAS:
            col_tarea = ORDEN_COLUMNAS.index(cabecera) + 1
            try:
                if not hoja_activa.cell(1, col_tarea).value:
                    hoja_activa.update_cell(1, col_tarea, cabecera)
            except Exception:
                hoja_activa.update_cell(1, col_tarea, cabecera)
        else:
            try:
                celda_tarea = hoja_activa.find(cabecera, in_row=1)
                col_tarea = celda_tarea.col
            except Exception:
                col_tarea = len(hoja_activa.row_values(1)) + 1
                hoja_activa.update_cell(1, col_tarea, cabecera)

        if es_examen and celda_alumno:
            try:
                valor_actual = hoja_activa.cell(celda_alumno.row, col_tarea).value
                if valor_actual:
                    st.error("Ya se ha recibido el examen y no puedes volver a entregarlo.")
                    st.stop()
            except Exception:
                pass

        enunciado = ""
        ruta_txt = f"{tarea}.txt"
        if os.path.exists(ruta_txt):
            with open(ruta_txt, "r", encoding="utf-8") as f:
                contenido = f.read()
                enunciado = f"Enunciado:\n{contenido}\n\n"
                
                if es_evaluable:
                    match_limite = re.search(r"Límite:\s*(\d{2}/\d{2}/\d{4}\s\d{2}:\d{2})", contenido)
                    if match_limite:
                        limite = datetime.strptime(match_limite.group(1), "%d/%m/%Y %H:%M").replace(tzinfo=zona_horaria)
                        if datetime.now(zona_horaria) > limite:
                            st.error("El plazo de entrega ha finalizado.")
                            st.stop()

        if es_examen or es_evaluable:
            instruccion = (
                "Muestra la nota numérica final. "
                "Desglosa la puntuación por apartados. "
                "Para cada apartado donde el alumno no tenga el 100% de la nota, explica el motivo exacto del fallo. "
                "Cero saludos. No des el código correcto. Si tiene un 10, escribe solo '10 - Perfecto'. "
                "REGLA DE FORMATO: PROHIBIDO usar Markdown. No uses asteriscos (*) ni almohadillas (#). "
                "Escribe en texto plano puro. Usa MAYÚSCULAS para resaltar los títulos de los apartados y guiones normales (-) para las listas."
            )
        else:
            instruccion = "Indica qué está mal. No des la solución directa ni escribas código correcto. Da una nota orientativa."
        
        prompt_base = f"""Evalúa este código de {alumno} para la tarea {tarea}.
        Asigna puntuaciones parciales y decimales. 
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
            fila = len(hoja_activa.col_values(1)) + 1
            hoja_activa.update_cell(fila, 1, alumno)
        else:
            fila = celda_alumno.row
        
        hoja_activa.update_cell(fila, col_tarea, registro_final)
        
        total_filas = len(hoja_activa.col_values(1))
        if total_filas > 1:
            hoja_activa.sort((1, 'asc'), range=f'A2:ZZ{total_filas}')
        
        if es_examen or es_evaluable:
            st.success("Recibido correctamente. Se te dará tu nota lo más pronto posible.")
        else:
            st.write(evaluacion)
            
    except ValueError:
        st.error("Formato inválido al procesar el archivo. Revisa el nombre.")
