"""
Sistema de Solicitudes — Flask sin base de datos
Los datos se guardan en memoria (se pierden al reiniciar).
Cuando quieras conectar MySQL, usa la version app_mysql.py
"""

import os
import hashlib
import requests
import json
from datetime import datetime
from functools import wraps
from flask import Flask, request, jsonify, session

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "cambia-esto-en-produccion")

WA_PHONE  = os.environ.get("WA_PHONE",  "")
WA_APIKEY = os.environ.get("WA_APIKEY", "")

# ════════════════════════════════════════════════════════════
#  RUTAS DE ARCHIVOS JSON
# ════════════════════════════════════════════════════════════
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(DATA_DIR, exist_ok=True)

USUARIOS_FILE    = os.path.join(DATA_DIR, "usuarios.json")
SOLICITUDES_FILE = os.path.join(DATA_DIR, "solicitudes.json")
COMENTARIOS_FILE = os.path.join(DATA_DIR, "comentarios.json")
VEHICULOS_FILE   = os.path.join(DATA_DIR, "vehiculos.json")
OPERADORES_FILE  = os.path.join(DATA_DIR, "operadores.json")
ACTIVIDADES_FILE = os.path.join(DATA_DIR, "actividades.json")

# ════════════════════════════════════════════════════════════
#  FUNCIONES DE PERSISTENCIA
# ════════════════════════════════════════════════════════════
def leer_json(filepath, default=None):
    if default is None: default = []
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return default
    return default

def guardar_json(filepath, data):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ════════════════════════════════════════════════════════════
#  DATOS EN MEMORIA (se cargan del JSON al iniciar)
# ════════════════════════════════════════════════════════════
def hp(p): return hashlib.sha256(p.encode()).hexdigest()

def cargar_datos():
    global USUARIOS, SOLICITUDES, COMENTARIOS, VEHICULOS, OPERADORES, ACTIVIDADES
    USUARIOS = leer_json(USUARIOS_FILE)
    if not USUARIOS:
        USUARIOS = [
            {"id": 1, "username": "superadmin", "password": hp("super123"), "rol": "superadmin"},
            {"id": 2, "username": "admin1",     "password": hp("admin123"), "rol": "admin"},
            {"id": 3, "username": "admin2",     "password": hp("admin456"), "rol": "admin"},
        ]
        guardar_json(USUARIOS_FILE, USUARIOS)
    SOLICITUDES = leer_json(SOLICITUDES_FILE, [])
    COMENTARIOS = leer_json(COMENTARIOS_FILE, [])
    VEHICULOS   = leer_json(VEHICULOS_FILE, [])
    OPERADORES  = leer_json(OPERADORES_FILE, [])
    ACTIVIDADES = leer_json(ACTIVIDADES_FILE, [])

USUARIOS = []
SOLICITUDES = []
COMENTARIOS = []
VEHICULOS = []
OPERADORES = []
ACTIVIDADES = []
WA_CONFIG = {"phone": WA_PHONE, "apikey": WA_APIKEY}

cargar_datos()

# ════════════════════════════════════════════════════════════
#  HELPERS
# ════════════════════════════════════════════════════════════
def login_req(f):
    @wraps(f)
    def w(*a, **k):
        if "user" not in session:
            return jsonify({"error": "No autenticado"}), 401
        return f(*a, **k)
    return w

def role(*roles):
    def d(f):
        @wraps(f)
        def w(*a, **k):
            if "user" not in session:
                return jsonify({"error": "No autenticado"}), 401
            if session["user"]["rol"] not in roles:
                return jsonify({"error": "Sin permiso"}), 403
            return f(*a, **k)
        return w
    return d

def sol_to_dict(s, include_comments=False):
    d = dict(s)
    d["solicitante"] = s["nombre"]
    d["comentarios"] = []
    if include_comments:
        d["comentarios"] = [c for c in COMENTARIOS if c["solicitudId"] == s["id"]]
    return d

def now_str():
    return datetime.now().strftime("%d/%m/%y %H:%M")

def new_id():
    return int(datetime.now().timestamp() * 1000)

# ════════════════════════════════════════════════════════════
#  FRONTEND
# ════════════════════════════════════════════════════════════
@app.route("/")
def index():
    html_path = os.path.join(os.path.dirname(__file__), "solicitudes.html")
    with open(html_path, encoding="utf-8") as f:
        return f.read()

# ════════════════════════════════════════════════════════════
#  AUTH
# ════════════════════════════════════════════════════════════
@app.route("/api/login", methods=["POST"])
def login():
    d = request.json
    u = next((x for x in USUARIOS
               if x["username"] == d.get("username","").strip()
               and x["password"] == hp(d.get("password",""))), None)
    if not u:
        return jsonify({"ok": False, "error": "Usuario o contrasena incorrectos"}), 401
    safe = {"id": u["id"], "username": u["username"], "rol": u["rol"]}
    session["user"] = safe
    return jsonify({"ok": True, "user": safe})

@app.route("/api/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"ok": True})

@app.route("/api/me")
def me():
    return jsonify({"user": session.get("user")})

# ════════════════════════════════════════════════════════════
#  SOLICITUDES
# ════════════════════════════════════════════════════════════
@app.route("/api/solicitudes", methods=["POST"])
def crear_solicitud():
    d   = request.json
    sol = {
        "id":          new_id(),
        "nombre":      d.get("nombre","").strip(),
        "tipo":        d.get("tipo","").strip(),
        "descripcion": d.get("descripcion","").strip(),
        "prioridad":   d.get("prioridad","Normal"),
        "estado":      "Pendiente",
        "asignadoA":   None,
        "fecha":       now_str(),
    }
    SOLICITUDES.insert(0, sol)
    guardar_json(SOLICITUDES_FILE, SOLICITUDES)
    wa_ok = enviar_whatsapp(sol)
    return jsonify({"ok": True, "solicitud": sol_to_dict(sol, True), "wa_enviado": wa_ok})

@app.route("/api/solicitudes", methods=["GET"])
@login_req
def listar_solicitudes():
    u = session["user"]
    if u["rol"] == "superadmin":
        sols = SOLICITUDES
    else:
        sols = [s for s in SOLICITUDES if s.get("asignadoA") == u["username"]]
    return jsonify([sol_to_dict(s, True) for s in sols])

@app.route("/api/solicitudes/<int:sid>/estado", methods=["PATCH"])
@login_req
def cambiar_estado(sid):
    u    = session["user"]
    data = request.json
    sol  = next((s for s in SOLICITUDES if s["id"] == sid), None)
    if not sol:
        return jsonify({"error": "No encontrada"}), 404
    if u["rol"] == "admin" and sol.get("asignadoA") != u["username"]:
        return jsonify({"error": "Sin permiso"}), 403
    sol["estado"] = data.get("estado", sol["estado"])
    guardar_json(SOLICITUDES_FILE, SOLICITUDES)
    texto = (data.get("comentario") or "").strip()
    if texto:
        COMENTARIOS.append({
            "id":          new_id(),
            "solicitudId": sid,
            "autor":       u["username"],
            "rolAutor":    u["rol"],
            "texto":       texto,
            "estadoRef":   sol["estado"],
            "fecha":       now_str(),
        })
        guardar_json(COMENTARIOS_FILE, COMENTARIOS)
    return jsonify({"ok": True, "solicitud": sol_to_dict(sol, True)})

@app.route("/api/solicitudes/<int:sid>/comentarios", methods=["POST"])
@login_req
def agregar_comentario(sid):
    u    = session["user"]
    data = request.json
    sol  = next((s for s in SOLICITUDES if s["id"] == sid), None)
    if not sol:
        return jsonify({"error": "No encontrada"}), 404
    if u["rol"] == "admin" and sol.get("asignadoA") != u["username"]:
        return jsonify({"error": "Sin permiso"}), 403
    texto = (data.get("texto") or "").strip()
    if not texto:
        return jsonify({"error": "El comentario no puede estar vacio"}), 400
    com = {
        "id":          new_id(),
        "solicitudId": sid,
        "autor":       u["username"],
        "rolAutor":    u["rol"],
        "texto":       texto,
        "estadoRef":   sol["estado"],
        "fecha":       now_str(),
    }
    COMENTARIOS.append(com)
    guardar_json(COMENTARIOS_FILE, COMENTARIOS)
    return jsonify({"ok": True, "comentario": com})

@app.route("/api/solicitudes/<int:sid>/prioridad", methods=["PATCH"])
@role("superadmin")
def cambiar_prioridad(sid):
    sol = next((s for s in SOLICITUDES if s["id"] == sid), None)
    if not sol:
        return jsonify({"error": "No encontrada"}), 404
    p = request.json.get("prioridad","Normal")
    if p not in ("Normal","Alta","Urgente"):
        return jsonify({"error": "Prioridad invalida"}), 400
    sol["prioridad"] = p
    guardar_json(SOLICITUDES_FILE, SOLICITUDES)
    return jsonify({"ok": True})


@app.route("/api/solicitudes/<int:sid>/asignar", methods=["PATCH"])
@role("superadmin")
def asignar(sid):
    sol = next((s for s in SOLICITUDES if s["id"] == sid), None)
    if not sol:
        return jsonify({"error": "No encontrada"}), 404
    sol["asignadoA"] = request.json.get("asignadoA") or None
    guardar_json(SOLICITUDES_FILE, SOLICITUDES)
    return jsonify({"ok": True})

# ════════════════════════════════════════════════════════════
#  USUARIOS
# ════════════════════════════════════════════════════════════
@app.route("/api/usuarios", methods=["GET"])
@role("superadmin")
def listar_usuarios():
    return jsonify([{"id":u["id"],"username":u["username"],"rol":u["rol"]} for u in USUARIOS])

@app.route("/api/usuarios", methods=["POST"])
@role("superadmin")
def crear_usuario():
    d        = request.json
    username = d.get("username","").strip()
    password = d.get("password","").strip()
    rol      = d.get("rol","admin")
    if not username or not password:
        return jsonify({"ok": False, "error": "Faltan datos"}), 400
    if any(u["username"] == username for u in USUARIOS):
        return jsonify({"ok": False, "error": "Ya existe"}), 400
    nuevo = {"id": new_id(), "username": username, "password": hp(password), "rol": rol}
    USUARIOS.append(nuevo)
    guardar_json(USUARIOS_FILE, USUARIOS)
    return jsonify({"ok": True, "user": {"id": nuevo["id"], "username": username, "rol": rol}})

@app.route("/api/usuarios/<int:uid>", methods=["DELETE"])
@role("superadmin")
def eliminar_usuario(uid):
    u = next((x for x in USUARIOS if x["id"] == uid), None)
    if not u:
        return jsonify({"error": "No encontrado"}), 404
    if u["username"] == "superadmin":
        return jsonify({"error": "No se puede eliminar"}), 403
    USUARIOS.remove(u)
    guardar_json(USUARIOS_FILE, USUARIOS)
    return jsonify({"ok": True})

# ════════════════════════════════════════════════════════════
#  VEHÍCULOS
# ════════════════════════════════════════════════════════════
@app.route("/api/vehiculos", methods=["GET"])
@login_req
def listar_vehiculos():
    return jsonify(VEHICULOS)

@app.route("/api/vehiculos", methods=["POST"])
@role("superadmin")
def crear_vehiculo():
    d = request.json
    nombre = d.get("nombre","").strip()
    tipo = d.get("tipo","camioneta")
    placa = d.get("placa","").strip()
    if not nombre or not placa:
        return jsonify({"error": "Faltan datos"}), 400
    if any(v.get("placa")==placa for v in VEHICULOS):
        return jsonify({"error": "Placa ya existe"}), 400
    v = {
        "id": new_id(),
        "nombre": nombre,
        "tipo": tipo,
        "placa": placa,
        "disponible": True,
        "fecha_creacion": now_str(),
    }
    VEHICULOS.append(v)
    guardar_json(VEHICULOS_FILE, VEHICULOS)
    return jsonify({"ok": True, "vehiculo": v})

@app.route("/api/vehiculos/<int:vid>", methods=["DELETE"])
@role("superadmin")
def eliminar_vehiculo(vid):
    v = next((x for x in VEHICULOS if x["id"] == vid), None)
    if not v:
        return jsonify({"error": "No encontrado"}), 404
    VEHICULOS.remove(v)
    guardar_json(VEHICULOS_FILE, VEHICULOS)
    return jsonify({"ok": True})

# ════════════════════════════════════════════════════════════
#  OPERADORES
# ════════════════════════════════════════════════════════════
@app.route("/api/operadores", methods=["GET"])
@login_req
def listar_operadores():
    return jsonify(OPERADORES)

@app.route("/api/operadores", methods=["POST"])
@role("superadmin")
def crear_operador():
    d = request.json
    nombre = d.get("nombre","").strip()
    telefono = d.get("telefono","").strip()
    licencia = d.get("licencia","Clase B")
    disponible = d.get("disponible", True)
    observaciones = d.get("observaciones","").strip()
    
    if not nombre or not telefono:
        return jsonify({"error": "Faltan datos"}), 400
    
    op = {
        "id": new_id(),
        "nombre": nombre,
        "telefono": telefono,
        "licencia": licencia,
        "disponible": disponible,
        "observaciones": observaciones,
        "fecha_creacion": now_str(),
    }
    OPERADORES.append(op)
    guardar_json(OPERADORES_FILE, OPERADORES)
    return jsonify({"ok": True, "operador": op})

@app.route("/api/operadores/<int:oid>", methods=["DELETE"])
@role("superadmin")
def eliminar_operador(oid):
    op = next((x for x in OPERADORES if x["id"] == oid), None)
    if not op:
        return jsonify({"error": "No encontrado"}), 404
    OPERADORES.remove(op)
    guardar_json(OPERADORES_FILE, OPERADORES)
    return jsonify({"ok": True})

# ════════════════════════════════════════════════════════════
#  ACTIVIDADES (asignación de solicitudes a vehículos con horarios)
# ════════════════════════════════════════════════════════════
@app.route("/api/actividades", methods=["GET"])
@login_req
def listar_actividades():
    # Retorna actividades del día actual por defecto
    hoy = datetime.now().strftime("%d/%m/%y").split("/")
    return jsonify(ACTIVIDADES)

@app.route("/api/actividades", methods=["POST"])
@login_req
def crear_actividad():
    d = request.json
    solicitud_id = d.get("solicitud_id")
    vehiculo_id = d.get("vehiculo_id")
    operador_id = d.get("operador_id")
    hora_inicio = d.get("hora_inicio","08:00")
    hora_fin = d.get("hora_fin","09:00")
    notas = d.get("notas","")
    prioridad = d.get("prioridad","Normal")
    fecha = d.get("fecha", datetime.now().strftime("%d/%m/%y"))
    
    sol = next((s for s in SOLICITUDES if s["id"]==solicitud_id),None)
    if not sol:
        return jsonify({"error": "Solicitud no encontrada"}), 404
    veh = next((v for v in VEHICULOS if v["id"]==vehiculo_id),None)
    if not veh:
        return jsonify({"error": "Vehículo no encontrado"}), 404
    if operador_id:
        op = next((o for o in OPERADORES if o["id"]==operador_id),None)
        if not op:
            return jsonify({"error": "Operador no encontrado"}), 404
    
    act = {
        "id": new_id(),
        "solicitud_id": solicitud_id,
        "vehiculo_id": vehiculo_id,
        "operador_id": operador_id or None,
        "fecha": fecha,
        "hora_inicio": hora_inicio,
        "hora_fin": hora_fin,
        "notas": notas,
        "prioridad": prioridad,
        "estado": "Pendiente",
        "asignado_por": session["user"]["username"],
        "creado_en": now_str(),
    }
    ACTIVIDADES.append(act)
    guardar_json(ACTIVIDADES_FILE, ACTIVIDADES)
    return jsonify({"ok": True, "actividad": act})

@app.route("/api/actividades/<int:aid>", methods=["DELETE"])
@login_req
def eliminar_actividad(aid):
    a = next((x for x in ACTIVIDADES if x["id"]==aid),None)
    if not a:
        return jsonify({"error": "No encontrada"}), 404
    ACTIVIDADES.remove(a)
    guardar_json(ACTIVIDADES_FILE, ACTIVIDADES)
    return jsonify({"ok": True})

@app.route("/api/actividades/<int:aid>/horario", methods=["PATCH"])
@login_req
def cambiar_horario_actividad(aid):
    d = request.json
    a = next((x for x in ACTIVIDADES if x["id"]==aid),None)
    if not a:
        return jsonify({"error": "No encontrada"}), 404
    a["hora_inicio"] = d.get("hora_inicio", a["hora_inicio"])
    a["hora_fin"] = d.get("hora_fin", a["hora_fin"])
    guardar_json(ACTIVIDADES_FILE, ACTIVIDADES)
    return jsonify({"ok": True, "actividad": a})

@app.route("/api/actividades/<int:aid>/estado", methods=["PATCH"])
@login_req
def cambiar_estado_actividad(aid):
    d = request.json
    a = next((x for x in ACTIVIDADES if x["id"]==aid),None)
    if not a:
        return jsonify({"error": "No encontrada"}), 404
    a["estado"] = d.get("estado", a.get("estado","Pendiente"))
    guardar_json(ACTIVIDADES_FILE, ACTIVIDADES)
    return jsonify({"ok": True, "actividad": a})

@app.route("/api/actividades/<int:aid>/prioridad", methods=["PATCH"])
@login_req
def cambiar_prioridad_actividad(aid):
    d = request.json
    a = next((x for x in ACTIVIDADES if x["id"]==aid),None)
    if not a:
        return jsonify({"error": "No encontrada"}), 404
    p = d.get("prioridad","Normal")
    if p not in ("Normal","Alta","Urgente"):
        return jsonify({"error": "Prioridad inválida"}), 400
    a["prioridad"] = p
    guardar_json(ACTIVIDADES_FILE, ACTIVIDADES)
    return jsonify({"ok": True, "actividad": a})

# ════════════════════════════════════════════════════════════
#  WHATSAPP
# ════════════════════════════════════════════════════════════
def enviar_whatsapp(sol):
    phone  = WA_CONFIG.get("phone")  or WA_PHONE
    apikey = WA_CONFIG.get("apikey") or WA_APIKEY
    if not phone or not apikey: return False
    emoji = {"Urgente":"🔴","Alta":"🟠","Normal":"🟢"}.get(sol.get("prioridad","Normal"),"🟢")
    texto = (f"📋 Nueva solicitud\n"
             f"👤 {sol.get('nombre','')}\n"
             f"📁 {sol['tipo']}\n"
             f"{emoji} Prioridad: {sol['prioridad']}\n"
             f"📝 {sol['descripcion']}\n"
             f"🕐 {sol['fecha']}")
    url = (f"https://api.callmebot.com/whatsapp.php"
           f"?phone={phone}&text={requests.utils.quote(texto)}&apikey={apikey}")
    try:
        r = requests.get(url, timeout=10)
        print(f"[WA] {'OK' if r.ok else 'Error'}")
        return r.ok
    except Exception as e:
        print(f"[WA] Error: {e}"); return False

@app.route("/api/wa/config", methods=["GET"])
@role("superadmin")
def wa_get():
    return jsonify({
        "configurado": bool(WA_CONFIG.get("phone") and WA_CONFIG.get("apikey")),
        "phone":  WA_CONFIG.get("phone",""),
        "apikey": WA_CONFIG.get("apikey",""),
    })

@app.route("/api/wa/config", methods=["POST"])
@role("superadmin")
def wa_set():
    d = request.json
    WA_CONFIG["phone"]  = d.get("phone","").strip()
    WA_CONFIG["apikey"] = d.get("apikey","").strip()
    return jsonify({"ok": True})

@app.route("/api/wa/test", methods=["POST"])
@role("superadmin")
def wa_test():
    sol = {"nombre":"Sistema","tipo":"Prueba","prioridad":"Normal",
           "descripcion":"Mensaje de prueba.","fecha":now_str()}
    ok = enviar_whatsapp(sol)
    return jsonify({"ok": ok, "error": "" if ok else "No se pudo enviar"})

# ════════════════════════════════════════════════════════════
#  MAIN
# ════════════════════════════════════════════════════════════
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print("=" * 50)
    print(f"  http://localhost:{port}")
    print(f"  superadmin / super123")
    print(f"  admin1     / admin123")
    print("=" * 50)
    app.run(host="0.0.0.0", port=port, debug=True)
