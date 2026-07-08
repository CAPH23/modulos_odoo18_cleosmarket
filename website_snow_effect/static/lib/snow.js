document.addEventListener("DOMContentLoaded", function () {
    // === AUDIO CONFIGURACIÓN PERSISTENTE ===
    let isPlaying = localStorage.getItem("music_playing") === "true";

    // === AUDIO ALEATORIO CON PERSISTENCIA ===
    let selectedTrack = localStorage.getItem("snow_music_track");

    // Si no hay canción guardada, selecciona una aleatoria
    if (!selectedTrack) {
        const musicFiles = [
            'the_first_noel.mp3',
            'we-wish-you-a-merry-christmas.mp3',
            'christmas-dreams-jingle-bells-268299.mp3',
            'deck-the-halls-271319.mp3',
            // Agrega aquí todos los archivos que tienes en la carpeta /music/
        ];
        selectedTrack = musicFiles[Math.floor(Math.random() * musicFiles.length)];
        localStorage.setItem("snow_music_track", selectedTrack);
    }

    const audio = document.createElement("audio");
    audio.src = `/website_snow_effect/static/lib/music/${selectedTrack}`;
    audio.loop = true;
    audio.volume = 0.3;
    document.body.appendChild(audio);

    // Restaurar tiempo de reproducción si existe
    const savedTime = sessionStorage.getItem("snow_music_time");
    if (savedTime) {
        audio.currentTime = parseFloat(savedTime);
    }

    if (isPlaying) {
        audio.play().catch(() => {});
    }

    // Guardar tiempo de reproducción antes de salir de la página
    window.addEventListener("beforeunload", () => {
        sessionStorage.setItem("snow_music_time", audio.currentTime);
    });

    // === EFECTO DE NIEVE ===
    const snowflake = document.createElement('div');
    snowflake.innerHTML = '❄';
    snowflake.style.position = 'fixed';
    snowflake.style.color = '#00FFFF';
    snowflake.style.fontSize = '1.5em';
    snowflake.style.zIndex = '9999';

    function createSnowflake() {
        const clone = snowflake.cloneNode(true);
        clone.style.left = Math.random() * window.innerWidth + 'px';
        clone.style.top = '-2em';
        document.body.appendChild(clone);

        let fall = setInterval(() => {
            const top = parseFloat(clone.style.top);
            if (top > window.innerHeight) {
                clone.remove();
                clearInterval(fall);
            } else {
                clone.style.top = top + 2 + 'px';
            }
        }, 30);
    }
    setInterval(createSnowflake, 500);

    // === EMOJIS NAVIDEÑOS DECORATIVOS ===
    const emojis = ['🎅', '🤶', '🧑‍🎄', '🎄', '🎁', '🧦', '🕯️', '🔔', '🛷', '🦌', '⛄', '☃️', '❄️', '🌟', '✨', '🪅', '🍪', '🥛', '🍬', '🍭', '🍫', '🧃', '🌨️', '🎶', '🛍️'];

    function getRandomEmoji(exclude = null) {
        let emoji;
        do {
            emoji = emojis[Math.floor(Math.random() * emojis.length)];
        } while (emoji === exclude);
        return emoji;
    }

    const emoji1 = getRandomEmoji();
    const emoji2 = getRandomEmoji();

    // Crear y animar el primer emoji
    const figure1 = document.createElement('div');
    figure1.innerHTML = emoji1;
    figure1.style.position = 'fixed';
    figure1.style.left = '10px';
    figure1.style.bottom = '-200px';
    figure1.style.fontSize = '6em';
    figure1.style.zIndex = '9999';
    figure1.style.transition = 'bottom 2s ease-out, transform 1s linear';
    figure1.style.transform = 'rotate(0deg)';
    figure1.style.willChange = 'transform';
    document.body.appendChild(figure1);

    let angle1 = 0;
    let rotating1 = true;
    const rotationInterval1 = setInterval(() => {
        if (rotating1) {
            angle1 += 10;
            figure1.style.transform = `rotate(${angle1}deg)`;
        }
    }, 50);

    // Iniciar movimiento del primer emoji
    setTimeout(() => {
        figure1.style.bottom = '20px';
    }, 100);


    // Detener rotación y comenzar el segundo emoji
    setTimeout(() => {
        rotating1 = false;
        figure1.style.transform = 'rotate(0deg)';

        // === FIGURE 2 ===
        const figure2 = document.createElement('div');
        figure2.innerHTML = emoji2;
        figure2.style.position = 'fixed';
        figure2.style.left = '80px';
        figure2.style.bottom = '-200px';
        figure2.style.fontSize = '6em';
        figure2.style.zIndex = '9999';
        figure2.style.transition = 'bottom 2s ease-out, transform 1s linear';
        figure2.style.transform = 'rotate(0deg)';
        figure2.style.willChange = 'transform';
        document.body.appendChild(figure2);

        let angle2 = 0;
        let rotating2 = true;
        const rotationInterval2 = setInterval(() => {
            if (rotating2) {
                angle2 += 10;
                figure2.style.transform = `rotate(${angle2}deg)`;
            }
        }, 50);

        // Subida del segundo emoji
        setTimeout(() => {
            figure2.style.bottom = '20px';
        }, 100);

        // Detener rotación
        setTimeout(() => {
            rotating2 = false;
            figure2.style.transform = 'rotate(0deg)';

            // Movimiento oscilatorio después de que figure2 esté posicionado
            let direction = 1;
            setInterval(() => {
                figure1.style.transform = `translateY(${direction * 20}px)`;
                figure2.style.transform = `translateY(${direction * 20}px)`;
                direction *= -1;
            }, 1000);
        }, 2200); // después de 2.2s de haber iniciado figure2

    }, 2200); // después de 2.2s de figure1


    // === BOTÓN DE MÚSICA ===
    const musicButton = document.createElement("button");
    musicButton.innerHTML = isPlaying ? '🔊' : '🔇';
    musicButton.title = isPlaying ? 'Pausar música' : 'Reanudar música';
    musicButton.style.position = 'fixed';
    musicButton.style.bottom = 'calc(3%)';
    musicButton.style.right = 'calc(5% + 50px)';
    musicButton.style.fontSize = '1.65em';
    musicButton.style.zIndex = '9999';
    musicButton.style.border = 'none';
    musicButton.style.background = 'rgba(255, 255, 255, 0.7)';
    musicButton.style.borderRadius = '50%';
    musicButton.style.padding = '0.3em 0.4em';
    musicButton.style.cursor = 'pointer';
    musicButton.style.boxShadow = '0 0 10px rgba(0,0,0,0.3)';
    musicButton.style.transition = 'transform 1s ease-in-out';
    document.body.appendChild(musicButton);

    function toggleAudio() {
        if (audio.paused) {
            audio.play().catch(() => {});
            musicButton.innerHTML = '🔊';
            musicButton.title = 'Pausar música';
            isPlaying = true;
        } else {
            audio.pause();
            musicButton.innerHTML = '🔇';
            musicButton.title = 'Reanudar música';
            isPlaying = false;
        }
        localStorage.setItem("music_playing", isPlaying);
    }

    musicButton.addEventListener('click', toggleAudio);

    // === ACTIVAR MÚSICA SI YA ESTABA ENCENDIDA CON CLIC DEL USUARIO ===
    document.addEventListener('click', function startMusic() {
        if (isPlaying && audio.paused) {
            audio.play().catch(() => {});
        }
        document.removeEventListener('click', startMusic);
    });
});
