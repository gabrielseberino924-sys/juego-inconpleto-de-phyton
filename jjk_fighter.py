#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
====================================================================
  JUJUTSU FIGHTERS  -  juego de pelea hecho por fans (Python + Pygame)
====================================================================
  Instalar :  pip install pygame
  Ejecutar :  python jjk_fighter.py

  - 30 personajes de Jujutsu Kaisen.
  - Jogo usa los sprites reales de la hoja (carpeta assets/jogo).
  - Los demas personajes usan sprites generados por codigo, pero si
    pones tus propios sprites en assets/<id>/ el juego los usa solo
    (mira el README.md para los nombres de archivo).
====================================================================
"""
import os
import sys
import array
import json
import math
import random

import pygame

# ------------------------------------------------------------------ CONSTANTES
W, H, FPS = 1280, 720, 60
GROUND = 628
GRAVITY = 0.85
ARENA_L, ARENA_R = 70, W - 70
STAND_H = 190                      # altura visual de un luchador (px)
HURT_W, HURT_H, HURT_CROUCH = 72, 172, 100
CW, CH = 190, 216                  # lienzo de los sprites generados por codigo
BASE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(BASE, 'assets')
SK = (240, 208, 178)
ANIMS = ('idle', 'walk', 'run', 'jump', 'crouch', 'attack', 'special', 'skill', 'hit')


# ------------------------------------------------------------------ UTILIDADES
def clamp(v, a, b):
    return a if v < a else b if v > b else v


def mix(c1, c2, t):
    t = clamp(t, 0.0, 1.0)
    return (int(c1[0] + (c2[0] - c1[0]) * t), int(c1[1] + (c2[1] - c1[1]) * t),
            int(c1[2] + (c2[2] - c1[2]) * t))


def dark(c, f=0.5):
    return (int(c[0] * f), int(c[1] * f), int(c[2] * f))


def light(c, f=0.5):
    return (int(c[0] + (255 - c[0]) * f), int(c[1] + (255 - c[1]) * f), int(c[2] + (255 - c[2]) * f))


def overlap(a, b):
    """Interseccion de dos rectangulos (x, y, w, h)."""
    return a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]


_FONTS = {}


def font(size):
    f = _FONTS.get(size)
    if f is None:
        f = _FONTS[size] = pygame.font.Font(None, size)
    return f


def text(surf, s, size, color, pos, anchor='topleft', shadow=(0, 0, 0), off=2):
    f = font(size)
    img = f.render(s, True, color)
    w, h = img.get_size()
    x, y = pos
    if anchor == 'center':
        x -= w // 2
        y -= h // 2
    elif anchor == 'midtop':
        x -= w // 2
    elif anchor == 'topright':
        x -= w
    elif anchor == 'midleft':
        y -= h // 2
    if shadow:
        surf.blit(f.render(s, True, shadow), (int(x + off), int(y + off)))
    surf.blit(img, (int(x), int(y)))
    return w


def slant_poly(x, y, w, h, sl, left=True):
    """Paralelogramo para barras inclinadas (P1 '/', P2 espejo)."""
    if left:
        return [(x + sl, y), (x + w + sl, y), (x + w, y + h), (x, y + h)]
    return [(x, y), (x + w, y), (x + w - sl, y + h), (x - sl, y + h)]


_BIG = {}


def big_portrait(cid, height=600, maxw=640):
    """Arte grande del personaje (assets/<id>/portrait_big.png) o None."""
    key = (cid, height, maxw)
    if key not in _BIG:
        p = os.path.join(ASSETS, cid, 'portrait_big.png')
        img = None
        if os.path.isfile(p):
            try:
                im = _png(p)
                k = min(height / float(im.get_height()), maxw / float(im.get_width()))
                img = pygame.transform.smoothscale(im, (max(1, int(im.get_width() * k)), max(1, int(im.get_height() * k))))
            except Exception:
                img = None
        _BIG[key] = img
    return _BIG[key]


_GLOW = {}


def glow(surf, x, y, r, color, k=1.0):
    """Resplandor radial (cacheado). k = intensidad 0..1"""
    r = max(8, int(r) // 4 * 4)
    key = (color, r, k)
    g = _GLOW.get(key)
    if g is None:
        g = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
        steps = max(6, r // 3)
        for i in range(steps, 0, -1):
            rr = int(r * i / steps)
            a = int((215 * (1 - i / steps) ** 1.6 + 10) * k)
            pygame.draw.circle(g, (color[0], color[1], color[2], min(255, a)), (r, r), rr)
        _GLOW[key] = g
    surf.blit(g, (int(x - r), int(y - r)))


# ------------------------------------------------------------------ MOVIMIENTOS Y PERSONAJES
PROJ_KINDS = ('proj', 'orb', 'stun', 'slash')
RANGED = ('proj', 'orb', 'stun', 'slash', 'beam', 'wave', 'meteor')

DEF = {
    'melee': dict(startup=6, active=5, recovery=15, range=95, hh=105, knock=7, stun=18, launch=0, anim='attack'),
    'multi': dict(startup=8, active=48, recovery=18, range=100, hh=105, knock=3, stun=10, launch=9, every=6, anim='attack'),
    'dash': dict(startup=8, active=14, recovery=18, range=90, hh=105, knock=9, stun=22, launch=0, speed=15, anim='special'),
    'teleport': dict(startup=14, active=6, recovery=20, range=110, hh=105, knock=9, stun=22, launch=8, anim='attack'),
    'proj': dict(startup=10, active=1, recovery=18, speed=13, size=28, life=90, knock=8, stun=20, launch=0,
                 anim='attack', y=125, pierce=False),
    'orb': dict(startup=14, active=1, recovery=26, speed=5, size=36, life=110, knock=6, stun=24, launch=0,
                anim='attack', y=125, pull=1.8, pullr=330),
    'stun': dict(startup=12, active=1, recovery=24, speed=15, size=28, life=70, knock=1, stun=75, launch=0,
                 anim='attack', y=125),
    'slash': dict(startup=12, active=1, recovery=22, speed=17, size=64, life=60, knock=9, stun=24, launch=0,
                  anim='attack', y=110, pierce=True),
    'beam': dict(startup=24, active=22, recovery=28, range=700, th=64, ticks=4, knock=6, stun=14, launch=0,
                 anim='special', y=120),
    'wave': dict(startup=20, active=1, recovery=32, range=640, speed=14, hh=90, knock=6, stun=30, launch=11,
                 anim='skill'),
    'meteor': dict(startup=30, active=1, recovery=36, count=5, blast=110, knock=9, stun=26, launch=11, anim='special'),
    'heal': dict(startup=18, active=1, recovery=30, anim='skill'),
    'buff': dict(startup=16, active=1, recovery=24, anim='skill'),
}


def M(kind, name, dmg, cost=0, color=(255, 255, 255), **kw):
    d = dict(DEF[kind])
    d.update(kw)
    d.update(kind=kind, name=name, dmg=dmg, cost=cost, color=color)
    return d


def U(name, color, ticks, dmg, dom=False, cine=None):
    return dict(name=name, color=color, ticks=ticks, dmg=dmg, dom=dom, cine=cine)


def C(cid, name, short, hp, spd, jmp, pw, style, normal, special, skill, ult):
    hair, hs, outfit, accent, acc = style[:5]
    ex = style[5] if len(style) > 5 else {}
    st = dict(skin=ex.get('skin', SK), hair=hair, hs=hs, outfit=outfit, accent=accent, acc=acc,
              pants=ex.get('pants', dark(outfit, 0.55)), wide=ex.get('wide', 1.0))
    return dict(id=cid, name=name, short=short, hp=hp, spd=spd, jmp=jmp, pw=pw, style=st,
                moves=dict(normal=normal, special=special, skill=skill), ult=ult)


ROSTER = [
    C('yuji', 'Yuji Itadori', 'Yuji', 1000, 5.4, 17.5, 1.0,
      ((235, 135, 160), 'spiky', (40, 40, 70), (200, 50, 70), 'none'),
      M('melee', 'Puño Divergente', 34),
      M('dash', 'Black Flash', 95, 25, (220, 30, 70), speed=19, launch=11),
      M('multi', 'Ráfaga de Golpes', 13, 30, (255, 170, 70)),
      U('Black Flash: Zona', (220, 30, 70), 7, 36)),
    C('megumi', 'Megumi Fushiguro', 'Megumi', 920, 5.2, 17.5, 1.0,
      ((35, 35, 55), 'spiky', (35, 38, 64), (90, 110, 180), 'none'),
      M('melee', 'Golpe de Sombra', 32),
      M('proj', 'Perros Divinos', 58, 20, (70, 70, 130), speed=17, size=44, pierce=True, life=70),
      M('meteor', 'Nue: Tormenta de Rayos', 44, 35, (250, 240, 120), count=4, blast=95),
      U('Jardín de Sombras Quimera', (30, 25, 80), 6, 44, True)),
    C('nobara', 'Nobara Kugisaki', 'Nobara', 900, 5.3, 17.5, 1.0,
      ((225, 130, 50), 'short', (55, 55, 66), (210, 160, 60), 'none'),
      M('melee', 'Martillazo', 36, range=105),
      M('proj', 'Clavo Resonante', 52, 20, (210, 210, 230), speed=22, size=20),
      M('beam', 'Resonancia', 100, 40, (255, 120, 170), th=44, range=520),
      U('Resonancia Total', (255, 100, 160), 5, 55)),
    C('gojo', 'Satoru Gojo', 'Gojo', 1000, 5.6, 18, 1.0,
      ((245, 245, 252), 'spiky', (28, 28, 50), (80, 130, 230), 'blindfold'),
      M('orb', 'Azul', 38, 0, (70, 150, 255), speed=6),
      M('proj', 'Rojo', 85, 25, (255, 60, 60), speed=14, size=48, knock=18, launch=12),
      M('beam', 'Púrpura Hueco', 190, 55, (200, 90, 255), th=120, range=950, ticks=3),
      U('Vacío Infinito', (150, 210, 255), 5, 60, True)),
    C('sukuna', 'Ryomen Sukuna', 'Sukuna', 1100, 5.4, 17.5, 1.15,
      ((240, 150, 170), 'spiky', (238, 234, 226), (190, 40, 50), 'marks', {'pants': (80, 40, 50)}),
      M('melee', 'Desmantelar', 38, range=112),
      M('slash', 'Corte', 60, 20, (255, 80, 80)),
      M('proj', 'Fuga: Flecha de Fuego', 120, 40, (255, 140, 30), speed=16, size=54, launch=12),
      U('Santuario Malévolo', (190, 10, 25), 8, 40, True)),
    C('nanami', 'Kento Nanami', 'Nanami', 1000, 4.9, 17, 1.05,
      ((230, 200, 120), 'short', (70, 78, 108), (230, 200, 60), 'glasses'),
      M('melee', 'Golpe de Mazo', 40, range=108),
      M('melee', 'Corte 7:3', 80, 20, (240, 210, 90), crit=0.3, startup=8, range=115),
      M('buff', 'Horas Extra', 0, 25, (240, 210, 90)),
      U('Ratio: Corte Total', (240, 210, 90), 3, 90)),
    C('inumaki', 'Toge Inumaki', 'Inumaki', 850, 5.5, 17.5, 0.95,
      ((228, 228, 238), 'short', (30, 42, 66), (205, 205, 215), 'mask'),
      M('melee', 'Golpe Veloz', 30, startup=5),
      M('stun', '¡No te muevas!', 20, 20, (255, 225, 90)),
      M('beam', '¡Explota!', 90, 35, (255, 235, 130), th=84, range=540),
      U('Palabra Maldita: ¡Aplástate!', (255, 240, 150), 4, 70)),
    C('maki', 'Maki Zenin', 'Maki', 950, 6.1, 18, 1.0,
      ((60, 95, 70), 'bun', (52, 92, 72), (235, 235, 235), 'scar'),
      M('melee', 'Lanza', 36, range=135),
      M('dash', 'Estocada Maldita', 75, 18, (160, 235, 170), speed=19, range=130),
      M('multi', 'Danza de Lanzas', 11, 28, (160, 235, 170), range=135),
      U('Tormenta de Armas Malditas', (120, 225, 150), 6, 46)),
    C('panda', 'Panda', 'Panda', 1200, 4.2, 16.5, 1.1,
      ((28, 28, 28), 'ears', (236, 236, 236), (40, 40, 40), 'none',
       {'skin': (244, 244, 244), 'wide': 1.25, 'pants': (50, 50, 50)}),
      M('melee', 'Puño de Gorila', 44),
      M('wave', 'Pisotón', 70, 22, (210, 210, 210), range=480),
      M('buff', 'Modo Gorila', 0, 25, (230, 230, 230)),
      U('Tambor Resonante', (225, 225, 225), 5, 55)),
    C('yuta', 'Yuta Okkotsu', 'Yuta', 1000, 5.4, 17.5, 1.05,
      ((28, 28, 38), 'short', (240, 240, 246), (60, 60, 100), 'none', {'pants': (200, 200, 215)}),
      M('melee', 'Katana', 40, 0, (200, 220, 255), range=132),
      M('slash', 'Corte de Rika', 75, 22, (190, 210, 255)),
      M('beam', 'Rayo de Rika', 130, 40, (150, 255, 255), th=90),
      U('Amor Verdadero Mutuo', (255, 150, 220), 8, 40, True)),
    C('toji', 'Toji Fushiguro', 'Toji', 1000, 6.5, 18.5, 1.05,
      ((22, 22, 28), 'short', (44, 54, 64), (225, 225, 225), 'scar'),
      M('melee', 'Cuchilla', 38, range=112),
      M('dash', 'Embestida', 85, 20, (210, 210, 220), speed=21),
      M('multi', 'Cortes Veloces', 12, 28, (210, 210, 220), every=5),
      U('Cadena de Mil Millas', (195, 195, 210), 5, 62)),
    C('geto', 'Suguru Geto', 'Geto', 950, 5.0, 17, 1.0,
      ((26, 26, 32), 'bun', (30, 30, 48), (235, 235, 235), 'none'),
      M('melee', 'Golpe de Maldición', 34),
      M('proj', 'Dragón Maldito', 70, 22, (130, 70, 180), speed=14, size=62, pierce=True, life=80),
      M('meteor', 'Horda de Maldiciones', 40, 35, (120, 55, 170), count=6),
      U('Desfile de los Cien Demonios', (90, 35, 140), 6, 46, True)),
    C('mahito', 'Mahito', 'Mahito', 900, 5.7, 18, 1.0,
      ((115, 145, 205), 'short', (72, 92, 132), (95, 65, 135), 'stitches', {'skin': (205, 205, 225)}),
      M('melee', 'Zarpazo', 34),
      M('proj', 'Cuerpo Retorcido', 55, 20, (155, 105, 225), speed=15, size=36),
      M('heal', 'Reparación Corporal', 120, 35, (120, 230, 150)),
      U('Autoencarnación de la Perfección', (110, 150, 235), 7, 42, True)),
    C('jogo', 'Jogo', 'Jogo', 950, 5.0, 17, 1.1,
      ((130, 75, 45), 'volcano', (205, 200, 70), (60, 60, 70), 'eye1', {'skin': (170, 180, 205)}),
      M('proj', 'Bola de Fuego', 40, 0, (255, 140, 30), fx='fireball', speed=14, size=32),
      M('meteor', 'Meteoros de Magma', 48, 25, (255, 110, 30), fx='meteor', count=5, startup=36, blast=115),
      M('wave', 'Descarga de Magma', 80, 35, (255, 140, 30), fx='wave', startup=30, range=680),
      U('Ataúd de la Montaña de Hierro', (255, 90, 20), 8, 42, True, cine='jogo_dominio')),
    C('hanami', 'Hanami', 'Hanami', 1050, 4.1, 16.5, 1.05,
      ((140, 195, 110), 'long', (118, 80, 56), (120, 205, 100), 'none', {'skin': (205, 175, 150), 'wide': 1.1}),
      M('melee', 'Raíz Golpeadora', 36),
      M('wave', 'Raíces del Bosque', 70, 22, (110, 195, 90)),
      M('heal', 'Fotosíntesis', 110, 35, (130, 230, 120)),
      U('Flor del Bosque', (255, 150, 185), 6, 46)),
    C('dagon', 'Dagon', 'Dagon', 1000, 5.0, 17, 1.0,
      ((45, 75, 115), 'short', (205, 185, 125), (60, 140, 190), 'none', {'skin': (125, 175, 205)}),
      M('proj', 'Chorro de Agua', 34, 0, (90, 170, 255), fx='water', speed=15, size=32),
      M('wave', 'Marejada', 70, 22, (80, 160, 255), fx='wave', range=660),
      M('beam', 'Tsunami', 120, 40, (60, 130, 255), th=110),
      U('Horizonte del Mar Capturado', (40, 120, 215), 7, 42, True)),
    C('choso', 'Choso', 'Choso', 1000, 5.3, 17.5, 1.0,
      ((40, 30, 32), 'long', (150, 130, 112), (175, 40, 50), 'stitches'),
      M('proj', 'Sangre Perforante', 36, 0, (205, 30, 45), speed=23, size=20),
      M('beam', 'Perforación de Sangre', 110, 30, (225, 35, 55), th=36, range=850),
      M('slash', 'Sangre Convergente', 80, 28, (200, 20, 35), size=72),
      U('Supernova de Sangre', (235, 40, 55), 5, 62)),
    C('todo', 'Aoi Todo', 'Todo', 1100, 5.0, 17, 1.1,
      ((42, 32, 26), 'short', (62, 62, 72), (185, 45, 45), 'scar', {'wide': 1.2}),
      M('melee', 'Palmada Boogie Woogie', 42),
      M('teleport', 'Boogie Woogie', 80, 20, (255, 210, 130)),
      M('multi', 'Lluvia de Golpes', 12, 30, (255, 210, 130)),
      U('Boogie Woogie: Tormenta', (255, 205, 120), 8, 38)),
    C('mai', 'Mai Zenin', 'Mai', 800, 5.6, 18, 0.95,
      ((115, 75, 55), 'long', (86, 54, 54), (215, 185, 165), 'none'),
      M('proj', 'Bala Maldita', 28, 0, (255, 205, 125), speed=24, size=16, startup=8),
      M('proj', 'Ráfaga', 24, 20, (255, 205, 125), speed=24, size=16, burst=4, gap=6, recovery=26),
      M('beam', 'Disparo Final', 130, 38, (255, 225, 160), th=40, range=950),
      U('Construcción Perfecta', (255, 215, 160), 4, 80)),
    C('kenjaku', 'Kenjaku', 'Kenjaku', 1000, 5.0, 17, 1.05,
      ((30, 30, 36), 'bun', (232, 232, 232), (70, 120, 70), 'stitches', {'pants': (60, 60, 70)}),
      M('orb', 'Gravedad', 40, 0, (165, 125, 225)),
      M('meteor', 'Lluvia de Maldiciones', 40, 28, (135, 95, 195), count=6),
      M('beam', 'Uzumaki', 150, 45, (125, 75, 205), th=130, range=900),
      U('Manipulación del Cerebro', (80, 45, 120), 6, 46, True)),
    C('higuruma', 'Hiromi Higuruma', 'Higuruma', 900, 4.9, 17, 1.0,
      ((62, 52, 46), 'short', (36, 36, 48), (205, 175, 65), 'glasses'),
      M('melee', 'Mazo del Juez', 40),
      M('stun', 'Confiscación', 25, 20, (235, 205, 95), stun=80),
      M('beam', 'Sentencia', 120, 40, (255, 232, 125), th=72),
      U('Tribunal de la Muerte', (215, 170, 55), 5, 60, True)),
    C('hakari', 'Kinji Hakari', 'Hakari', 1200, 5.0, 17, 1.05,
      ((232, 205, 125), 'short', (42, 42, 54), (235, 195, 65), 'none', {'wide': 1.15}),
      M('melee', 'Golpe Jackpot', 38),
      M('dash', 'Embestida Jackpot', 80, 20, (255, 215, 80), speed=18),
      M('heal', 'Jackpot', 200, 45, (255, 215, 80)),
      U('Paseo de la Muerte', (255, 85, 205), 10, 35, True)),
    C('kashimo', 'Hajime Kashimo', 'Kashimo', 1000, 5.8, 18, 1.0,
      ((236, 236, 116), 'spiky', (32, 32, 44), (90, 205, 255), 'scar'),
      M('proj', 'Descarga', 36, 0, (125, 225, 255), speed=19, size=26),
      M('dash', 'Cuerpo de Relámpago', 90, 22, (150, 232, 255), speed=23),
      M('beam', 'Rayo Maldito', 120, 38, (160, 235, 255), th=60),
      U('Mítico: Tormenta', (155, 235, 255), 6, 50)),
    C('naoya', 'Naoya Zenin', 'Naoya', 850, 7.1, 19, 0.95,
      ((242, 212, 105), 'short', (232, 202, 162), (60, 60, 60), 'none'),
      M('melee', 'Golpe Veloz', 28, startup=4, recovery=11),
      M('teleport', 'Proyección 24 fps', 70, 18, (250, 232, 150)),
      M('multi', 'Ráfaga 24 fps', 10, 26, (250, 232, 150), every=4),
      U('Proyección Final', (250, 230, 150), 7, 40)),
    C('mechamaru', 'Mechamaru', 'Mechamaru', 950, 4.6, 16.5, 1.05,
      ((60, 60, 70), 'bald', (182, 182, 198), (230, 60, 60), 'visor', {'skin': (190, 192, 204)}),
      M('proj', 'Ráfaga de Energía', 30, 0, (255, 140, 90), speed=22, size=22),
      M('beam', 'Cañón Ultra Cilindro', 140, 35, (255, 125, 85), th=82),
      M('meteor', 'Lluvia de Misiles', 40, 32, (255, 150, 75), count=6),
      U('Ultra Cilindro: Máxima Potencia', (255, 130, 80), 4, 85)),
    C('yuki', 'Yuki Tsukumo', 'Yuki', 1100, 5.7, 18, 1.1,
      ((242, 242, 200), 'long', (32, 32, 34), (235, 235, 105), 'none'),
      M('melee', 'Patada Pesada', 38),
      M('wave', 'Masa Virtual', 80, 22, (255, 245, 150)),
      M('dash', 'Garuda', 90, 28, (255, 245, 150), speed=20),
      U('Estrella Negra', (255, 232, 125), 5, 62)),
    C('uraume', 'Uraume', 'Uraume', 900, 5.2, 17.5, 1.0,
      ((232, 242, 255), 'long', (182, 202, 232), (120, 172, 232), 'mask'),
      M('proj', 'Esquirla de Hielo', 32, 0, (185, 232, 255), speed=17),
      M('wave', 'Suelo Helado', 70, 22, (170, 222, 255)),
      M('beam', 'Ventisca', 110, 36, (205, 242, 255), th=92),
      U('Prisión Glacial', (160, 222, 255), 6, 46, True)),
    C('kamo', 'Noritoshi Kamo', 'Kamo', 900, 5.0, 17, 1.0,
      ((32, 26, 32), 'long', (135, 42, 52), (225, 62, 72), 'none'),
      M('proj', 'Flecha de Sangre', 36, 0, (205, 30, 45), speed=19),
      M('slash', 'Hoja de Sangre', 70, 22, (210, 35, 50)),
      M('orb', 'Sangre Convergente', 90, 32, (165, 22, 34), size=44),
      U('Supernova', (225, 45, 60), 5, 60)),
    C('naobito', 'Naobito Zenin', 'Naobito', 950, 6.4, 18.5, 1.0,
      ((205, 205, 205), 'short', (62, 52, 46), (205, 165, 85), 'none'),
      M('melee', 'Golpe Veloz', 34, startup=4, recovery=12),
      M('dash', 'Proyección Rápida', 80, 20, (235, 205, 125), speed=21),
      M('multi', 'Ráfaga', 11, 28, (235, 205, 125), every=5),
      U('Proyección Maestra', (235, 205, 125), 6, 50)),
    C('utahime', 'Utahime Iori', 'Utahime', 880, 5.1, 17.5, 0.95,
      ((32, 26, 32), 'long', (232, 232, 238), (185, 62, 62), 'none', {'pants': (210, 210, 222)}),
      M('proj', 'Ondas de Canto', 30, 0, (255, 225, 185), speed=15, size=30),
      M('buff', 'Canción de Poder', 0, 22, (255, 225, 185)),
      M('heal', 'Melodía Sanadora', 120, 35, (150, 235, 160)),
      U('Coro Maldito', (255, 220, 180), 5, 55)),
]
CBYID = {c['id']: c for c in ROSTER}
AIR_KICK = M('melee', 'Patada aérea', 26, 0, (255, 255, 255), startup=3, active=9, recovery=8, range=85, hh=95,
             knock=5, stun=16)


# ------------------------------------------------------------------ SPRITES
class Frame(object):
    """Un cuadro de animacion. `ax` = x del 'pivote' (pies), `h` = distancia del borde superior a los pies."""
    __slots__ = ('r', 'l', 'ax', 'h', 'w')

    def __init__(self, surf, ax, h):
        self.r = surf
        self.l = None
        self.ax = ax
        self.h = h
        self.w = surf.get_width()

    def get(self, facing):
        if facing >= 0:
            return self.r, self.ax
        if self.l is None:
            self.l = pygame.transform.flip(self.r, True, False)
        return self.l, self.w - self.ax


FXSCALE = {'fireball': 1.4, 'meteor': 1.5, 'meteor_small': 1.4, 'explosion': 1.45, 'wave': 1.3,
           'ring': 3.4, 'orb': 1.5, 'smoke_0': 1.6, 'smoke_1': 1.6, 'smoke_2': 1.6,
           'flame_0': 1.7, 'flame_1': 1.7, 'water': 1.5, 'domain': 2.0}


def _png(path):
    return pygame.image.load(path).convert_alpha()


def load_custom(c, only=None):
    """Carga assets/<id>/ si existe (sprites reales). only=('idle',) carga solo esas animaciones."""
    folder = os.path.join(ASSETS, c['id'])
    if not os.path.isfile(os.path.join(folder, 'idle_0.png')):
        return None
    anchors, meta = {}, {}
    for fn, dst in (('anchors.json', anchors), ('meta.json', meta)):
        p = os.path.join(folder, fn)
        if os.path.isfile(p):
            try:
                with open(p, 'r') as fh:
                    dst.update(json.load(fh))
            except Exception:
                pass
    first = _png(os.path.join(folder, 'idle_0.png'))
    scale = meta.get('scale', STAND_H / float(first.get_height()))
    sprites = {}
    for a in ANIMS:
        if only and a not in only:
            continue
        lst, i = [], 0
        while True:
            name = '%s_%d' % (a, i)
            p = os.path.join(folder, name + '.png')
            if not os.path.isfile(p):
                break
            img = _png(p)
            w, h = img.get_size()
            sw, sh = max(1, int(w * scale)), max(1, int(h * scale))
            img = pygame.transform.smoothscale(img, (sw, sh))
            ax = anchors[name][0] * scale if name in anchors else sw / 2.0
            hh = anchors[name][1] * scale if (name in anchors and len(anchors[name]) > 1) else sh
            lst.append(Frame(img, ax, hh))
            i += 1
        if lst:
            sprites[a] = lst
    fx = {}
    if only:
        return sprites, fx
    try:
        names = sorted(os.listdir(folder))
    except Exception:
        names = []
    for fn in names:
        if fn.startswith('fx_') and fn.endswith('.png'):
            key = fn[3:-4]
            img = _png(os.path.join(folder, fn))
            k = meta.get('fx_scale', {}).get(key, FXSCALE.get(key, 1.4))
            img = pygame.transform.smoothscale(img, (max(1, int(img.get_width() * k)), max(1, int(img.get_height() * k))))
            fx[key] = img
            fx[key + '_l'] = pygame.transform.flip(img, True, False)
    return sprites, fx


# ---- dibujo procedural de personajes
def draw_head(sf, cx, cy, r, st):
    D = pygame.draw
    skin, hair, hs, acc = st['skin'], st['hair'], st['hs'], st['acc']

    def I(v):
        return int(v)

    if hs in ('long', 'bun'):
        D.ellipse(sf, hair, (I(cx - r * 1.15), I(cy - r * 1.0), I(r * 2.3), I(r * 2.6)))
    if hs == 'bun':
        D.circle(sf, hair, (I(cx - r * 0.2), I(cy - r * 1.3)), I(r * 0.5))
    if hs == 'ears':
        D.circle(sf, hair, (I(cx - r * 0.75), I(cy - r * 0.85)), I(r * 0.38))
        D.circle(sf, hair, (I(cx + r * 0.75), I(cy - r * 0.85)), I(r * 0.38))
    D.circle(sf, skin, (I(cx), I(cy)), I(r))
    if hs == 'ears':
        D.circle(sf, hair, (I(cx + r * 0.4), I(cy - r * 0.05)), I(r * 0.28))
        D.circle(sf, hair, (I(cx - r * 0.3), I(cy - r * 0.05)), I(r * 0.28))
    pts = None
    if hs == 'spiky':
        pts = [(-1, -0.1), (-1.1, -1.15), (-0.55, -0.7), (-0.4, -1.65), (0, -0.95), (0.4, -1.7), (0.6, -0.8),
               (1.15, -1.35), (1.05, -0.15), (0.4, -0.45), (-0.5, -0.4)]
    elif hs in ('short', 'long', 'bun'):
        pts = [(-1, 0.1), (-0.95, -0.9), (0, -1.25), (0.95, -0.9), (1.02, -0.05), (0.55, -0.55), (-0.5, -0.5)]
    elif hs == 'volcano':
        pts = [(-0.8, -0.6), (-0.6, -1.5), (0.6, -1.5), (0.8, -0.6), (0.4, -0.5), (-0.4, -0.5)]
    if pts:
        D.polygon(sf, hair, [(I(cx + px * r), I(cy + py * r)) for px, py in pts])
    if hs == 'volcano':
        D.polygon(sf, (255, 150, 40), [(I(cx - r * 0.5), I(cy - r * 1.5)), (I(cx - r * 0.2), I(cy - r * 2.0)),
                                       (I(cx + r * 0.1), I(cy - r * 1.6)), (I(cx + r * 0.4), I(cy - r * 2.2)),
                                       (I(cx + r * 0.5), I(cy - r * 1.5))])
    ex, ey = cx + r * 0.45, cy + r * 0.05
    if acc == 'blindfold':
        D.rect(sf, (18, 18, 26), (I(cx - r), I(cy - r * 0.35), I(r * 2), I(r * 0.55)))
    elif acc == 'eye1':
        D.circle(sf, (255, 255, 255), (I(cx + r * 0.1), I(cy - r * 0.05)), I(r * 0.38))
        D.circle(sf, (20, 20, 30), (I(cx + r * 0.2), I(cy - r * 0.05)), I(r * 0.18))
    elif acc != 'visor':
        D.circle(sf, (20, 20, 30), (I(ex), I(ey)), max(1, I(r * 0.12)))
        D.circle(sf, (20, 20, 30), (I(cx - r * 0.05), I(ey)), max(1, I(r * 0.12)))
    if acc == 'mask':
        D.rect(sf, st['accent'], (I(cx - r * 0.9), I(cy + r * 0.2), I(r * 1.8), I(r * 0.75)))
    elif acc == 'glasses':
        D.circle(sf, (30, 30, 44), (I(ex), I(ey)), max(2, I(r * 0.28)), 2)
        D.circle(sf, (30, 30, 44), (I(cx - r * 0.05), I(ey)), max(2, I(r * 0.28)), 2)
        D.line(sf, (30, 30, 44), (I(cx + r * 0.2), I(ey)), (I(cx + r * 0.25), I(ey)), 2)
    elif acc == 'scar':
        D.line(sf, (150, 60, 60), (I(cx + r * 0.2), I(cy - r * 0.45)), (I(cx + r * 0.7), I(cy + r * 0.45)), 2)
    elif acc == 'stitches':
        D.line(sf, (60, 40, 55), (I(cx - r * 0.9), I(cy - r * 0.6)), (I(cx + r * 0.9), I(cy - r * 0.6)), 2)
        for k in range(-3, 4):
            D.line(sf, (60, 40, 55), (I(cx + k * r * 0.25), I(cy - r * 0.75)), (I(cx + k * r * 0.25), I(cy - r * 0.45)), 1)
    elif acc == 'marks':
        for k in range(2):
            D.line(sf, (60, 30, 40), (I(cx + r * 0.1), I(cy + r * (0.2 + k * 0.25))),
                   (I(cx + r * 0.85), I(cy + r * (0.2 + k * 0.25))), 2)
    elif acc == 'visor':
        D.rect(sf, (235, 70, 70), (I(cx - r * 0.2), I(cy - r * 0.25), I(r * 1.2), I(r * 0.35)))
    if acc not in ('mask',):
        D.line(sf, (130, 70, 70), (I(cx + r * 0.2), I(cy + r * 0.55)), (I(cx + r * 0.6), I(cy + r * 0.55)), 1)


def _ik(a, b, l1, l2, sign):
    dx, dy = b[0] - a[0], b[1] - a[1]
    dist = math.hypot(dx, dy)
    if dist < 1e-6:
        dist, dx, dy = 1e-6, 0.0, 1.0
    maxd = l1 + l2 - 0.5
    if dist > maxd:
        k = maxd / dist
        dx, dy, dist = dx * k, dy * k, maxd
    bx, by = a[0] + dx, a[1] + dy
    ux, uy = dx / dist, dy / dist
    aa = (l1 * l1 - l2 * l2 + dist * dist) / (2 * dist)
    hh = math.sqrt(max(0.0, l1 * l1 - aa * aa))
    mx, my = a[0] + ux * aa, a[1] + uy * aa
    return (mx - uy * hh * sign, my + ux * hh * sign), (bx, by)


def draw_char(st, p):
    """Dibuja un luchador (mirando a la derecha) con la pose `p`."""
    sf = pygame.Surface((CW, CH), pygame.SRCALPHA)
    D = pygame.draw
    cx, G = CW // 2, CH - 8
    wide = st['wide']
    hip = (cx + p['hx'], G - p['hip'])
    sh = (hip[0] + p['lean'], hip[1] - 56)
    outfit, pants, skin = st['outfit'], st['pants'], st['skin']
    shoe = dark(pants, 0.5)

    def line(a, b, w, col):
        D.line(sf, col, (int(a[0]), int(a[1])), (int(b[0]), int(b[1])), w)
        D.circle(sf, col, (int(a[0]), int(a[1])), w // 2)
        D.circle(sf, col, (int(b[0]), int(b[1])), w // 2)

    def leg(off, col):
        foot = (hip[0] + off[0], G - off[1])
        knee, foot = _ik(hip, foot, 42, 42, -1)
        w = int(15 * wide)
        line(hip, knee, w, col)
        line(knee, foot, w - 1, col)
        D.ellipse(sf, shoe, (int(foot[0] - 8), int(foot[1] - 5), 22, 11))

    def arm(off, col, hand_col):
        sp = (sh[0], sh[1] + 5)
        tgt = (sh[0] + off[0], sh[1] + off[1])
        elb, hnd = _ik(sp, tgt, 30, 30, 1)
        w = int(12 * wide)
        line(sp, elb, w, col)
        line(elb, hnd, w - 1, col)
        D.circle(sf, hand_col, (int(hnd[0]), int(hnd[1])), 6)

    arm(p['bh'], dark(outfit, 0.75), dark(skin, 0.85))
    leg(p['bf'], dark(pants, 0.8))
    D.polygon(sf, outfit, [(int(sh[0] - 20 * wide), int(sh[1])), (int(sh[0] + 20 * wide), int(sh[1])),
                           (int(hip[0] + 16 * wide), int(hip[1])), (int(hip[0] - 16 * wide), int(hip[1]))])
    D.polygon(sf, st['accent'], [(int(sh[0] - 7), int(sh[1])), (int(sh[0] + 7), int(sh[1])), (int(sh[0]), int(sh[1] + 24))])
    D.line(sf, st['accent'], (int(hip[0] - 14 * wide), int(hip[1])), (int(hip[0] + 14 * wide), int(hip[1])), 4)
    leg(p['ff'], pants)
    D.line(sf, skin, (int(sh[0]), int(sh[1])), (int(sh[0] + p['tilt'] * 0.5), int(sh[1] - 14)), 7)
    draw_head(sf, int(sh[0] + p['tilt'] + 2), int(sh[1] - 26), 17, st)
    arm(p['fh'], outfit, skin)
    return sf


def P(**kw):
    p = dict(hip=84, lean=4, tilt=0, hx=0, ff=(16, 0), bf=(-16, 0), fh=(26, 18), bh=(14, 26))
    p.update(kw)
    return p


def poses_idle():
    return [P(hip=83 + b, fh=(26, 18 + b), bh=(15, 26 - b)) for b in (0, 1, 2, 1)]


def poses_walk():
    out = []
    for i in range(6):
        ph = i / 6.0 * math.tau
        s, c = math.sin(ph), math.cos(ph)
        out.append(P(hip=82 + abs(c) * 2, lean=6, ff=(14 + 22 * s, 12 * max(0, -c)), bf=(-14 - 22 * s, 12 * max(0, c)),
                     fh=(22 - 8 * s, 20), bh=(16 + 8 * s, 26)))
    return out


def poses_run():
    out = []
    for i in range(6):
        ph = i / 6.0 * math.tau
        s, c = math.sin(ph), math.cos(ph)
        out.append(P(hip=77 + abs(c) * 3, lean=17, ff=(10 + 30 * s, 24 * max(0, -c)), bf=(-10 - 30 * s, 24 * max(0, c)),
                     fh=(12 + 22 * s, 24), bh=(12 - 22 * s, 24)))
    return out


def poses_jump():
    return [P(hip=92, lean=6, ff=(14, 20), bf=(-10, 10), fh=(20, -14), bh=(0, -10)),
            P(hip=90, lean=6, ff=(20, 30), bf=(-6, 22), fh=(26, 6), bh=(10, 10)),
            P(hip=88, lean=4, ff=(22, 34), bf=(-2, 30), fh=(28, 14), bh=(12, 18)),
            P(hip=86, lean=4, ff=(16, 12), bf=(-12, 6), fh=(24, 20), bh=(14, 24))]


def poses_crouch():
    return [P(hip=62, lean=10, ff=(26, 0), bf=(-22, 0), fh=(26, 12), bh=(14, 20)),
            P(hip=50, lean=14, ff=(30, 0), bf=(-24, 0), fh=(26, 14), bh=(14, 20))]


def poses_attack():
    return [P(lean=-2, fh=(-6, 14), bh=(20, 16), ff=(18, 0), bf=(-18, 0)),
            P(lean=16, hx=6, fh=(62, -2), bh=(10, 22), ff=(26, 0), bf=(-20, 0)),
            P(lean=10, hx=4, fh=(44, 6), bh=(12, 22), ff=(24, 0), bf=(-18, 0))]


def poses_special():
    return [P(lean=0, fh=(14, -28), bh=(8, -30)),
            P(lean=-4, hip=86, fh=(18, -52), bh=(10, -54)),
            P(lean=-6, hip=86, fh=(22, -60), bh=(14, -62)),
            P(lean=14, hx=6, fh=(56, -10), bh=(50, -4), ff=(28, 0), bf=(-22, 0))]


def poses_skill():
    return [P(hip=70, lean=8, fh=(24, 18), bh=(10, 24), ff=(24, 0), bf=(-20, 0)),
            P(hip=58, lean=14, fh=(30, 34), bh=(18, 38), ff=(28, 0), bf=(-24, 0)),
            P(hip=52, lean=20, hx=4, fh=(50, 40), bh=(40, 44), ff=(32, 0), bf=(-26, 0)),
            P(hip=52, lean=20, hx=4, fh=(54, 44), bh=(44, 48), ff=(32, 0), bf=(-26, 0))]


def poses_hit():
    return [P(lean=-14, tilt=-6, hip=82, fh=(-4, 22), bh=(-10, 26), ff=(10, 0), bf=(-22, 0)),
            P(lean=-22, tilt=-10, hip=76, fh=(-10, 20), bh=(-16, 24), ff=(4, 2), bf=(-26, 0)),
            P(lean=-30, tilt=-14, hip=70, hx=-6, fh=(-14, 16), bh=(-20, 20), ff=(-4, 14), bf=(-30, 6))]


POSES = dict(idle=poses_idle, walk=poses_walk, run=poses_run, jump=poses_jump, crouch=poses_crouch,
             attack=poses_attack, special=poses_special, skill=poses_skill, hit=poses_hit)


def build_proc(c, only=None):
    out = {}
    for a, fn in POSES.items():
        if only and a not in only:
            continue
        out[a] = [Frame(draw_char(c['style'], p), CW // 2, CH - 8) for p in fn()]
    return out


class Bank(object):
    """Cache de sprites (guarda solo los ultimos 4 personajes completos)."""
    full = {}
    order = []
    prev = {}

    @classmethod
    def get(cls, c):
        cid = c['id']
        if cid in cls.full:
            cls.order.remove(cid)
            cls.order.append(cid)
            return cls.full[cid]
        data = load_custom(c)
        if data is None:
            data = (build_proc(c), {})
        cls.full[cid] = data
        cls.order.append(cid)
        while len(cls.order) > 4:
            old = cls.order.pop(0)
            cls.full.pop(old, None)
        return data

    @classmethod
    def preview(cls, c):
        cid = c['id']
        if cid in cls.full:
            return cls.full[cid][0]['idle']
        if cid not in cls.prev:
            data = load_custom(c, ('idle',))
            cls.prev[cid] = data[0]['idle'] if data else build_proc(c, ('idle',))['idle']
        return cls.prev[cid]


_PORT = {}


def portrait(c, size=96):
    key = (c['id'], size)
    if key in _PORT:
        return _PORT[key]
    face = os.path.join(ASSETS, c['id'], 'face_0.png')
    if os.path.isfile(face):
        sf = pygame.transform.smoothscale(_png(face), (size, size))
    else:
        st = c['style']
        sf = pygame.Surface((size, size))
        sf.fill(dark(st['outfit'], 0.35))
        pygame.draw.circle(sf, dark(c['ult']['color'], 0.55), (size // 2, int(size * 0.45)), int(size * 0.42))
        pygame.draw.ellipse(sf, st['outfit'], (int(size * 0.08), int(size * 0.7), int(size * 0.84), int(size * 0.6)))
        pygame.draw.polygon(sf, st['accent'], [(int(size * 0.42), int(size * 0.72)), (int(size * 0.58), int(size * 0.72)),
                                                (int(size * 0.5), int(size * 0.92))])
        draw_head(sf, size // 2, int(size * 0.44), int(size * 0.27), st)
    _PORT[key] = sf
    return sf


# ------------------------------------------------------------------ ESCENARIOS
STAGES = [
    ('Escuela Jujutsu - Atardecer', (255, 190, 120), (200, 100, 120), (70, 45, 90), (52, 42, 58)),
    ('Shibuya - Noche', (8, 8, 28), (30, 30, 90), (110, 50, 140), (30, 28, 44)),
    ('Shinjuku - Cielo Rojo', (60, 0, 10), (160, 25, 25), (240, 110, 50), (54, 22, 24)),
    ('Valle de Cenizas', (36, 38, 52), (96, 88, 104), (170, 150, 150), (62, 58, 64)),
]


def build_stage(i):
    name, c0, c1, c2, cg = STAGES[i]
    sf = pygame.Surface((W, H))
    D = pygame.draw
    for y in range(H):
        t = clamp(y / float(GROUND - 40), 0, 1)
        col = mix(c0, c1, t * 2) if t < 0.5 else mix(c1, c2, (t - 0.5) * 2)
        D.line(sf, col, (0, y), (W, y))
    rnd = random.Random(i * 77 + 5)
    ax, ay = (980, 170) if i != 3 else (300, 150)
    gc = light(c2, 0.5)
    D.circle(sf, mix(gc, c1, 0.55), (ax, ay), 96)
    D.circle(sf, mix(gc, c1, 0.25), (ax, ay), 66)
    D.circle(sf, light(gc, 0.45), (ax, ay), 46)
    for layer, (base, hmin, hmax) in enumerate(((GROUND - 20, 150, 340), (GROUND, 70, 230))):
        col = dark(mix(c1, c0, 0.5), 0.55 - layer * 0.25)
        x = -30
        while x < W:
            w, h = rnd.randint(60, 150), rnd.randint(hmin, hmax)
            D.rect(sf, col, (x, base - h, w, h))
            if layer == 0:
                for wy in range(base - h + 14, base - 16, 26):
                    for wx in range(x + 10, x + w - 10, 22):
                        if rnd.random() < 0.28:
                            D.rect(sf, (255, 226, 130), (wx, wy, 8, 12))
            x += w + rnd.randint(-10, 14)
    for y in range(GROUND, H):
        D.line(sf, mix(light(cg, 0.15), dark(cg, 0.5), (y - GROUND) / float(H - GROUND)), (0, y), (W, y))
    D.line(sf, light(cg, 0.5), (0, GROUND), (W, GROUND), 3)
    for k in range(-9, 10):
        D.line(sf, dark(cg, 0.7), (W // 2 + k * 50, GROUND), (W // 2 + k * 190, H), 1)
    return sf


# ------------------------------------------------------------------ ENTRADA (jugadores y CPU)
class Inp(object):
    __slots__ = ('dx', 'jump', 'down', 'block', 'normal', 'special', 'skill', 'domain')

    def __init__(self):
        self.dx = 0
        self.jump = self.down = self.block = False
        self.normal = self.special = self.skill = self.domain = False


K = pygame
P1_KEYS = dict(left=[K.K_a], right=[K.K_d], jump=[K.K_w], down=[K.K_s], normal=[K.K_f], special=[K.K_g],
               skill=[K.K_h], domain=[K.K_t], block=[K.K_r])
P2_KEYS = dict(left=[K.K_LEFT], right=[K.K_RIGHT], jump=[K.K_UP], down=[K.K_DOWN], normal=[K.K_KP1, K.K_k],
               special=[K.K_KP2, K.K_l], skill=[K.K_KP3, K.K_o], domain=[K.K_KP0, K.K_i], block=[K.K_KP5, K.K_u])


class KeyCtrl(object):
    def __init__(self, km):
        self.km = km
        self.prev = {}

    def read(self, keys, me, opp):
        i = Inp()

        def held(n):
            for k in self.km[n]:
                if keys[k]:
                    return True
            return False

        i.dx = (1 if held('right') else 0) - (1 if held('left') else 0)
        i.down = held('down')
        i.block = held('block')
        for n in ('jump', 'normal', 'special', 'skill', 'domain'):
            h = held(n)
            setattr(i, n, h and not self.prev.get(n, False))
            self.prev[n] = h
        return i


class Dummy(object):
    def read(self, keys, me, opp):
        return Inp()


def pick_move(me, ad):
    opts, wts = [], []
    for key in ('normal', 'special', 'skill'):
        mv = me.moves[key]
        if me.ce < mv['cost']:
            continue
        k = mv['kind']
        if k == 'heal':
            if me.hp < me.maxhp * 0.6:
                opts.append(key)
                wts.append(3)
            continue
        if k == 'buff':
            if me.buff <= 0:
                opts.append(key)
                wts.append(2)
            continue
        reach = 150 if k in ('melee', 'multi') else 330 if k in ('dash', 'teleport') else 900
        if ad <= reach:
            opts.append(key)
            wts.append(2 if key == 'normal' else 3)
    if not opts:
        return None
    return random.choices(opts, wts)[0]


class AI(object):
    def __init__(self, level):
        self.lv = (0.6, 1.0, 1.6)[level]
        self.t = 0
        self.plan = 'approach'
        self.cool = 40

    def read(self, keys, me, opp):
        i = Inp()
        self.cool -= 1
        if me.state in ('hit', 'ko', 'trapped', 'domain', 'attack'):
            return i
        dx = opp.x - me.x
        ad = abs(dx)
        d = 1 if dx >= 0 else -1
        self.t -= 1
        if self.t <= 0:
            self.t = int(random.randint(8, 22) / self.lv) + 2
            r = random.random()
            if opp.state == 'attack' and ad < 300 and r < 0.35 * self.lv:
                self.plan = 'block'
            elif ad > 420:
                self.plan = 'zone' if r < 0.4 else 'approach'
            elif ad > 170:
                self.plan = 'approach' if r < 0.5 else 'zone' if r < 0.8 else 'jump'
            else:
                self.plan = 'attack' if r < 0.62 else 'retreat' if r < 0.75 else 'block' if r < 0.88 else 'jump'
        if me.ce >= 100 and ad < 700 and random.random() < 0.02:
            i.domain = True
            return i
        p = self.plan
        if p == 'approach':
            i.dx = d
        elif p == 'retreat':
            i.dx = -d
        elif p == 'block':
            i.block = True
        elif p == 'jump':
            i.jump = True
            i.dx = d
            self.plan = 'approach'
        elif p in ('attack', 'zone'):
            if self.cool <= 0:
                key = pick_move(me, ad)
                if key:
                    setattr(i, key, True)
                    self.cool = int(random.randint(18, 50) / self.lv)
                else:
                    i.dx = d
            else:
                i.dx = d if (ad > 120 and p == 'attack') else 0
        return i


# ------------------------------------------------------------------ EFECTOS
class Fx(object):
    def __init__(self, kind, x, y, life, **kw):
        self.kind, self.x, self.y = kind, x, y
        self.life = self.max = life
        self.kw = kw

    def update(self):
        self.life -= 1
        self.y += self.kw.get('vy', 0)

    def draw(self, cv):
        k, t, kw = self.kind, self.life / float(self.max), self.kw
        if k == 'ring':
            r = kw['r1'] + (kw['r0'] - kw['r1']) * t
            pygame.draw.circle(cv, kw['color'], (int(self.x), int(self.y)), max(2, int(r)), max(1, int(kw.get('w', 4) * t)))
        elif k == 'img':
            img = kw['img']
            img.set_alpha(int(255 * min(1.0, t * 2.2)))
            cv.blit(img, (int(self.x - img.get_width() / 2), int(self.y - img.get_height())))
            img.set_alpha(255)
        elif k == 'text':
            text(cv, kw['s'], kw.get('size', 34), kw['color'], (self.x, self.y), 'center')
        elif k == 'glow':
            glow(cv, self.x, self.y, kw['r'] * (0.6 + 0.4 * t), kw['color'])


class Projectile(object):
    def __init__(self, m, owner, mv, x, y, vx, vy, kind=None):
        self.m, self.o, self.mv = m, owner, mv
        self.x, self.y, self.vx, self.vy = x, y, vx, vy
        self.kind = kind or mv['kind']
        self.life = mv.get('life', 90)
        self.age = 0
        self.dead = False
        self.hit = False
        self.size = mv.get('size', 28)
        self.color = mv['color']
        fxn = mv.get('fx')
        self.fxn = fxn if (fxn and owner.fx.get(fxn) is not None) else None
        self.x0 = x
        self.front = 0
        self.dir = 1 if vx >= 0 else -1

    # --- daño
    def hit_target(self, opp, dmg=None, sx=None, **over):
        mv = self.mv
        args = dict(knock=mv['knock'], stun=mv['stun'], launch=mv.get('launch', 0), sx=sx if sx is not None else self.x)
        args.update(over)
        return opp.take_hit(self.o, mv['dmg'] if dmg is None else dmg, **args)

    def explode(self, opp):
        m, mv = self.m, self.mv
        bl = mv.get('blast', 100)
        if overlap((self.x - bl, GROUND - 160, bl * 2, 170), opp.hurt()):
            self.hit_target(opp, sx=self.x, knock=mv['knock'], stun=mv['stun'], launch=mv.get('launch', 0))
        img = self.o.fx.get('explosion')
        if img is not None and self.kind == 'meteor':
            m.fx.append(Fx('img', self.x, GROUND + 6, 30, img=img))
            sm = self.o.fx.get('smoke_%d' % random.randint(0, 2))
            if sm is not None:
                m.fx.append(Fx('img', self.x + random.randint(-30, 30), GROUND + 4, 40, img=sm))
        else:
            m.fx.append(Fx('ring', self.x, GROUND - 20, 18, color=self.color, r0=20, r1=bl, w=8))
            m.fx.append(Fx('glow', self.x, GROUND - 40, 14, r=bl, color=self.color))
        m.spark(self.x, GROUND - 30, self.color, 14)
        m.shake = max(m.shake, 6)
        m.sfx('boom')
        self.dead = True

    def update(self):
        opp = self.o.opp
        k = self.kind
        self.age += 1
        mv = self.mv
        if k == 'wave':
            self.front += mv['speed']
            if self.front > mv['range']:
                self.dead = True
                return
            seg = 150
            start = max(0, self.front - seg)
            ln = self.front - start
            x = self.x0 + start if self.dir == 1 else self.x0 - start - ln
            r = (x, GROUND - mv['hh'], ln, mv['hh'])
            if not self.hit and opp.y >= GROUND - 14 and overlap(r, opp.hurt()):
                if self.hit_target(opp, sx=self.x0):
                    self.hit = True
            return
        if k == 'meteor':
            self.vy += 0.5
            self.x += self.vx
            self.y += self.vy
            r = (self.x - self.size, self.y - self.size, self.size * 2, self.size * 2)
            if self.y >= GROUND - 10 or (opp.state not in ('ko', 'trapped', 'domain') and opp.invul <= 0
                                         and overlap(r, opp.hurt())):
                self.explode(opp)
            return
        self.x += self.vx
        self.y += self.vy
        self.life -= 1
        if k == 'orb' and opp.state not in ('ko', 'trapped', 'domain'):
            if abs(opp.x - self.x) < mv['pullr']:
                opp.x += clamp(self.x - opp.x, -1, 1) * mv['pull']
        if self.life <= 0 or self.x < -120 or self.x > W + 120:
            if k == 'orb':
                self.explode(opp)
            self.dead = True
            return
        sz = self.size
        r = (self.x - sz / 2.0, self.y - (sz if k == 'slash' else sz / 2.0), sz, sz * 2 if k == 'slash' else sz)
        if not self.hit and overlap(r, opp.hurt()):
            res = self.hit_target(opp)
            if res:
                m = self.m
                m.spark(self.x, self.y, self.color, 10, big=(res is True))
                if mv.get('pierce') and res is True:
                    self.hit = True
                else:
                    self.dead = True
                if self.kind == 'orb':
                    m.fx.append(Fx('ring', self.x, self.y, 16, color=self.color, r0=10, r1=90, w=6))

    def draw(self, cv):
        k = self.kind
        c = self.color
        if k == 'wave':
            ln = int(self.front)
            if ln < 6:
                return
            img = self.o.fx.get('wave') if self.fxn == 'wave' else None
            if img is not None:
                s = pygame.transform.smoothscale(img, (ln, img.get_height()))
                if self.dir < 0:
                    s = pygame.transform.flip(s, True, False)
                x = self.x0 if self.dir == 1 else self.x0 - ln
                cv.blit(s, (int(x), int(GROUND - s.get_height() + 22)))
            else:
                hh = self.mv['hh']
                for i in range(0, ln, 34):
                    a = self.x0 + i * self.dir
                    hgt = hh * (0.45 + 0.55 * abs(math.sin(i * 0.09 + self.age * 0.35)))
                    pts = [(a, GROUND + 6), (a + 17 * self.dir, GROUND - hgt), (a + 34 * self.dir, GROUND + 6)]
                    pygame.draw.polygon(cv, c, [(int(px), int(py)) for px, py in pts])
                    pygame.draw.polygon(cv, light(c, 0.6), [(int(a + 9 * self.dir), int(GROUND + 2)),
                                                            (int(a + 17 * self.dir), int(GROUND - hgt * 0.55)),
                                                            (int(a + 25 * self.dir), int(GROUND + 2))])
                glow(cv, self.x0 + ln * self.dir, GROUND - 20, 46, c)
            return
        if k == 'meteor':
            img = self.o.fx.get('meteor') if self.fxn == 'meteor' else None
            if img is not None:
                cv.blit(img, (int(self.x - img.get_width() / 2), int(self.y - img.get_height() * 0.6)))
            else:
                glow(cv, self.x, self.y, self.size * 2.6, c)
                pygame.draw.circle(cv, light(c, 0.2), (int(self.x), int(self.y)), self.size)
                pygame.draw.circle(cv, (255, 255, 255), (int(self.x), int(self.y)), int(self.size * 0.5))
                pygame.draw.line(cv, c, (int(self.x), int(self.y)), (int(self.x - self.vx * 6), int(self.y - 70)), 8)
            return
        img = self.o.fx.get(self.fxn) if self.fxn else None
        if img is not None:
            img = self.o.fx.get(self.fxn + '_l') if self.vx < 0 else img
            cv.blit(img, (int(self.x - img.get_width() * 0.62), int(self.y - img.get_height() / 2)))
            return
        sz = self.size
        glow(cv, self.x, self.y, sz * 1.9, c)
        if k == 'slash':
            d = 1 if self.vx >= 0 else -1
            outer, inner = [], []
            for a in range(-70, 71, 10):
                ang = math.radians(a)
                outer.append((self.x + d * math.cos(ang) * sz * 0.9, self.y + math.sin(ang) * sz * 1.05))
            for a in range(70, -71, -10):
                ang = math.radians(a)
                inner.append((self.x - d * 14 + d * math.cos(ang) * sz * 0.55, self.y + math.sin(ang) * sz * 0.95))
            pygame.draw.polygon(cv, c, [(int(a), int(b)) for a, b in outer + inner])
            pygame.draw.polygon(cv, light(c, 0.7), [(int(a - d * 6), int(b)) for a, b in outer[2:-2] + inner[2:-2]])
        else:
            pygame.draw.circle(cv, c, (int(self.x), int(self.y)), int(sz * 0.55))
            pygame.draw.circle(cv, light(c, 0.75), (int(self.x), int(self.y)), int(sz * 0.32))
            if k == 'orb':
                pygame.draw.circle(cv, (255, 255, 255), (int(self.x), int(self.y)), int(sz * 0.55), 2)
            for j in range(1, 4):
                pygame.draw.circle(cv, dark(c, 0.8), (int(self.x - self.vx * j * 1.6), int(self.y)), max(2, int(sz * 0.34 - j * 3)))


# ------------------------------------------------------------------ LUCHADOR
class Fighter(object):
    def __init__(self, match, idx, c, x, facing):
        self.m, self.idx, self.c = match, idx, c
        self.spr, self.fx = Bank.get(c)
        self.moves = c['moves']
        self.maxhp, self.spd, self.jmp, self.pw = c['hp'], c['spd'], c['jmp'], c['pw']
        self.opp = None
        self.wins = 0
        self.custom = os.path.isfile(os.path.join(ASSETS, c['id'], 'idle_0.png'))
        self.ko_last = False
        if self.custom:                      # meta.json: ko_lying = tumbarse rotado; ko_last = el ultimo cuadro de 'hit' es el caido
            try:
                with open(os.path.join(ASSETS, c['id'], 'meta.json'), 'r') as fh:
                    meta = json.load(fh)
                self.custom = not meta.get('ko_lying', False)
                self.ko_last = bool(meta.get('ko_last', False))
            except Exception:
                pass
        self.reset(x, facing)

    def reset(self, x, facing):
        self.x, self.y, self.vx, self.vy, self.facing = x, GROUND, 0.0, 0.0, facing
        self.hp = float(self.maxhp)
        self.ghost = self.hp
        self.ce = 30.0
        self.state, self.st, self.at = 'idle', 0, 0
        self.move, self.mkey, self.mt, self.total, self.landed = None, None, 0, 1, False
        self.queue = []
        self.buff = self.stun = self.invul = self.combo = self.combo_t = self.flash = 0
        self.run_t, self.run_dir = 0, 0
        self.ult, self.dom_total = None, 0
        self.air_used = False
        self.ko_img = None

    # ---- utilidades
    def set_state(self, n):
        if self.state != n:
            self.state = n
            self.st = 0

    def hurt(self):
        h = HURT_CROUCH if self.state == 'crouch' else HURT_H
        return (self.x - HURT_W / 2.0, self.y - h, HURT_W, h)

    def melee_rect(self, mv):
        r = mv['range']
        x = self.x + 10 if self.facing == 1 else self.x - 10 - r
        return (x, self.y - mv['hh'] - 8, r, mv['hh'])

    # ---- daño recibido
    def take_hit(self, atk, dmg, knock=6, stun=18, launch=0, unblockable=False, sx=None):
        if self.state in ('ko', 'domain', 'trapped') or self.invul > 0:
            return False
        m = self.m
        if sx is None:
            sx = atk.x
        dirx = 1 if self.x >= sx else -1
        dmg *= atk.pw * (1.35 if atk.buff > 0 else 1.0)
        front = (sx - self.x) * self.facing > 0
        if self.state == 'block' and front and not unblockable:
            self.hp = max(1.0, self.hp - dmg * 0.12)
            self.vx = dirx * min(knock, 6) * 0.7
            self.ce = min(100.0, self.ce + 2)
            m.spark(self.x + self.facing * 34, self.y - 110, (120, 180, 255), 8, big=False)
            m.hitstop = max(m.hitstop, 2)
            m.sfx('block')
            return 'block'
        self.hp -= dmg
        self.move = None
        self.queue = []
        self.set_state('hit')
        self.stun = stun
        self.vx = dirx * knock
        if launch:
            self.vy = -launch
            self.y = GROUND - 1
        atk.ce = min(100.0, atk.ce + dmg * 0.10)
        self.ce = min(100.0, self.ce + dmg * 0.05)
        atk.combo += 1
        atk.combo_t = 100
        self.flash = 5
        m.hitstop = max(m.hitstop, 3 + min(5, int(dmg / 25)))
        m.shake = max(m.shake, min(11, dmg / 9.0))
        m.spark(self.x, self.y - 105, (255, 240, 200), 8 + int(dmg / 12))
        m.sfx('hit')
        if self.hp <= 0:
            self.hp = 0.0
            self.state, self.st = 'ko', 0
            self.vy, self.vx = -10.0, dirx * 8.0
            self.y = GROUND - 1
            m.shake, m.hitstop, m.flash = 14, 10, 6
            m.sfx('ko')
        return True

    # ---- actualizacion
    def update(self, inp, opp):
        self.at += 1
        self.st += 1
        if self.buff > 0:
            self.buff -= 1
        if self.invul > 0:
            self.invul -= 1
        if self.flash > 0:
            self.flash -= 1
        if self.combo_t > 0:
            self.combo_t -= 1
            if self.combo_t == 0:
                self.combo = 0
        if self.ce < 100:
            self.ce = min(100.0, self.ce + 0.08)
        if self.ghost > self.hp:
            self.ghost = max(self.hp, self.ghost - 0.7)
        elif self.ghost < self.hp:
            self.ghost = self.hp
        if self.queue:
            for q in self.queue:
                q[0] -= 1
            due = [q for q in self.queue if q[0] <= 0]
            self.queue = [q for q in self.queue if q[0] > 0]
            for q in due:
                q[1]()
        st = self.state
        if st == 'ko':
            self.physics()
            return
        if st == 'trapped':
            return
        if st == 'domain':
            self.run_domain(opp)
            return
        if st == 'hit':
            self.stun -= 1
            self.physics()
            if self.stun <= 0 and self.y >= GROUND:
                self.set_state('idle')
            return
        if st == 'attack':
            self.run_move(opp)
            self.physics()
            return
        self.control(inp, opp)
        self.physics()

    def physics(self):
        if self.y < GROUND or self.vy < 0:
            self.vy += GRAVITY
        self.y += self.vy
        if self.y >= GROUND:
            self.y = GROUND
            if self.vy > 0:
                self.vy = 0.0
            if self.state in ('hit', 'ko', 'attack'):
                self.vx *= 0.8
        self.x = clamp(self.x + self.vx, ARENA_L, ARENA_R)

    def control(self, inp, opp):
        ground = self.y >= GROUND
        if ground and abs(opp.x - self.x) > 6:
            self.facing = 1 if opp.x > self.x else -1
        if ground:
            self.air_used = False
            if inp.domain and self.ce >= 100 and opp.state not in ('ko', 'domain', 'trapped'):
                self.start_domain(opp)
                return
            for key, flag in (('skill', inp.skill), ('special', inp.special), ('normal', inp.normal)):
                if flag and self.start_move(key):
                    return
            if inp.block:
                self.set_state('block')
                self.vx = 0
                return
            if inp.down:
                self.set_state('crouch')
                self.vx = 0
                return
            if inp.jump:
                self.vy = -self.jmp
                self.vx = inp.dx * self.spd
                self.set_state('jump')
                self.y = GROUND - 1
                self.m.sfx('jump')
                return
            if inp.dx:
                if inp.dx == self.run_dir:
                    self.run_t += 1
                else:
                    self.run_dir, self.run_t = inp.dx, 0
                fast = self.run_t > 40
                self.vx = inp.dx * self.spd * (1.5 if fast else 1.0)
                self.set_state('run' if fast else 'walk')
            else:
                self.run_t = 0
                self.vx = 0
                self.set_state('idle')
        else:
            if inp.normal and not self.air_used:
                self.air_used = True
                self.start_air()
                return
            if inp.dx:
                self.vx = clamp(self.vx + inp.dx * 0.3, -self.spd * 1.4, self.spd * 1.4)
            self.set_state('jump')

    # ---- movimientos
    def start_move(self, key):
        mv = self.moves[key]
        if self.ce < mv['cost']:
            return False
        self.ce -= mv['cost']
        self.move, self.mkey, self.mt, self.landed = mv, key, 0, False
        self.total = mv['startup'] + mv['active'] + mv['recovery']
        self.set_state('attack')
        self.vx = 0
        return True

    def start_air(self):
        mv = AIR_KICK
        self.move, self.mkey, self.mt, self.landed = mv, 'air', 0, False
        self.total = mv['startup'] + mv['active'] + mv['recovery']
        self.set_state('attack')

    def run_move(self, opp):
        mv = self.move
        k, t, su, ac = mv['kind'], self.mt, mv['startup'], mv['active']
        m = self.m
        if k in PROJ_KINDS:
            if t == su:
                self.fire(mv)
        elif k == 'wave':
            if t == su:
                p = Projectile(m, self, mv, self.x + self.facing * 40, GROUND, self.facing, 0, kind='wave')
                m.projs.append(p)
                m.sfx('boom')
        elif k == 'meteor':
            if t == su:
                self.fire_meteors(mv, opp)
        elif k == 'heal':
            if t == su:
                self.hp = min(float(self.maxhp), self.hp + mv['dmg'])
                m.spark(self.x, self.y - 100, (120, 255, 150), 16)
                m.sfx('heal')
                m.fx.append(Fx('text', self.x, self.y - 190, 40, s='+%d' % mv['dmg'], color=(120, 255, 150), vy=-1))
        elif k == 'buff':
            if t == su:
                self.buff = 480
                m.spark(self.x, self.y - 100, mv['color'], 16)
                m.sfx('buff')
                m.fx.append(Fx('text', self.x, self.y - 190, 40, s='¡PODER!', color=mv['color'], vy=-1))
        elif k == 'beam':
            if t == su:
                m.sfx('beam')
            if su <= t < su + ac:
                every = max(1, ac // mv['ticks'])
                n = t - su
                if n % every == 0 and n // every < mv['ticks']:
                    if overlap(self.beam_rect(mv), opp.hurt()):
                        opp.take_hit(self, mv['dmg'] / float(mv['ticks']), knock=mv['knock'], stun=mv['stun'],
                                     launch=(mv['launch'] if n // every == mv['ticks'] - 1 else 0))
        else:  # melee, multi, dash, teleport
            if k == 'teleport' and t == su:
                side = opp.facing
                self.x = clamp(opp.x - side * 70, ARENA_L, ARENA_R)
                self.facing = side
                m.spark(self.x, self.y - 90, mv['color'], 12)
                m.sfx('shoot')
            if su <= t < su + ac:
                if k == 'dash' and abs(opp.x - self.x) > 45:
                    self.x = clamp(self.x + self.facing * mv['speed'], ARENA_L, ARENA_R)
                if k == 'multi' and (t - su) % mv['every'] == 0:
                    self.landed = False
                if not self.landed and overlap(self.melee_rect(mv), opp.hurt()):
                    dmg = mv['dmg']
                    if mv.get('crit') and random.random() < mv['crit']:
                        dmg *= 2
                        m.fx.append(Fx('text', opp.x, opp.y - 200, 40, s='¡CRÍTICO!', color=(255, 230, 90), vy=-1))
                    launch = mv['launch']
                    if k == 'multi' and t < su + ac - mv['every']:
                        launch = 0
                    res = opp.take_hit(self, dmg, knock=mv['knock'], stun=mv['stun'], launch=launch)
                    if res:
                        self.landed = True
                        if k == 'dash':
                            self.mt = max(self.mt, su + ac - 1)
        self.mt += 1
        if self.mt >= self.total:
            self.move = None
            self.set_state('idle')

    def beam_len(self, mv):
        n = self.mt - mv['startup']
        return mv['range'] * clamp((n + 1) / 5.0, 0.0, 1.0)

    def beam_rect(self, mv):
        ln = self.beam_len(mv)
        x0 = self.x + self.facing * 30
        x = x0 if self.facing == 1 else x0 - ln
        return (x, self.y - mv['y'] - mv['th'] / 2.0, ln, mv['th'])

    def fire(self, mv):
        n = mv.get('burst', 1)
        self.spawn_proj(mv)
        for i in range(1, n):
            self.queue.append([i * mv.get('gap', 6), (lambda mv=mv: self.spawn_proj(mv))])

    def spawn_proj(self, mv):
        p = Projectile(self.m, self, mv, self.x + self.facing * 55, self.y - mv.get('y', 125),
                       self.facing * mv['speed'], 0)
        self.m.projs.append(p)
        self.m.spark(p.x, p.y, mv['color'], 5, big=False)
        self.m.sfx('shoot')

    def fire_meteors(self, mv, opp):
        n = mv['count']
        for i in range(n):
            def make(i=i):
                x = clamp(opp.x + random.randint(-260, 260), ARENA_L, ARENA_R)
                self.m.projs.append(Projectile(self.m, self, mv, x, -90, random.uniform(-1, 1),
                                               random.uniform(7, 10), kind='meteor'))
            if i == 0:
                make()
            else:
                self.queue.append([i * 7, make])

    # ---- dominio / tecnica maxima
    def start_domain(self, opp):
        u = self.c['ult']
        self.ce = 0.0
        self.ult = u
        self.dom_total = 40 + u['ticks'] * 18 + 34
        self.move = None
        self.queue = []
        self.set_state('domain')
        self.invul = self.dom_total + 10
        self.vx = 0
        opp.move = None
        opp.queue = []
        opp.vx = opp.vy = 0.0
        opp.y = GROUND
        opp.set_state('trapped')
        self.m.flash = 6
        if not self.m.begin_cine(u.get('cine')):
            self.m.sfx('domain')

    def run_domain(self, opp):
        u, t, gap = self.ult, self.st, 18
        n = (t - 40) // gap
        if t >= 40 and (t - 40) % gap == 0 and 0 <= n < u['ticks']:
            d = u['dmg'] * self.pw * (1.35 if self.buff > 0 else 1.0)
            opp.hp = max(0.0, opp.hp - d)
            opp.flash = 6
            self.m.flash = 3
            self.m.shake = max(self.m.shake, 7)
            self.m.sfx('hit')
            self.m.spark(opp.x, opp.y - 100, light(u['color'], 0.4), 16)
            self.m.fx.append(Fx('ring', opp.x, opp.y - 100, 14, color=light(u['color'], 0.5), r0=10, r1=110, w=7))
            if opp.hp <= 0:
                opp.state, opp.st = 'ko', 0
                opp.vy, opp.vx = -10.0, (1 if opp.x >= self.x else -1) * 7.0
                opp.y = GROUND - 1
                self.set_state('idle')
                self.m.shake, self.m.hitstop = 14, 10
                return
        if t >= self.dom_total:
            self.set_state('idle')
            if opp.state == 'trapped':
                opp.set_state('hit')
                opp.stun = 24
                opp.vx = (1 if opp.x >= self.x else -1) * 6.0

    # ---- animacion y dibujo
    def current_frame(self):
        spr, st = self.spr, self.state

        def pick(name, idx):
            lst = spr.get(name) or spr['idle']
            return lst[int(clamp(idx, 0, len(lst) - 1))]

        if st == 'attack':
            mv = self.move
            lst = spr.get(mv['anim']) or spr['idle']
            n, su = len(lst), mv['startup']
            if mv['kind'] == 'multi':
                idx = (self.mt // 3) % n
            elif self.mt < su:
                idx = int(self.mt / float(max(1, su)) * (n - 1))
            else:
                idx = n - 1
            return lst[int(clamp(idx, 0, n - 1))]
        if st == 'hit':
            n = len(spr.get('hit') or [])
            usable = n - 1 if (self.ko_last and n > 1) else n
            if self.y < GROUND - 2:
                return pick('hit', usable - 1)
            return pick('hit', min(usable - 2 if usable >= 3 else usable - 1, self.st // 6))
        if st == 'ko':
            return pick('hit', 99)
        if st == 'trapped':
            return pick('hit', 0)
        if st == 'domain':
            lst = spr.get('special') or spr['idle']
            return lst[min(len(lst) - 1, 1 + (self.st // 12) % 2)]
        if self.y < GROUND - 2 or st == 'jump':
            vy = self.vy
            return pick('jump', 0 if vy < -8 else 1 if vy < -1 else 2 if vy < 4 else 3)
        if st == 'block':
            return pick('crouch', 1)
        if st == 'crouch':
            return pick('crouch', min(1, self.st // 5))
        if st == 'run':
            lst = spr.get('run') or spr['idle']
            return lst[(self.at // 4) % len(lst)]
        if st == 'walk':
            lst = spr.get('walk') or spr['idle']
            return lst[(self.at // 6) % len(lst)]
        lst = spr['idle']
        return lst[(self.at // 9) % len(lst)]

    def draw(self, cv):
        fr = self.current_frame()
        img, ax = fr.get(self.facing)
        x, y = int(self.x - ax), int(self.y - fr.h)
        if self.state == 'ko' and not self.custom and self.y >= GROUND - 1 and self.vy == 0:
            if self.ko_img is None:
                self.ko_img = pygame.transform.rotate(img, 90 if self.facing == 1 else -90)
            img = self.ko_img
            x, y = int(self.x - (119 if self.facing == 1 else 97)), int(self.y - 124)
        if self.state not in ('ko',):
            glow(cv, self.x, self.y - 90, 112, light(self.c['ult']['color'], 0.25), 0.3)
        if self.buff > 0:
            glow(cv, self.x, self.y - 95, 120 + int(8 * math.sin(self.at * 0.2)), self.c['ult']['color'])
        if self.state == 'block':
            glow(cv, self.x + self.facing * 42, self.y - 100, 74, (110, 170, 255))
        cv.blit(img, (x, y))
        if self.flash > 0:
            glow(cv, self.x, self.y - 100, 70, (255, 255, 255))


# ------------------------------------------------------------------ PARTIDA
class Cinematic(object):
    """Cinematica a pantalla completa: secuencia de JPG + audio WAV en assets/cinematicas/<nombre>/."""

    def __init__(self, name):
        self.folder = os.path.join(ASSETS, 'cinematicas', name)
        self.n, self.fps, self.ok = 0, 30.0, False
        try:
            with open(os.path.join(self.folder, 'info.json'), 'r') as fh:
                info = json.load(fh)
            self.n, self.fps = int(info['frames']), float(info.get('fps', 30))
            self.ok = self.n > 0
        except Exception:
            pass
        self.total = int(self.n * FPS / self.fps) if self.ok else 0
        self.t, self.idx, self.img, self.snd = 0, -1, None, None
        self.dark = self.fade = None

    def start(self):
        try:
            self.snd = pygame.mixer.Sound(os.path.join(self.folder, 'audio.wav'))
            self.snd.play()
        except Exception:
            self.snd = None

    def stop(self):
        if self.snd is not None:
            try:
                self.snd.stop()
            except Exception:
                pass

    @property
    def done(self):
        return self.t >= self.total

    def update(self):
        self.t += 1

    def draw(self, scr):
        idx = min(self.n - 1, int(self.t * self.fps / FPS))
        if idx != self.idx:
            self.idx = idx
            try:
                self.img = pygame.image.load(os.path.join(self.folder, 'f_%04d.jpg' % (idx + 1))).convert()
            except Exception:
                return
        fr = self.img
        if self.dark is None:
            self.dark = pygame.Surface((W, H), pygame.SRCALPHA)
            self.dark.fill((0, 0, 0, 125))
            self.fade = pygame.Surface((W, H), pygame.SRCALPHA)
        # fondo: el mismo cuadro, muy reducido y estirado (efecto desenfocado) y oscurecido
        bg = pygame.transform.smoothscale(pygame.transform.smoothscale(fr, (18, 32)), (W, H))
        scr.blit(bg, (0, 0))
        scr.blit(self.dark, (0, 0))
        vw = int(H * fr.get_width() / float(fr.get_height()))
        scr.blit(pygame.transform.smoothscale(fr, (vw, H)), ((W - vw) // 2, 0))
        x0 = (W - vw) // 2
        for k, a in enumerate((255, 190, 120)):
            c = (255, 150 + k * 20, 60)
            pygame.draw.line(scr, c, (x0 - 1 - k * 2, 0), (x0 - 1 - k * 2, H), 2)
            pygame.draw.line(scr, c, (x0 + vw + k * 2, 0), (x0 + vw + k * 2, H), 2)
        text(scr, 'ENTER: saltar', 22, (230, 230, 240), (W - 20, H - 30), 'topright')
        a = 0
        if self.t < 12:
            a = int(255 * (1 - self.t / 12.0))
        elif self.t > self.total - 14:
            a = int(255 * (self.t - (self.total - 14)) / 14.0)
        if a > 0:
            self.fade.fill((0, 0, 0, min(255, a)))
            scr.blit(self.fade, (0, 0))


class Match(object):
    def __init__(self, g, c1, c2, mode, level, stage):
        self.g, self.mode, self.level = g, mode, level
        self.stage = stage
        self.f = [Fighter(self, 0, c1, 400, 1), Fighter(self, 1, c2, W - 400, -1)]
        self.f[0].opp, self.f[1].opp = self.f[1], self.f[0]
        self.ctrl = [KeyCtrl(P1_KEYS) if mode in ('1p', '2p', 'train') else AI(level),
                     KeyCtrl(P2_KEYS) if mode == '2p' else Dummy() if mode == 'train' else AI(level)]
        self.projs, self.fx, self.parts = [], [], []
        self.hitstop, self.shake, self.flash, self.t = 0, 0.0, 0, 0
        self.round, self.phase, self.pt = 1, 'intro', 0
        self.timer = 99 * FPS
        self.winner = None
        self.paused = False
        self.cine = None
        if mode == 'train':
            self.timer = 99 * FPS

    # ---- efectos
    def spark(self, x, y, color, n=10, big=True):
        for _ in range(n):
            a = random.uniform(0, math.tau)
            v = random.uniform(2, 9 if big else 5)
            self.parts.append([x, y, math.cos(a) * v, math.sin(a) * v - 1, random.randint(12, 24), 24, color,
                               random.randint(3, 6), 0.25])
        self.fx.append(Fx('ring', x, y, 10, color=color, r0=6, r1=46 if big else 26, w=4))

    def sfx(self, name):
        self.g.sfx.play(name)

    def begin_cine(self, key):
        if not key or not self.g.cine_on:
            return False
        c = Cinematic(key)
        if not c.ok:
            return False
        c.start()
        self.cine = c
        return True

    def end_cine(self):
        if self.cine is not None:
            self.cine.stop()
            self.cine = None
            self.flash = 6

    def new_round(self):
        a, b = self.f
        a.reset(400, 1)
        b.reset(W - 400, -1)
        self.projs, self.fx, self.parts = [], [], []
        self.timer = 99 * FPS
        self.phase, self.pt, self.winner = 'intro', 0, None

    def domain_caster(self):
        for f in self.f:
            if f.state == 'domain':
                return f
        return None

    # ---- logica
    def update(self, keys):
        self.t += 1
        if self.cine is not None:
            self.cine.update()
            if self.cine.done:
                self.end_cine()
            return
        for fx in self.fx:
            fx.update()
        self.fx = [e for e in self.fx if e.life > 0]
        for p in self.parts:
            p[0] += p[2]
            p[1] += p[3]
            p[3] += p[8]
            p[4] -= 1
        self.parts = [p for p in self.parts if p[4] > 0]
        self.shake = self.shake * 0.82 if self.shake > 0.6 else 0.0
        if self.flash > 0:
            self.flash -= 1
        if self.hitstop > 0:
            self.hitstop -= 1
            return
        ph = self.phase
        if ph == 'intro':
            self.pt += 1
            for f in self.f:
                f.at += 1
            if self.pt >= 130:
                self.phase, self.pt = 'fight', 0
            return
        if ph == 'over':
            return
        if ph == 'ko' and self.pt < 60 and self.t % 3:      # camara lenta al K.O.
            self.pt += 1
            return
        blank = Inp()
        for i, f in enumerate(self.f):
            inp = self.ctrl[i].read(keys, f, f.opp) if ph == 'fight' else blank
            f.update(inp, f.opp)
        self.separate()
        for p in self.projs:
            p.update()
        self.clash()
        self.projs = [p for p in self.projs if not p.dead]
        if ph == 'ko':
            self.pt += 1
            if self.pt >= 170:
                if self.f[0].wins >= 2 or self.f[1].wins >= 2:
                    self.phase = 'over'
                else:
                    self.round += 1
                    self.new_round()
            return
        # --- fase de pelea
        if self.mode == 'train':
            for f in self.f:
                if f.hp < f.maxhp * 0.3 and f.state != 'ko':
                    f.hp = float(f.maxhp)
                    f.ghost = f.hp
                f.ce = min(100.0, f.ce + 0.25)
                if f.state == 'ko':
                    f.reset(f.x, f.facing)
            return
        if self.domain_caster() is None:
            self.timer -= 1
        dead = [f for f in self.f if f.state == 'ko']
        if dead or self.timer <= 0:
            if dead and len(dead) == 1:
                w = dead[0].opp
            elif dead:
                w = None
            else:
                a, b = self.f
                w = a if a.hp > b.hp else b if b.hp > a.hp else None
            self.winner = w
            if w is not None:
                w.wins += 1
            self.phase, self.pt = 'ko', 0

    def separate(self):
        a, b = self.f
        bad = ('trapped', 'domain')
        if abs(a.y - b.y) < 90 and a.state not in bad and b.state not in bad:
            d = b.x - a.x
            if abs(d) < 58:
                push = (58 - abs(d)) / 2.0
                s = 1 if d >= 0 else -1
                a.x = clamp(a.x - s * push, ARENA_L, ARENA_R)
                b.x = clamp(b.x + s * push, ARENA_L, ARENA_R)

    def clash(self):
        ps = [p for p in self.projs if p.kind in PROJ_KINDS and not p.dead]
        for i in range(len(ps)):
            for j in range(i + 1, len(ps)):
                a, b = ps[i], ps[j]
                if a.o is b.o or a.dead or b.dead:
                    continue
                if abs(a.x - b.x) < (a.size + b.size) * 0.5 and abs(a.y - b.y) < (a.size + b.size) * 0.5:
                    self.spark((a.x + b.x) / 2, (a.y + b.y) / 2, (255, 255, 255), 14)
                    if not a.mv.get('pierce'):
                        a.dead = True
                    if not b.mv.get('pierce'):
                        b.dead = True

    # ---- dibujo
    def draw_domain_bg(self, cv, f):
        u, t, tot = f.ult, f.st, f.dom_total
        k = clamp(min(t / 18.0, (tot - t) / 18.0), 0.0, 1.0)
        col = u['color']
        ov = self.g.overlay
        ov.fill((dark(col, 0.22)[0], dark(col, 0.22)[1], dark(col, 0.22)[2], int(238 * k)))
        cv.blit(ov, (0, 0))
        dom = f.fx.get('domain')
        if dom is not None:      # escenario propio del Dominio (p. ej. el Acuario Sumergido de Dagon)
            top = GROUND + 6 - dom.get_height()
            dom.set_alpha(int(255 * k))
            cv.blit(dom, ((W - dom.get_width()) // 2, top))
            dom.set_alpha(255)
            fc = dark(col, 0.22)
            fade = pygame.Surface((W, 56), pygame.SRCALPHA)
            for yy in range(56):
                fade.fill((fc[0], fc[1], fc[2], int(238 * k * (1 - yy / 56.0))), (0, yy, W, 1))
            cv.blit(fade, (0, top))
            pygame.draw.rect(cv, dark(col, 0.45), (0, GROUND + 6, W, H - GROUND))
            pygame.draw.line(cv, light(col, 0.4), (0, GROUND + 6), (W, GROUND + 6), 3)
            return
        cx, cy = W // 2, GROUND - 170
        n = 28
        ray = mix(dark(col, 0.22), col, 0.5 * k)
        for i in range(n):
            a = i / float(n) * math.tau + t * 0.012
            w = 0.03 + 0.012 * math.sin(t * 0.1 + i)
            pts = [(cx, cy), (cx + math.cos(a - w) * 1100, cy + math.sin(a - w) * 1100),
                   (cx + math.cos(a + w) * 1100, cy + math.sin(a + w) * 1100)]
            pygame.draw.polygon(cv, ray, [(int(px), int(py)) for px, py in pts])
        ring = f.fx.get('ring')
        if ring is not None:
            rr = pygame.transform.rotate(ring, t * 1.5)
            cv.blit(rr, (cx - rr.get_width() // 2, cy - rr.get_height() // 2))
        else:
            for i in range(5):
                rad = (t * 4 + i * 80) % 400 + 40
                pygame.draw.circle(cv, light(col, 0.3), (cx, cy), rad, 3)
        pygame.draw.rect(cv, dark(col, 0.45), (0, GROUND, W, H - GROUND))
        pygame.draw.line(cv, light(col, 0.4), (0, GROUND), (W, GROUND), 3)

    def draw_beam(self, cv, f):
        mv = f.move
        ln = f.beam_len(mv)
        if ln < 4:
            return
        c, th = mv['color'], mv['th']
        x0 = f.x + f.facing * 30
        x = int(x0 if f.facing == 1 else x0 - ln)
        y = int(f.y - mv['y'] - th / 2.0)
        fl = 1.0 + 0.12 * math.sin(self.t * 1.3)
        h2 = int(th * fl)
        y2 = int(f.y - mv['y'] - h2 / 2.0)
        tmp = pygame.Surface((int(ln), h2 + 24), pygame.SRCALPHA)
        tmp.fill((c[0], c[1], c[2], 70))
        cv.blit(tmp, (x, y2 - 12))
        pygame.draw.rect(cv, c, (x, y2, int(ln), h2))
        pygame.draw.rect(cv, light(c, 0.6), (x, y2 + h2 // 5, int(ln), h2 * 3 // 5))
        pygame.draw.rect(cv, (255, 255, 255), (x, y2 + h2 * 2 // 5, int(ln), max(2, h2 // 5)))
        glow(cv, x0 + f.facing * 10, f.y - mv['y'], th * 1.1, c)

    def draw_world(self, cv):
        cv.blit(self.g.stages[self.stage], (0, 0))
        dom = self.domain_caster()
        if dom:
            self.draw_domain_bg(cv, dom)
        shadow = self.g.shadow
        for f in self.f:
            cv.blit(shadow, (int(f.x - shadow.get_width() / 2), GROUND - 8))
        order = sorted(self.f, key=lambda q: (q.state in ('attack', 'domain'), q.idx == 1))
        for f in order:
            f.draw(cv)
        for f in self.f:
            if f.state == 'attack' and f.move['kind'] == 'beam' and f.move['startup'] <= f.mt < f.move['startup'] + f.move['active']:
                self.draw_beam(cv, f)
        for p in self.projs:
            p.draw(cv)
        for e in self.fx:
            e.draw(cv)
        for p in self.parts:
            r = max(1, int(p[7] * p[4] / float(p[5])))
            pygame.draw.circle(cv, p[6], (int(p[0]), int(p[1])), r)

    def draw_hud(self, scr):
        D = pygame.draw
        keyname = ('T', 'I / Num0')
        for i, f in enumerate(self.f):
            left = i == 0
            bw, sl = 470, 20
            bx = 118 if left else W - 118 - bw
            col = f.c['ult']['color']
            px = 18 if left else W - 18 - 92
            D.rect(scr, dark(col, 0.4), (px - 4, 10, 100, 100))
            scr.blit(portrait(f.c, 92), (px, 14))
            D.rect(scr, light(col, 0.3), (px - 4, 10, 100, 100), 4)
            text(scr, f.c['name'].upper(), 32, (255, 255, 255), ((bx + sl + 6) if left else (bx + bw - sl - 6), 6),
                 'topleft' if left else 'topright')
            D.polygon(scr, (12, 10, 20), slant_poly(bx - 3, 38, bw + 6, 32, sl + 2, left))
            ratio, gr = clamp(f.hp / float(f.maxhp), 0, 1), clamp(f.ghost / float(f.maxhp), 0, 1)
            for r, c in ((gr, (235, 235, 240)),
                         (ratio, (80, 220, 95) if ratio > 0.5 else (245, 205, 45) if ratio > 0.25 else (240, 65, 55))):
                w = int(bw * r)
                if w > 2:
                    xx = bx if left else bx + bw - w
                    D.polygon(scr, c, slant_poly(xx, 41, w, 26, sl, left))
                    if c != (235, 235, 240):
                        D.polygon(scr, light(c, 0.45), slant_poly(xx + (3 if left else 0), 41, w - 3, 8, sl * 0.3, left))
            for k in range(1, 10):
                xk = bx + bw * k / 10.0
                if left:
                    D.line(scr, (10, 8, 16), (int(xk + sl), 41), (int(xk), 67), 2)
                else:
                    D.line(scr, (10, 8, 16), (int(xk), 41), (int(xk - sl), 67), 2)
            D.polygon(scr, light(col, 0.5), slant_poly(bx - 3, 38, bw + 6, 32, sl + 2, left), 3)
            cw = 300
            cxx = bx if left else bx + bw - cw
            D.polygon(scr, (12, 10, 20), slant_poly(cxx - 2, 74, cw + 4, 16, 9, left))
            w = int(cw * f.ce / 100.0)
            full = f.ce >= 99.9
            colce = light(col, 0.25)
            if full and (self.t // 6) % 2:
                colce = (255, 255, 255)
            if w > 2:
                D.polygon(scr, colce, slant_poly(cxx if left else cxx + cw - w, 76, w, 12, 8, left))
            if full:
                text(scr, 'DOMINIO LISTO [%s]' % (keyname[i] if self.mode == '2p' or left else '-'), 20,
                     (255, 255, 255), (cxx + (cw + 22 if left else -22), 74), 'topleft' if left else 'topright')
            for r in range(2):
                cx = (bx + 16 + r * 26) if left else (bx + bw - 16 - r * 26)
                c2 = (255, 210, 60) if r < f.wins else (50, 48, 66)
                D.polygon(scr, c2, [(cx, 94), (cx + 9, 103), (cx, 112), (cx - 9, 103)])
                D.polygon(scr, (255, 255, 255), [(cx, 94), (cx + 9, 103), (cx, 112), (cx - 9, 103)], 1)
            if f.combo >= 2 and self.domain_caster() is None:
                text(scr, '%d HITS' % f.combo, 46, (255, 225, 90), ((60 if left else W - 60), 190), 'topleft' if left else 'topright')
            if f.buff > 0:
                text(scr, 'PODER +', 22, light(col, 0.3), (bx if left else bx + bw, 118), 'topleft' if left else 'topright')
        t = max(0, int(math.ceil(self.timer / float(FPS)))) if self.mode != 'train' else 0
        hexa = [(W // 2 - 54, 50), (W // 2 - 32, 12), (W // 2 + 32, 12), (W // 2 + 54, 50), (W // 2 + 32, 88), (W // 2 - 32, 88)]
        D.polygon(scr, (12, 10, 20), hexa)
        D.polygon(scr, (255, 225, 140), hexa, 3)
        text(scr, '--' if self.mode == 'train' else '%02d' % t, 60, (255, 255, 255), (W // 2, 51), 'center')
        text(scr, self.g.stage_names[self.stage], 20, (235, 235, 245), (W // 2, 96), 'midtop')

    def draw_banner(self, scr):
        c = (W // 2, 270)
        if self.phase == 'intro':
            if self.pt < 70:
                text(scr, 'RONDA %d' % self.round, 110, (255, 255, 255), c, 'center', off=5)
            elif self.pt < 125:
                text(scr, '¡PELEA!', 130, (255, 210, 60), c, 'center', off=6)
        elif self.phase == 'ko':
            if self.winner is None:
                text(scr, 'EMPATE', 120, (255, 255, 255), c, 'center', off=5)
            else:
                text(scr, 'K.O.' if self.winner.opp.hp <= 0 else 'TIEMPO', 140, (255, 70, 60), c, 'center', off=6)
                if self.pt > 50:
                    text(scr, self.winner.c['name'] + ' gana la ronda', 44, (255, 255, 255), (W // 2, 360), 'center')
        elif self.phase == 'over':
            w = self.f[0] if self.f[0].wins >= 2 else self.f[1]
            text(scr, '¡%s GANA!' % w.c['name'].upper(), 96, (255, 215, 70), (W // 2, 250), 'center', off=5)
            text(scr, 'ENTER: revancha     ESC: seleccionar personajes', 38, (255, 255, 255), (W // 2, 340), 'center')
        dom = self.domain_caster()
        if dom:
            u, t = dom.ult, dom.st
            k = clamp(min(t / 14.0, (dom.dom_total - t) / 14.0), 0.0, 1.0)
            xoff = int((1 - clamp(t / 18.0, 0, 1)) * -500)
            text(scr, 'EXPANSIÓN DE DOMINIO' if u['dom'] else 'TÉCNICA MÁXIMA', 44, (255, 255, 255),
                 (W // 2 + xoff, 150), 'center', shadow=dark(u['color'], 0.6), off=3)
            text(scr, u['name'], 76, light(u['color'], 0.45), (W // 2 - xoff, 215), 'center',
                 shadow=dark(u['color'], 0.35), off=4)

    def draw(self, scr):
        if self.cine is not None:
            self.cine.draw(scr)
            return
        cv = self.g.canvas
        self.draw_world(cv)
        ox = oy = 0
        if self.shake > 0:
            ox, oy = int(random.uniform(-1, 1) * self.shake), int(random.uniform(-1, 1) * self.shake)
        scr.fill((0, 0, 0))
        scr.blit(cv, (ox, oy))
        scr.blit(self.g.vignette, (0, 0))
        if self.flash > 0:
            ov = self.g.overlay
            ov.fill((255, 255, 255, int(150 * self.flash / 6.0)))
            scr.blit(ov, (0, 0))
        self.draw_hud(scr)
        self.draw_banner(scr)
        if self.paused:
            ov = self.g.overlay
            ov.fill((0, 0, 0, 160))
            scr.blit(ov, (0, 0))
            text(scr, 'PAUSA', 120, (255, 255, 255), (W // 2, 300), 'center')
            text(scr, 'P: continuar    ESC: salir al menú', 36, (230, 230, 240), (W // 2, 390), 'center')
        elif self.mode == 'train':
            text(scr, 'ENTRENAMIENTO  -  P: pausa   ESC: salir', 24, (230, 230, 240), (W // 2, H - 30), 'center')



class SFX(object):
    """Efectos de sonido sintetizados por codigo (no necesita archivos). Si no hay audio, no hace nada."""

    def __init__(self):
        self.ok, self.mute, self.t = False, False, 0
        self.snd, self.last = {}, {}
        try:
            info = pygame.mixer.get_init()
            if not info or info[1] != -16:
                return
            self.rate, _, self.ch = info
            self.build()
            self.ok = True
        except Exception:
            self.ok = False

    def make(self, dur, fn):
        n = int(self.rate * dur)
        buf = array.array('h')
        for i in range(n):
            v = fn(i / float(self.rate), i / float(n))
            v = int(max(-1.0, min(1.0, v)) * 24000)
            for _ in range(self.ch):
                buf.append(v)
        return pygame.mixer.Sound(buffer=buf.tobytes())

    def build(self):
        tau, sin, rnd = math.tau, math.sin, random.uniform
        lp = [0.0]

        def low(p):
            lp[0] = lp[0] * 0.92 + rnd(-1, 1) * 0.08
            return lp[0] * 5.0

        S = self.snd
        S['hit'] = self.make(0.13, lambda t, p: (rnd(-1, 1) * 0.5 + sin(tau * (150 - 90 * p) * t) * 0.9) * (1 - p) ** 2)
        S['block'] = self.make(0.12, lambda t, p: (sin(tau * 820 * t) * 0.5 + sin(tau * 1230 * t) * 0.35 + rnd(-1, 1) * 0.1) * (1 - p) ** 3)
        S['shoot'] = self.make(0.17, lambda t, p: sin(tau * (1000 - 700 * p) * t) * 0.5 * (1 - p))
        S['boom'] = self.make(0.45, lambda t, p: (low(p) + sin(tau * 55 * t) * 0.7) * (1 - p) ** 1.5)
        S['beam'] = self.make(0.55, lambda t, p: (sin(tau * (180 + 120 * sin(tau * 9 * t)) * t) * 0.5 + rnd(-1, 1) * 0.15)
                              * min(1.0, p * 8) * (1 - p))
        S['domain'] = self.make(0.9, lambda t, p: sin(tau * (70 + 520 * p * p) * t) * 0.65 * (0.6 + 0.4 * sin(tau * 14 * t))
                                * min(1.0, p * 10) * (1 - p * 0.4))
        S['ko'] = self.make(0.7, lambda t, p: (sin(tau * (120 - 75 * p) * t) * 0.8 + rnd(-1, 1) * 0.35) * (1 - p) ** 1.5)
        S['jump'] = self.make(0.1, lambda t, p: sin(tau * (300 + 500 * p) * t) * 0.35 * (1 - p))
        S['heal'] = self.make(0.4, lambda t, p: sin(tau * (523, 659, 784, 1047)[min(3, int(p * 4))] * t) * 0.4 * (1 - p))
        S['buff'] = self.make(0.3, lambda t, p: sin(tau * (400 + 800 * p) * t) * 0.4 * (1 - p))
        S['ui'] = self.make(0.05, lambda t, p: sin(tau * 880 * t) * 0.3 * (1 - p))
        S['ok'] = self.make(0.09, lambda t, p: sin(tau * 1250 * t) * 0.35 * (1 - p))
        for k in S:
            S[k].set_volume(0.5)

    def play(self, name):
        if not self.ok or self.mute:
            return
        if self.t - self.last.get(name, -99) < 3:
            return
        self.last[name] = self.t
        try:
            self.snd[name].play()
        except Exception:
            pass


# ------------------------------------------------------------------ JUEGO / MENUS
CONTROLS = [
    ('', 'JUGADOR 1', 'JUGADOR 2'),
    ('Mover', 'A / D', 'Flechas izq / der'),
    ('Saltar / Agacharse', 'W / S', 'Flechas arriba / abajo'),
    ('Ataque normal', 'F', 'K  (o Num 1)'),
    ('Ataque especial', 'G', 'L  (o Num 2)'),
    ('Habilidad', 'H', 'O  (o Num 3)'),
    ('Expansión de Dominio (barra llena)', 'T', 'I  (o Num 0)'),
    ('Bloquear (mantener)', 'R', 'U  (o Num 5)'),
]


class Game(object):
    MENU = ['1 JUGADOR  (vs CPU)', '2 JUGADORES', 'ENTRENAMIENTO', 'DEMO  CPU vs CPU', 'DIFICULTAD', 'CINEMÁTICAS', 'CONTROLES', 'SALIR']
    DESC = ['Pelea contra la CPU con el personaje que elijas.', 'Dos jugadores en el mismo teclado.',
            'Practica combos contra un muñeco que se cura solo.', 'Mira a dos personajes de la CPU pelear.',
            'Elige qué tan listo es el rival.  (izquierda / derecha)',
            'Activa o desactiva la cinemática del dominio de Jogo.  (izquierda / derecha)',
            'Teclas de ambos jugadores.', 'Cerrar el juego.']

    def __init__(self):
        try:
            pygame.mixer.pre_init(22050, -16, 1, 512)
        except Exception:
            pass
        pygame.init()
        try:
            self.screen = pygame.display.set_mode((W, H), pygame.SCALED | pygame.RESIZABLE)
        except Exception:
            self.screen = pygame.display.set_mode((W, H))
        pygame.display.set_caption('JUJUTSU FIGHTERS  -  juego de fans')
        self.clock = pygame.time.Clock()
        self.sfx = SFX()
        self.stage_pick = -1
        self.cine_on = True
        self.canvas = pygame.Surface((W, H))
        self.overlay = pygame.Surface((W, H), pygame.SRCALPHA)
        self.shadow = pygame.Surface((120, 26), pygame.SRCALPHA)
        for i in range(8, 0, -1):
            pygame.draw.ellipse(self.shadow, (0, 0, 0, 22 + (8 - i) * 9), (60 - i * 7, 13 - i, i * 14, i * 2 + 2))
        self.stages = [build_stage(i) for i in range(len(STAGES))]
        self.stage_names = [s[0] for s in STAGES]
        self.scene, self.menu_i, self.level, self.mode = 'title', 0, 1, '1p'
        self.cols = 10
        self.sel = None
        self.match = None
        self.t = 0
        self.last_pair = None
        self.bg_title = build_stage(2)
        self.embers = []
        self.show_ids = [c['id'] for c in ROSTER if os.path.isfile(os.path.join(ASSETS, c['id'], 'portrait_big.png'))]
        v = pygame.Surface((W, H), pygame.SRCALPHA)
        d = 7
        for i in range(46):
            pygame.draw.rect(v, (0, 0, 0, int(165 * (1 - i / 46.0) ** 2.3)), (int(i * d * 1.78), i * d, W - 2 * int(i * d * 1.78), H - 2 * i * d), d * 2)
        self.vignette = v

    # ---- seleccion
    def start_select(self, mode):
        self.mode = mode
        self.scene = 'select'
        self.sel = dict(cur=[3, 13], lock=[False, False], pick=0, go=0)

    def sel_move(self, who, dx, dy):
        cur = self.sel['cur']
        n = len(ROSTER)
        i = cur[who]
        r, c = divmod(i, self.cols)
        c = (c + dx) % self.cols
        r = (r + dy) % ((n + self.cols - 1) // self.cols)
        cur[who] = min(n - 1, r * self.cols + c)

    def sel_confirm(self, who):
        self.sel['lock'][who] = True
        if self.mode != '2p':
            self.sel['pick'] = 1
        if all(self.sel['lock']):
            self.sel['go'] = 40

    def sel_cancel(self, who):
        s = self.sel
        if self.mode == '2p':
            s['lock'][who] = False
        else:
            if s['lock'][1]:
                s['lock'][1] = False
            elif s['lock'][0]:
                s['lock'][0] = False
            s['pick'] = 0 if not s['lock'][0] else 1
        s['go'] = 0

    def start_match(self):
        c1, c2 = ROSTER[self.sel['cur'][0]], ROSTER[self.sel['cur'][1]]
        self.last_pair = (c1, c2)
        self.match = Match(self, c1, c2, self.mode, self.level, self.stage_pick if self.stage_pick >= 0 else random.randrange(len(STAGES)))
        self.scene = 'match'

    # ---- eventos
    def on_key(self, k):
        sc = self.scene
        if k == pygame.K_m:
            self.sfx.mute = not self.sfx.mute
            return False
        if k == pygame.K_F11:
            try:
                pygame.display.toggle_fullscreen()
            except Exception:
                pass
            return False
        if sc in ('title', 'select', 'controls'):
            self.sfx.play('ok' if k in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_f) else 'ui')
        if sc == 'title':
            if k in (pygame.K_UP, pygame.K_w):
                self.menu_i = (self.menu_i - 1) % len(self.MENU)
            elif k in (pygame.K_DOWN, pygame.K_s):
                self.menu_i = (self.menu_i + 1) % len(self.MENU)
            elif k in (pygame.K_LEFT, pygame.K_a, pygame.K_RIGHT, pygame.K_d) and self.menu_i in (4, 5):
                step = -1 if k in (pygame.K_LEFT, pygame.K_a) else 1
                if self.menu_i == 4:
                    self.level = (self.level + step) % 3
                else:
                    self.cine_on = not self.cine_on
            elif k in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_f):
                i = self.menu_i
                if i == 0:
                    self.start_select('1p')
                elif i == 1:
                    self.start_select('2p')
                elif i == 2:
                    self.start_select('train')
                elif i == 3:
                    self.start_select('cpu')
                elif i == 4:
                    self.level = (self.level + 1) % 3
                elif i == 5:
                    self.cine_on = not self.cine_on
                elif i == 6:
                    self.scene = 'controls'
                else:
                    return True
            elif k == pygame.K_ESCAPE:
                return True
        elif sc == 'controls':
            if k in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_SPACE):
                self.scene = 'title'
        elif sc == 'select':
            s = self.sel
            if k == pygame.K_ESCAPE:
                if any(s['lock']):
                    s['lock'] = [False, False]
                    s['pick'], s['go'] = 0, 0
                else:
                    self.scene = 'title'
                return False
            if s['go']:
                return False
            if k == pygame.K_TAB:
                self.stage_pick = (self.stage_pick + 2) % (len(STAGES) + 1) - 1
                return False
            if self.mode == '2p':
                nav1 = {pygame.K_a: (-1, 0), pygame.K_d: (1, 0), pygame.K_w: (0, -1), pygame.K_s: (0, 1)}
                nav2 = {pygame.K_LEFT: (-1, 0), pygame.K_RIGHT: (1, 0), pygame.K_UP: (0, -1), pygame.K_DOWN: (0, 1)}
                if k in nav1 and not s['lock'][0]:
                    self.sel_move(0, *nav1[k])
                elif k in nav2 and not s['lock'][1]:
                    self.sel_move(1, *nav2[k])
                elif k == pygame.K_f and not s['lock'][0]:
                    self.sel_confirm(0)
                elif k in (pygame.K_k, pygame.K_KP1, pygame.K_RETURN) and not s['lock'][1]:
                    self.sel_confirm(1)
                elif k == pygame.K_g:
                    self.sel_cancel(0)
                elif k in (pygame.K_l, pygame.K_KP2):
                    self.sel_cancel(1)
                elif k == pygame.K_r:
                    for w in (0, 1):
                        if not s['lock'][w]:
                            s['cur'][w] = random.randrange(len(ROSTER))
            else:
                who = s['pick']
                nav = {pygame.K_a: (-1, 0), pygame.K_d: (1, 0), pygame.K_w: (0, -1), pygame.K_s: (0, 1),
                       pygame.K_LEFT: (-1, 0), pygame.K_RIGHT: (1, 0), pygame.K_UP: (0, -1), pygame.K_DOWN: (0, 1)}
                if k in nav:
                    self.sel_move(who, *nav[k])
                elif k in (pygame.K_f, pygame.K_RETURN, pygame.K_SPACE, pygame.K_k):
                    if not s['lock'][who]:
                        self.sel_confirm(who)
                elif k in (pygame.K_g, pygame.K_BACKSPACE):
                    self.sel_cancel(who)
                elif k == pygame.K_r:
                    s['cur'][who] = random.randrange(len(ROSTER))
        elif sc == 'match':
            m = self.match
            if m.cine is not None:
                if k in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_ESCAPE, pygame.K_f):
                    m.end_cine()
                return False
            if k == pygame.K_ESCAPE:
                self.scene = 'select'
                self.sel['lock'] = [False, False]
                self.sel['pick'], self.sel['go'] = 0, 0
            elif k == pygame.K_p and m.phase != 'over':
                m.paused = not m.paused
            elif k == pygame.K_RETURN and m.phase == 'over':
                self.start_match()
        return False

    # ---- bucle
    def update(self, keys):
        self.t += 1
        self.sfx.t += 1
        if self.scene in ('title', 'select', 'controls'):
            for _ in range(2):
                self.embers.append([random.uniform(0, W), H + 8, random.uniform(-0.6, 0.6), random.uniform(-3.2, -1.0),
                                    random.uniform(1.5, 4.0), random.randint(120, 260)])
            for e in self.embers:
                e[0] += e[2] + math.sin(e[1] * 0.02) * 0.4
                e[1] += e[3]
                e[5] -= 1
            self.embers = [e for e in self.embers if e[5] > 0 and e[1] > -10][-260:]
        if self.scene == 'match':
            if not self.match.paused:
                self.match.update(keys)
        elif self.scene == 'select' and self.sel['go']:
            self.sel['go'] -= 1
            if self.sel['go'] == 0:
                self.start_match()

    def run(self):
        while True:
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    return
                if e.type == pygame.KEYDOWN and self.on_key(e.key):
                    return
            keys = pygame.key.get_pressed()
            self.update(keys)
            self.draw()
            pygame.display.flip()
            self.clock.tick(FPS)

    # ---- pantallas
    def draw(self):
        sc, scr = self.scene, self.screen
        if sc == 'match':
            self.match.draw(scr)
        elif sc == 'select':
            self.draw_select(scr)
        elif sc == 'controls':
            self.draw_controls(scr)
        else:
            self.draw_title(scr)

    def draw_title(self, scr):
        t = self.t
        scr.blit(self.bg_title, (0, 0))
        ov = self.overlay
        ov.fill((0, 0, 0, 0))
        pygame.draw.rect(ov, (6, 2, 12, 120), (0, 0, W, H))
        pygame.draw.polygon(ov, (8, 4, 18, 185), [(700, 0), (W, 0), (W, H), (560, H)])
        pygame.draw.polygon(ov, (255, 70, 60, 70), [(694, 0), (704, 0), (564, H), (554, H)])
        scr.blit(ov, (0, 0))
        glow(scr, 960, 330, 330, (255, 80, 50), 0.38)
        for e in self.embers:
            r = max(1, int(e[4] * min(1.0, e[5] / 90.0)))
            pygame.draw.circle(scr, (255, 150 + int(80 * (e[4] / 4.0)), 50), (int(e[0]), int(e[1])), r)
        # arte grande del personaje (rotando)
        ids = self.show_ids
        if ids:
            slot, ph = divmod(t, 210)
            cid = ids[slot % len(ids)]
            img = big_portrait(cid)
            if img is not None:
                a = 255
                if ph < 24:
                    a = int(255 * ph / 24.0)
                elif ph > 186:
                    a = int(255 * (210 - ph) / 24.0)
                img.set_alpha(a)
                scr.blit(img, (985 - img.get_width() // 2 + int(math.sin(t * 0.02) * 6), H - 40 - img.get_height()))
                img.set_alpha(255)
                if a > 120:
                    text(scr, CBYID[cid]['name'].upper(), 40, (255, 255, 255), (W - 40, 22), 'topright', shadow=(120, 20, 30), off=3)
        # logo
        glow(scr, 330, 170, 300, (150, 60, 255), 0.30)
        pulse = int(math.sin(t * 0.05) * 3)
        text(scr, 'JUJUTSU', 150, (255, 255, 255), (66, 40 + pulse), shadow=(140, 40, 220), off=7)
        text(scr, 'FIGHTERS', 150, (255, 88, 58), (66, 158 - pulse), shadow=(100, 8, 28), off=7)
        pygame.draw.polygon(scr, (255, 70, 60), [(70, 300), (560, 300), (548, 308), (70, 308)])
        text(scr, 'JUEGO DE PELEA  -  30 PERSONAJES', 24, (230, 230, 245), (72, 314))
        # menu
        ov.fill((0, 0, 0, 0))
        y0 = 350
        for i in range(len(self.MENU)):
            sel = i == self.menu_i
            x = 70 + (16 if sel else 0)
            y = y0 + i * 40 - i * 4
            col = (255, 60, 70, 235) if sel else (18, 14, 28, 175)
            pygame.draw.polygon(ov, col, slant_poly(x, y, 440, 34, 16))
            if sel:
                pygame.draw.polygon(ov, (255, 200, 120, 255), slant_poly(x, y, 440, 34, 16), 2)
        scr.blit(ov, (0, 0))
        for i, item in enumerate(self.MENU):
            sel = i == self.menu_i
            lab = item
            if i == 4:
                lab = 'DIFICULTAD:  < %s >' % ('FÁCIL', 'NORMAL', 'DIFÍCIL')[self.level]
            elif i == 5:
                lab = 'CINEMÁTICAS:  < %s >' % ('SÍ' if self.cine_on else 'NO')
            text(scr, lab, 30 if sel else 28, (255, 255, 255) if sel else (205, 205, 225),
                 (70 + (16 if sel else 0) + 34, y0 + i * 36 + 4), shadow=(0, 0, 0))
        pygame.draw.rect(scr, (8, 4, 16), (0, H - 40, W, 40))
        pygame.draw.line(scr, (255, 70, 60), (0, H - 40), (W, H - 40), 2)
        text(scr, self.DESC[self.menu_i], 22, (255, 225, 150), (24, H - 30))
        text(scr, 'M sonido   F11 pantalla completa', 20, (180, 180, 200), (W - 20, H - 28), 'topright')
        scr.blit(self.vignette, (0, 0))

    def draw_controls(self, scr):
        scr.blit(self.bg_title, (0, 0))
        self.overlay.fill((0, 0, 0, 170))
        scr.blit(self.overlay, (0, 0))
        text(scr, 'CONTROLES', 80, (255, 255, 255), (W // 2, 70), 'center')
        y = 150
        for a, b, c in CONTROLS:
            head = a == ''
            text(scr, a, 34, (230, 230, 245), (140, y))
            text(scr, b, 34, (255, 230, 90) if not head else (120, 220, 255), (700, y))
            text(scr, c, 34, (255, 230, 90) if not head else (255, 150, 110), (940, y))
            y += 56
        text(scr, 'Mantén la dirección para CORRER.  Saltar esquiva ondas de suelo, agacharse esquiva proyectiles altos.',
             24, (210, 210, 225), (W // 2, 590), 'center')
        text(scr, 'Ataque normal en el aire = patada aérea.  La energía maldita sube sola y al golpear.',
             24, (210, 210, 225), (W // 2, 622), 'center')
        text(scr, 'Barra llena: ¡Expansión de Dominio!   P = pausa   M = sonido   F11 = pantalla completa   TAB = escenario',
             24, (210, 210, 225), (W // 2, 654), 'center')
        text(scr, 'ESC: volver', 28, (255, 255, 255), (W // 2, H - 30), 'center')

    def draw_select(self, scr):
        s = self.sel
        scr.blit(self.bg_title, (0, 0))
        self.overlay.fill((0, 0, 0, 150))
        scr.blit(self.overlay, (0, 0))
        who = s['pick'] if self.mode != '2p' else 0
        title = 'ELIGE TU LUCHADOR'
        if self.mode != '2p':
            title = 'JUGADOR 1: ELIGE TU LUCHADOR' if not s['lock'][0] else 'ELIGE A TU RIVAL'
            if self.mode == 'cpu':
                title = 'DEMO: ELIGE LUCHADOR 1' if not s['lock'][0] else 'DEMO: ELIGE LUCHADOR 2'
        else:
            title = 'JUGADOR 1  vs  JUGADOR 2'
        text(scr, title, 54, (255, 255, 255), (W // 2, 14), 'midtop')
        sn = 'ALEATORIO' if self.stage_pick < 0 else self.stage_names[self.stage_pick]
        text(scr, 'ESCENARIO [TAB]: ' + sn, 22, (255, 230, 120), (W - 20, 18), 'topright')
        text(scr, 'SONIDO [M]: ' + ('SÍ' if (self.sfx.ok and not self.sfx.mute) else 'NO'), 22, (200, 200, 215), (20, 18))
        cw, ch, gap = 112, 122, 8
        x0 = (W - (self.cols * (cw + gap) - gap)) // 2
        y0 = 78
        for i, c in enumerate(ROSTER):
            r, col = divmod(i, self.cols)
            x, y = x0 + col * (cw + gap), y0 + r * (ch + gap)
            pygame.draw.rect(scr, dark(c['style']['outfit'], 0.5), (x, y, cw, ch))
            scr.blit(portrait(c, 96), (x + 8, y + 6))
            pygame.draw.rect(scr, (20, 20, 30), (x, y + ch - 20, cw, 20))
            text(scr, c['short'].upper(), 20, (255, 255, 255), (x + cw // 2, y + ch - 10), 'center', shadow=None)
            pygame.draw.rect(scr, (70, 70, 90), (x, y, cw, ch), 2)
        cols = ((90, 220, 255), (255, 150, 70))
        for p in (0, 1):
            i = s['cur'][p]
            if self.mode != '2p' and p == 1 and not s['lock'][0]:
                continue
            r, col = divmod(i, self.cols)
            x, y = x0 + col * (cw + gap), y0 + r * (ch + gap)
            off = 0 if p == 0 else 4
            pygame.draw.rect(scr, cols[p], (x - 3 + off, y - 3 + off, cw + 6 - off * 2, ch + 6 - off * 2),
                             6 if (p == 0 and not s['lock'][0]) or (p == 1 and not s['lock'][1]) else 10)
            tag = ('P1' if p == 0 else ('CPU' if self.mode in ('1p', 'train') else 'P2')) + (' OK' if s['lock'][p] else '')
            text(scr, tag, 22, cols[p], (x + 4 + off, y + 4 + off), shadow=(0, 0, 0))
        for p in (0, 1):
            if self.mode != '2p' and p == 1 and not s['lock'][0]:
                continue
            c = ROSTER[s['cur'][p]]
            left = p == 0
            px = 40 if left else W // 2 + 20
            pygame.draw.rect(scr, (0, 0, 0), (px, 468, W // 2 - 60, 228))
            pygame.draw.rect(scr, cols[p], (px, 468, W // 2 - 60, 228), 3)
            fr = Bank.preview(c)
            f = fr[(self.t // 9) % len(fr)]
            img, ax = f.get(1 if left else -1)
            scr.blit(img, (px + 100 - int(ax) + (0 if left else W // 2 - 260), 688 - f.h))
            tx = px + (210 if left else 20)
            text(scr, c['name'].upper(), 38, (255, 255, 255), (tx, 482))
            for k, (lab, val, mx) in enumerate((('VIDA', c['hp'], 1200), ('VELOCIDAD', c['spd'], 7.2), ('PODER', c['pw'], 1.2))):
                yy = 520 + k * 20
                text(scr, lab, 18, (200, 200, 215), (tx, yy), shadow=None)
                pygame.draw.rect(scr, (40, 40, 56), (tx + 110, yy + 3, 150, 11))
                pygame.draw.rect(scr, cols[p], (tx + 110, yy + 3, int(150 * clamp(val / float(mx), 0, 1)), 11))
            mv = c['moves']
            kk = ('F', 'G', 'H') if (left or self.mode != '2p') else ('K', 'L', 'O')
            for j, key in enumerate(('normal', 'special', 'skill')):
                text(scr, '%s  %s' % (kk[j], mv[key]['name']), 22, (255, 235, 120), (tx, 588 + j * 24), shadow=None)
            text(scr, '%s  %s' % ('T' if (left or self.mode != '2p') else 'I', c['ult']['name']), 22, light(c['ult']['color'], 0.4), (tx, 662), shadow=None)
        if s['go']:
            text(scr, '¡A PELEAR!', 80, (255, 220, 70), (W // 2, 440), 'center')
        else:
            hint = 'WASD/Flechas mover  -  F/ENTER aceptar  -  G volver  -  R aleatorio  -  ESC menú'
            text(scr, hint, 20, (210, 210, 225), (W // 2, H - 12), 'center', shadow=None)


def main():
    Game().run()
    pygame.quit()
    sys.exit()


if __name__ == '__main__':
    main()
