const datosTexto = JSON.parse(document.getElementById("texto-datos").textContent);
const oraciones = dividirEnOraciones(datosTexto);
const palabrasTotales = oraciones.flatMap((oracion) => oracion.split(/\s+/).filter(Boolean));

const contenedorTexto = document.getElementById("texto-prueba");
const entrada = document.getElementById("entrada-usuario");
const marcadorTiempo = document.getElementById("tiempo-restante");
const barraProgreso = document.getElementById("barra-progreso");
const pantallaResultado = document.getElementById("pantalla-resultado");
const valorWpm = document.getElementById("valor-wpm");
const imagenResultado = document.getElementById("imagen-resultado");
const indicadorRacha = document.getElementById("indicador-racha");
const contadorRacha = document.getElementById("contador-racha");

const DURACION_SEGUNDOS = 60;
const UMBRAL_RACHA = 4;

let indiceActual = 0;
let indiceOracionActual = 0;
let palabras = [];
let palabrasCorrectas = 0;
let palabrasProcesadas = 0;
let tiempoRestante = DURACION_SEGUNDOS;
let intervalo = null;
let pruebaIniciada = false;
let pruebaTerminada = false;
let palabrasCorrectasConsecutivas = 0;

function dividirEnOraciones(texto) {
    const partes = texto
        .split(/(?<=[.!?])\s+/)
        .map((oracion) => oracion.trim())
        .filter(Boolean);

    return partes.length > 0 ? partes : [texto.trim()].filter(Boolean);
}

function obtenerPalabrasActuales() {
    return oraciones[indiceOracionActual]?.split(/\s+/).filter(Boolean) || [];
}

function actualizarBarraProgreso() {
    const porcentaje = palabrasTotales.length > 0 ? (palabrasProcesadas / palabrasTotales.length) * 100 : 0;
    barraProgreso.style.width = `${Math.min(100, porcentaje)}%`;
}

function dibujarTexto() {
    palabras = obtenerPalabrasActuales();
    contenedorTexto.innerHTML = palabras
        .map((palabra, indice) => {
            const letras = palabra
                .split("")
                .map((letra) => `<span class="letra">${letra}</span>`)
                .join("");
            return `<span class="palabra" data-indice="${indice}">${letras}</span>`;
        })
        .join(" ");
    marcarPalabraActual();
}

function marcarPalabraActual() {
    document.querySelectorAll(".palabra").forEach((elemento) => elemento.classList.remove("actual"));
    const elementoActual = document.querySelector(`.palabra[data-indice="${indiceActual}"]`);
    if (elementoActual) {
        elementoActual.classList.add("actual");
    }
}

// Colorea letra por letra la palabra que se esta escribiendo en este momento
function actualizarLetrasPalabraActual() {
    const elementoActual = document.querySelector(`.palabra[data-indice="${indiceActual}"]`);
    if (!elementoActual) {
        return;
    }

    const palabraObjetivo = palabras[indiceActual];
    const letras = elementoActual.querySelectorAll(".letra");
    const escrito = entrada.value;

    letras.forEach((letraElemento, indice) => {
        letraElemento.classList.remove("correcta", "incorrecta", "cursor");
        if (indice < escrito.length) {
            letraElemento.classList.add(escrito[indice] === palabraObjetivo[indice] ? "correcta" : "incorrecta");
        } else if (indice === escrito.length) {
            letraElemento.classList.add("cursor");
        }
    });
}

function iniciarCuentaRegresiva() {
    intervalo = setInterval(() => {
        tiempoRestante -= 1;
        marcadorTiempo.textContent = tiempoRestante;
        if (tiempoRestante <= 0) {
            finalizarPrueba();
        }
    }, 1000);
}

function mostrarImagenResultado(palabrasPorMinuto) {
    let src = imagenResultado.dataset.liebre;
    let etiqueta = "Liebre";

    if (palabrasPorMinuto < 30) {
        src = imagenResultado.dataset.caracol;
        etiqueta = "Caracol";
    } else if (palabrasPorMinuto > 60) {
        src = imagenResultado.dataset.chita;
        etiqueta = "Chita";
    }

    imagenResultado.src = src;
    imagenResultado.alt = etiqueta;
    imagenResultado.hidden = false;
}

function finalizarPrueba() {
    if (pruebaTerminada) {
        return;
    }
    pruebaTerminada = true;

    clearInterval(intervalo);
    entrada.disabled = true;

    const segundosUsados = DURACION_SEGUNDOS - tiempoRestante;
    const minutos = segundosUsados > 0 ? segundosUsados / 60 : 1 / 60;
    const palabrasPorMinuto = Math.round(palabrasCorrectas / minutos);

    valorWpm.textContent = palabrasPorMinuto;
    mostrarImagenResultado(palabrasPorMinuto);
    pantallaResultado.classList.add("visible");

    fetch("/guardar_resultado", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ velocidad: palabrasPorMinuto }),
    });
}

function mostrarRacha() {
    indicadorRacha.classList.add("activo");
    contadorRacha.textContent = palabrasCorrectasConsecutivas;
}

function ocultarRacha() {
    indicadorRacha.classList.remove("activo");
    palabrasCorrectasConsecutivas = 0;
}

function avanzarOracion() {
    indiceActual = 0;
    indiceOracionActual += 1;
    entrada.value = "";
    ocultarRacha();

    if (indiceOracionActual >= oraciones.length) {
        finalizarPrueba();
        return;
    }

    dibujarTexto();
    actualizarBarraProgreso();
}

// Se ejecuta cuando el usuario confirma una palabra con espacio o enter
function procesarPalabra() {
    const escrita = entrada.value.trim();
    const elementoActual = document.querySelector(`.palabra[data-indice="${indiceActual}"]`);
    const palabraObjetivo = palabras[indiceActual];

    if (elementoActual) {
        const letras = elementoActual.querySelectorAll(".letra");
        letras.forEach((letraElemento, indice) => {
            letraElemento.classList.remove("cursor");
            const correcta = indice < escrita.length && escrita[indice] === palabraObjetivo[indice];
            letraElemento.classList.toggle("correcta", correcta);
            letraElemento.classList.toggle("incorrecta", !correcta);
        });

        const esCorrecta = escrita === palabraObjetivo;
        elementoActual.classList.toggle("correcta", esCorrecta);
        elementoActual.classList.toggle("incorrecta", !esCorrecta);

        if (esCorrecta && !elementoActual.dataset.contada) {
            palabrasCorrectas += 1;
            elementoActual.dataset.contada = "1";
            palabrasCorrectasConsecutivas += 1;

            if (palabrasCorrectasConsecutivas >= UMBRAL_RACHA) {
                mostrarRacha();
            }
        } else if (!esCorrecta) {
            ocultarRacha();
        }
    }

    indiceActual += 1;
    palabrasProcesadas += 1;
    entrada.value = "";
    actualizarBarraProgreso();

    if (indiceActual >= palabras.length) {
        avanzarOracion();
        return;
    }

    marcarPalabraActual();
}

// Permite volver a la palabra anterior si quedo marcada como incorrecta
function retrocederPalabra() {
    const palabraAnterior = document.querySelector(`.palabra[data-indice="${indiceActual - 1}"]`);
    if (!palabraAnterior || !palabraAnterior.classList.contains("incorrecta")) {
        return;
    }

    indiceActual -= 1;
    palabraAnterior.classList.remove("correcta", "incorrecta");
    palabraAnterior.querySelectorAll(".letra").forEach((letra) => {
        letra.classList.remove("correcta", "incorrecta", "cursor");
    });

    ocultarRacha();
    actualizarBarraProgreso();
    marcarPalabraActual();
}

entrada.addEventListener("input", (evento) => {
    if (pruebaTerminada) {
        return;
    }

    if (!pruebaIniciada) {
        pruebaIniciada = true;
        iniciarCuentaRegresiva();
    }

    if (evento.target.value.endsWith(" ")) {
        procesarPalabra();
        return;
    }

    actualizarLetrasPalabraActual();
});

entrada.addEventListener("keydown", (evento) => {
    if (pruebaTerminada) {
        return;
    }

    if (evento.key === "Enter") {
        evento.preventDefault();
        if (entrada.value.trim().length > 0) {
            entrada.value += " ";
            entrada.dispatchEvent(new Event("input"));
        }
        return;
    }

    if (evento.key === "Backspace" && entrada.value.length === 0 && indiceActual > 0) {
        evento.preventDefault();
        retrocederPalabra();
    }
});

dibujarTexto();
actualizarBarraProgreso();
entrada.focus();
