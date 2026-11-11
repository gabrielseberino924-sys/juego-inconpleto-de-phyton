# JUJUTSU FIGHTERS  (juego de pelea hecho por fans)

Juego de pelea 2D en Python + Pygame con **30 personajes** de Jujutsu Kaisen.
**Sprites reales (de tus hojas):** Jogo, Dagon (hoja propia en alta resolución) y 16 personajes de la hoja grande
(Yuji, Megumi, Nobara, Gojo, Sukuna, Nanami, Inumaki, Maki, Panda, Yuta, Geto, Mahito, Hanami, Choso, Mai y Kenjaku).
Los otros 12 (Toji, Todo, Hakari, Higuruma, Kashimo, Naoya, Mechamaru, Yuki, Uraume, Kamo, Naobito, Utahime)
usan sprites generados por código; puedes reemplazarlos por arte tuyo cuando quieras (ver más abajo).

**Cinemática:** cuando Jogo usa su Expansión de Dominio se reproduce el video
(`assets/cinematicas/jogo_dominio/`: cuadros JPG + audio). ENTER / ESPACIO la salta. Se activa o
desactiva en el menú de inicio (CINEMÁTICAS).

## Instalar y ejecutar
```
pip install pygame
python jjk_fighter.py
```
Modos: 1 jugador (vs CPU, 3 dificultades), 2 jugadores en el mismo teclado,
entrenamiento y demo CPU vs CPU. Mejor de 3 rondas, 99 segundos.

## Controles
| Acción                         | Jugador 1 | Jugador 2          |
|--------------------------------|-----------|--------------------|
| Mover (mantener = correr)      | A / D     | Flechas izq / der  |
| Saltar / Agacharse             | W / S     | Flechas arriba / abajo |
| Ataque normal                  | F         | K (o Num 1)        |
| Ataque especial                | G         | L (o Num 2)        |
| Habilidad                      | H         | O (o Num 3)        |
| Expansión de Dominio (barra 100) | T       | I (o Num 0)        |
| Bloquear (mantener)            | R         | U (o Num 5)        |

Menús: flechas / WASD, ENTER acepta, ESC vuelve, P pausa, R = personaje aleatorio.
En la selección: **TAB** cambia el escenario. En cualquier momento: **M** activa/desactiva el sonido y **F11** pantalla completa.

- La energía maldita (barra de color) sube sola y al golpear. Los especiales cuestan energía.
- Saltar esquiva las ondas de suelo; agacharse esquiva los proyectiles altos.
- Ataque normal en el aire = **patada aérea** (una por salto).
- Los efectos de sonido se generan por código (no hay archivos de audio). Si no hay audio disponible, el juego sigue sin sonido.
- Al K.O. hay cámara lenta y el perdedor cae al suelo.
- Con la barra llena, la **Expansión de Dominio / Técnica Máxima** es un golpe cinematográfico que no se puede bloquear.

## Dagon (sprites reales, con efectos propios)
- Normal (F): **Chorro de Agua** (proyectil)  - Especial (G): **Marejada** (ola de tiburones por el suelo)
- Habilidad (H): **Tsunami** (tentáculos)  - Dominio (T): **Horizonte del Mar Capturado**, con el escenario del Acuario Sumergido
- `tools/extraer_sprites_dagon.py HOJA.png assets` recorta su hoja (cuadros, efectos, retrato y fondo del dominio).

## Jogo (sprites reales)
- Normal (F): **Bola de Fuego**  - Especial (G): **Meteoros de Magma**
- Habilidad (H): **Descarga de Magma** (onda de suelo)  - Dominio (T): **Ataúd de la Montaña de Hierro**

## Poner tus propios sprites a cualquier personaje
Crea la carpeta `assets/<id>/` (los ids están en `ROSTER` dentro de `jjk_fighter.py`:
`yuji`, `gojo`, `sukuna`, `megumi`, ...). Los PNG con fondo transparente, mirando a la **derecha**,
recortados al personaje, con estos nombres (empieza en 0):

```
idle_0.png ... walk_0.png ... run_0.png ... jump_0.png (4: sube, sube, baja, cae)
crouch_0.png (2)  attack_0.png ... special_0.png ... skill_0.png ... hit_0.png (el último = golpe fuerte/KO)
face_0.png   (retrato cuadrado para el HUD y la selección)
```
Solo `idle_0.png` es obligatorio; si falta una animación se usa `idle`.
Opcional: `meta.json` con `{"scale": 1.6}` para ajustar el tamaño y `anchors.json` con
`{"idle_0": [x_de_los_pies, alto], ...}`. Los efectos `fx_fireball.png`, `fx_meteor.png`,
`fx_explosion.png`, `fx_wave.png`, `fx_ring.png`... se usan desde los movimientos que tengan `fx='...'`.
`tools/extraer_sprites_jogo.py` es el script que recortó la hoja de Jogo (sirve de ejemplo).

## Editar / añadir personajes y movimientos
Todo está en la lista `ROSTER` de `jjk_fighter.py`. Cada personaje tiene vida, velocidad, salto, poder,
3 movimientos y un movimiento máximo. Tipos de movimiento: `melee, multi, dash, teleport, proj, orb, stun, slash,
beam, wave, meteor, heal, buff` (parámetros por defecto en el diccionario `DEF`).



## Hojas de sprites generadas
`tools/generar_hojas.py` dibuja a los 29 personajes (todos menos Jogo) con contorno, sombreado y
detalles de vestuario, crea una hoja PNG por personaje (`hojas_de_sprites/hoja_<id>.png`, con el mismo
formato que la hoja de Jogo) y exporta los cuadros sueltos a `assets/<id>/`.
```
pip install pillow
python tools/generar_hojas.py              # todos
python tools/generar_hojas.py gojo sukuna  # solo esos
```
Para usar arte propio: sobrescribe los PNG de `assets/<id>/` (o bórralos y pon los tuyos). Si quitas
`"ko_lying": true` de `meta.json`, el personaje ya no se tumba rotado al caer en el K.O.


## Importar sprites desde una hoja
`tools/importar_hoja.py` recorta la hoja de 18 paneles (cuerpos por animación, retrato y cara) a
`assets/<id>/` y amplía los sprites conservando el aspecto de pixel art.
```
pip install pillow numpy scipy
python tools/importar_hoja.py RUTA/Hoja_de_sprites.png            # todos
python tools/importar_hoja.py RUTA/Hoja_de_sprites.png yuji gojo   # solo esos
```
Los sprites de la hoja son muy pequeños (unos 30 px de alto, y menos en la fila de abajo), por eso se ven
pixelados al ampliarlos. Con una hoja de mayor resolución el resultado mejora sin tocar el código.

## Cinemática propia
Para otra cinemática: carpeta `assets/cinematicas/<nombre>/` con `f_0001.jpg`, `f_0002.jpg`...,
`audio.wav` e `info.json` (`{"fps": 30, "frames": N}`), y en `ROSTER` pon `cine='<nombre>'` en la
técnica máxima del personaje (`U(..., cine='<nombre>')`). Con ffmpeg:
```
ffmpeg -i video.mp4 -vf fps=30 -q:v 5 f_%04d.jpg
ffmpeg -i video.mp4 -vn -ac 1 -ar 22050 -c:a pcm_s16le audio.wav
```

*Proyecto de fans sin fines de lucro. Jujutsu Kaisen y sus personajes pertenecen a sus creadores.*

## Subir la calidad de los sprites (hojas de alta resolución)
La calidad de un sprite depende de la resolución de la hoja original: los cuadros de Jogo medían ~116 px de
alto, pero los de la hoja de 18 paneles solo ~30 px, y ninguna ampliación automática puede inventar ese detalle.
Para que cualquier personaje se vea como Jogo, genera **una hoja por personaje** con el mismo formato que la de
18 paneles (título, retrato a la izquierda, filas IDLE / CAMINANDO / CORRIENDO / SALTANDO / AGACHADO /
ATAQUE NORMAL / ATAQUE ESPECIAL / HABILIDAD / DAÑO-IMPACTO, EXPRESIONES y PALETA), a la máxima resolución que
permita tu generador (idealmente cada cuadro de ~100 px de alto o más), fondo blanco y personaje mirando a la derecha.
Luego impórtala:
```
python tools/importar_hoja.py hoja_gojo.png --individual gojo
```
Las hojas de mayor resolución se amplían con suavizado en vez de pixel art, y el recorte se adapta solo al tamaño.
