import random
from datetime import datetime
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

from config import get_connection

app = Flask(__name__)
app.secret_key = "cambia-esta-clave-por-una-propia-y-segura"

EXTENSIONES_PERMITIDAS = {"txt", "py"}


def archivo_permitido(nombre_archivo):
    return "." in nombre_archivo and nombre_archivo.rsplit(".", 1)[1].lower() in EXTENSIONES_PERMITIDAS


def login_requerido(vista):
    # Evita que se acceda a rutas internas sin haber iniciado sesion
    @wraps(vista)
    def envoltura(*args, **kwargs):
        if "usuario_id" not in session:
            return redirect(url_for("login"))
        return vista(*args, **kwargs)

    return envoltura


@app.route("/")
def login():
    if "usuario_id" in session:
        return redirect(url_for("menu"))
    return render_template("login.html")


def ensure_login_attempts_table():
    """Crea la tabla LoginAttempts si no existe. Usada para no modificar el archivo database.sql."""
    conexion = get_connection()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS LoginAttempts (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    usuario_id INT NOT NULL,
                    intentos_fallidos INT NOT NULL DEFAULT 0,
                    bloqueado TINYINT(1) NOT NULL DEFAULT 0,
                    fecha_bloqueo DATETIME NULL,
                    UNIQUE KEY (usuario_id),
                    FOREIGN KEY (usuario_id) REFERENCES Usuario(id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """
            )
        conexion.commit()
    finally:
        conexion.close()


@app.route("/login", methods=["POST"])
def procesar_login():
    usuario = request.form.get("usuario", "").strip()
    contrasena = request.form.get("contrasena", "")

    # Asegurar que la tabla de intentos exista (no modificamos database.sql)
    ensure_login_attempts_table()

    conexion = get_connection()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("SELECT * FROM Usuario WHERE usuario = %s", (usuario,))
            fila = cursor.fetchone()

            if not fila:
                # Usuario no existe: respuesta genérica
                flash("Usuario o contraseña incorrectos")
                return redirect(url_for("login"))

            # Obtener/crear registro de intentos para este usuario
            cursor.execute(
                "SELECT * FROM LoginAttempts WHERE usuario_id = %s",
                (fila["id"],),
            )
            intento = cursor.fetchone()

            if intento and intento.get("bloqueado"):
                flash("Cuenta bloqueada por intentos fallidos. Contacta al administrador.")
                return redirect(url_for("login"))

            # Login exitoso: resetear/insertar intento 0
            if check_password_hash(fila["contrasena"], contrasena):
                if intento:
                    cursor.execute(
                        "UPDATE LoginAttempts SET intentos_fallidos = 0, bloqueado = 0, fecha_bloqueo = NULL WHERE usuario_id = %s",
                        (fila["id"],),
                    )
                else:
                    cursor.execute(
                        "INSERT INTO LoginAttempts (usuario_id, intentos_fallidos, bloqueado) VALUES (%s, 0, 0)",
                        (fila["id"],),
                    )
                conexion.commit()
                session["usuario_id"] = fila["id"]
                session["usuario"] = fila["usuario"]
                return redirect(url_for("menu"))

            # Contraseña incorrecta: incrementar
            nuevos_intentos = (intento["intentos_fallidos"] if intento else 0) + 1
            if intento:
                if nuevos_intentos >= 4:
                    cursor.execute(
                        "UPDATE LoginAttempts SET intentos_fallidos = %s, bloqueado = 1, fecha_bloqueo = %s WHERE usuario_id = %s",
                        (nuevos_intentos, datetime.now(), fila["id"]),
                    )
                    flash("Demasiados intentos fallidos. La cuenta ha sido bloqueada.")
                else:
                    cursor.execute(
                        "UPDATE LoginAttempts SET intentos_fallidos = %s WHERE usuario_id = %s",
                        (nuevos_intentos, fila["id"]),
                    )
                    flash(f"Usuario o contraseña incorrectos. Intentos {nuevos_intentos}/4")
            else:
                # crear fila de intentos
                bloqueado_flag = 1 if nuevos_intentos >= 4 else 0
                fecha_b = datetime.now() if bloqueado_flag else None
                cursor.execute(
                    "INSERT INTO LoginAttempts (usuario_id, intentos_fallidos, bloqueado, fecha_bloqueo) VALUES (%s, %s, %s, %s)",
                    (fila["id"], nuevos_intentos, bloqueado_flag, fecha_b),
                )
                if bloqueado_flag:
                    flash("Demasiados intentos fallidos. La cuenta ha sido bloqueada.")
                else:
                    flash(f"Usuario o contraseña incorrectos. Intentos {nuevos_intentos}/4")

            conexion.commit()
            return redirect(url_for("login"))

    finally:
        conexion.close()


@app.route("/registro", methods=["GET", "POST"])
def registro():
    if request.method == "GET":
        return render_template("registro.html")

    nombre = request.form.get("nombre", "").strip()
    edad = request.form.get("edad", "").strip()
    usuario = request.form.get("usuario", "").strip()
    contrasena = request.form.get("contrasena", "")

    if not nombre or not edad or not usuario or not contrasena:
        flash("Completa todos los campos")
        return redirect(url_for("registro"))

    conexion = get_connection()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("SELECT id FROM Usuario WHERE usuario = %s", (usuario,))
            if cursor.fetchone():
                flash("Ese nombre de usuario ya existe")
                return redirect(url_for("registro"))

            cursor.execute(
                "INSERT INTO Usuario (nombre, edad, usuario, contrasena) VALUES (%s, %s, %s, %s)",
                (nombre, edad, usuario, generate_password_hash(contrasena)),
            )
        conexion.commit()
    finally:
        conexion.close()

    flash("Cuenta creada, ahora inicia sesión")
    return redirect(url_for("login"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/menu")
@login_requerido
def menu():
    conexion = get_connection()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT u.usuario AS usuario, MAX(m.velocidad) AS mejor_velocidad
                FROM Marcador m
                JOIN Usuario u ON u.id = m.usuario_id
                GROUP BY u.id, u.usuario
                ORDER BY mejor_velocidad DESC
                LIMIT 3
                """
            )
            top_usuarios = cursor.fetchall()
    finally:
        conexion.close()

    return render_template("menu.html", usuario=session["usuario"], top_usuarios=top_usuarios)


@app.route("/personalizado", methods=["GET", "POST"])
@login_requerido
def personalizado():
    if request.method == "GET":
        return render_template("personalizado.html")

    archivo = request.files.get("archivo")
    if not archivo or archivo.filename == "" or not archivo_permitido(archivo.filename):
        flash("Sube un archivo .txt o .py válido")
        return redirect(url_for("personalizado"))

    contenido = archivo.read().decode("utf-8", errors="ignore").strip()
    if not contenido:
        flash("El archivo está vacío")
        return redirect(url_for("personalizado"))

    nombre_archivo = secure_filename(archivo.filename)

    conexion = get_connection()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                "INSERT INTO Texto (tipo, contenido) VALUES (%s, %s)",
                ("personalizado", contenido),
            )
            texto_id = cursor.lastrowid
        conexion.commit()
    finally:
        conexion.close()

    return redirect(url_for("test", tipo="personalizado", texto_id=texto_id, nombre=nombre_archivo))


@app.route("/test/<tipo>")
@login_requerido
def test(tipo):
    if tipo not in ("codigo", "plano", "personalizado"):
        return redirect(url_for("menu"))

    texto_id = request.args.get("texto_id")
    nombre_archivo = request.args.get("nombre", "")

    conexion = get_connection()
    try:
        with conexion.cursor() as cursor:
            if texto_id:
                cursor.execute("SELECT * FROM Texto WHERE id = %s", (texto_id,))
                texto = cursor.fetchone()
            else:
                cursor.execute("SELECT * FROM Texto WHERE tipo = %s", (tipo,))
                textos = cursor.fetchall()
                texto = random.choice(textos) if textos else None
    finally:
        conexion.close()

    if not texto:
        flash("No hay textos disponibles para esta opción")
        return redirect(url_for("menu"))

    titulos = {
        "codigo": "practica.py",
        "plano": "documento.txt",
        "personalizado": nombre_archivo or "personalizado.txt",
    }

    return render_template("test.html", texto=texto["contenido"], titulo=titulos[tipo])


@app.route("/guardar_resultado", methods=["POST"])
@login_requerido
def guardar_resultado():
    datos = request.get_json(silent=True) or {}
    velocidad = int(datos.get("velocidad", 0))

    conexion = get_connection()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                "INSERT INTO Marcador (usuario_id, velocidad, fecha) VALUES (%s, %s, %s)",
                (session["usuario_id"], velocidad, datetime.now()),
            )
        conexion.commit()
    finally:
        conexion.close()

    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(debug=True)
