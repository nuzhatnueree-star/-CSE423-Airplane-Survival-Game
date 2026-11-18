import math
import os
import random
import sys
import time
from OpenGL.GL import *
from OpenGL.GLU import *
from OpenGL.GLUT import *
def safe_call(func, *args, **kwargs):
    try:
        if callable(func):
            return func(*args, **kwargs)
    except Exception:
        return None
# Global camera variables for viewing angle and position
camera_yaw = 0.0
camera_pitch = 20.0
camera_distance = 10.0

# Window dimensions
window_width = 800
window_height = 600


class Game:

    def __init__(self):
        # Environment grid size
        self.GRID_SIZE = 20
        # building heights
        self.terrain_grid = [[0] * self.GRID_SIZE for _ in range(self.GRID_SIZE)]
        # X and Y positions of rings to pass through
        self.ring_positions_x = [1, -2, 3, -4, -2, 0, 2]
        self.ring_positions_y = [2, 3, 10, 6, 7, 4, 1]
        # Rotation recovery speed when returning to neutral
        self.rotation_recovery_speed = 0.2
        # Number of rain drops
        self.RAIN_PARTICLE_COUNT = 200
        # Number of snowflakes
        self.SNOW_PARTICLE_COUNT = 500
        self.BOMB_BOX_COUNT = 10  # Number of destructible bomb boxes on ground.
        self.SKY_BOMB_COUNT = 5

        # Maximum plane rotation limits
        self.PLANE_MAX_ROLL = 11
        self.PLANE_MAX_PITCH = 10
        self.PLANE_MAX_YAW = 15
        # Collision detection distances
        self.COLLISION_DISTANCE_RING = 4.0
        self.RING_PASS_Z_THRESHOLD = 2.0
        self.RING_PASS_RADIUS = 1.5
        self.COLLISION_DISTANCE_BOMB = 1.0

        self.CANNON_WORLD_OFFSET_X = 0.9
        self.CANNON_WORLD_OFFSET_Y = 0.05
        self.CANNON_WORLD_OFFSET_Z = -0.6

        self.LOWER_GUN_WORLD_OFFSET_X = 0.0
        self.LOWER_GUN_WORLD_OFFSET_Y = -0.15
        self.LOWER_GUN_WORLD_OFFSET_Z = -0.9

        # Speed adjustment values
        self.SPEED_INCREMENT = 0.1
        self.SPEED_DECREMENT = 0.1
        self.MAX_SPEED = 0.7

        # Plane movement boundaries
        self.PLANE_BOUNDARY_X = 15
        self.PLANE_BOUNDARY_Y = 10

        # Flying past the mountains on either side is allowed briefly, but
        # if the dragon stays out there too long it dies. 9.0 matches the
        # mountain column position placed in environment() (lane_half_width
        # 8, so the mountains sit at grid position 9).
        self.MOUNTAIN_BOUNDARY_X = 9.0
        self.OUT_OF_BOUNDS_TIME_LIMIT = 10.0
        # Timestamp (game-elapsed seconds) when the dragon first flew past
        # the mountains; None while it's within bounds.
        self.out_of_bounds_since = None

        # Bullet speeds
        self.BULLET_SPEED = 0.5
        self.BOMB_SPEED = 0.1
        # Rain effect parameters
        self.RAIN_SPEED = 0.05
        self.RAIN_LENGTH = 0.2
        # Snow effect parameters
        self.SNOW_SPEED = 0.025

        # Recurring weather cycle: (phase name, duration in seconds).
        # A long, heavy snowfall rolls through, pauses, a rain+thunder storm
        # rolls in, pauses, then it repeats forever.
        self.WEATHER_CYCLE = [
            ("snow", 30.0),
            ("clear", 5.0),
            ("storm", 15.0),
            ("clear", 5.0),
        ]
        self.WEATHER_TOTAL = sum(duration for _, duration in self.WEATHER_CYCLE)
        self.weather_phase = "clear"

        # Sky bomb spawn boundaries
        self.SKY_BOMB_X_MIN = -3.0
        self.SKY_BOMB_X_MAX = 3.0

        # Game state variables
        self.LIVES = 3
        self.ring_count = 0
        self.score = 0
        self.bullets_fired = 0
        self.bullets_hit = 0
        # Tracking firing abuse (too many shots with no hits)
        self.misuse_fire = False
        self.misuse_time = 0.0
        self.collision_type = None
        # Day/night cycle settings
        self.auto_daynight = True
        self.force_daynight = None
        self.GAME_OVER = False
        # Countdown match clock: starts at ROUND_TIME_LIMIT seconds once the
        # game starts, ticks down every real second, and hits 0 -> game
        # over. Flying through a ring target (fire ring/cloud/leaf) adds
        # RING_TIME_BONUS seconds back.
        self.ROUND_TIME_LIMIT = 30.0
        self.RING_TIME_BONUS = 10.0
        self.time_remaining = self.ROUND_TIME_LIMIT
        self._last_timer_tick = None
        self.START = False
        self.CHEAT_MODE = False
        self.cheat_mode = False
        self.first_person = False
        # "i" info button on the start screen, and whether its instructions
        # panel is currently open
        self.INFO_ICON_RADIUS = 14
        self.INFO_ICON_MARGIN = 24
        self.SHOW_INSTRUCTIONS = False
        # Whether the current sky color counts as "night" - drives which
        # body (sun/moon) gets drawn. Recomputed every frame in display()
        # alongside the sky-color cycle.
        self.is_night = False
        # The sun/moon are real objects placed far out in world space
        # (not a 2D screen overlay), so they behave like actual distant
        # sky objects: real depth-tested geometry, so mountains/trees
        # correctly occlude them when in front, and fixed in the world
        # rather than tied to the dragon, so they only shift on screen
        # when the camera itself is rotated (arrow keys / first-person
        # toggle) - never from plain WASD steering, which only scrolls
        # the nearby terrain and never moves the camera.
        self.SKY_BODY_RADIUS = 10.0
        self.SUN_WORLD_POS = (-30.0, 26.0, -130.0)
        self.MOON_WORLD_POS = (30.0, 26.0, -130.0)
        # Plane movement speed (forward speed)
        self.speed = 0.3
        # Plane position in world space
        self.translation_x = 0.0
        self.translation_y = 0.0
        # Plane rotation angles
        self.rotation_x = 0.0
        self.rotation_y = 0.0
        self.rotation_z = 4.0
        # Camera zoom level
        self.zoom = 4.0

        self.window = None

        # Define patches along the flight path
        base_patches = [
            (-8.0, 2),
            (-20.0, 0),
            (-40.0, 3),
            (-60.0, 1),
            (-80.0, 5),
            (-100.0, 4),
            (-120.0, 2),
        ]
        shapes = ["ring", "square", "triangle"]
        # Each patch represents a section of the game world
        self.patches = [
            {"z": z, "n": n, "passed": False, "shape": random.choice(shapes)}
            for (z, n) in base_patches
        ]

        # Object lists for the game world
        self.bullets = []
        self.bombs = []
        self.sky_bombs = []
        self.bomb_boxes = []
        self.boat_bullets = []
        # Boats fire a volley of cannonballs at the dragon on this cadence
        self.BOAT_FIRE_INTERVAL = 20.0
        self.BOAT_BULLET_SPEED = 0.35
        self.last_boat_volley_time = 0.0
        # HUD warning shown when a boat cannonball is about to land. Object
        # speeds (BOAT_BULLET_SPEED and friends) are per-frame increments,
        # and the timer callback below drives the game at 60 FPS, so
        # converting "distance remaining" into real seconds needs this.
        self.GAME_FPS = 60
        self.BOAT_ATTACK_WARNING_LEAD = 2.0
        self.boat_attack_warning = False
        # Holding "H" raises a shield that blocks enemy hits, but holding
        # it past SHIELD_HOLD_LIMIT seconds overloads it and ends the game
        self.SHIELD_HOLD_LIMIT = 5.0
        self.shield_active = False
        self.shield_key_down = False
        self.shield_press_start = None
        self.rain = []
        self.RAINING = True
        self.snow = []
        self.SNOWING = False
        self.rot = False
        self.TIME = 0
        # Time tracking for game elapsed time
        self.game_start_time = time.time()

    def init_rain(self):
        """Initialize rain particles at random positions in the game world"""
        self.rain = []
        for _ in range(self.RAIN_PARTICLE_COUNT):
            self.rain.append(
                [
                    random.uniform(-20, 20),
                    random.uniform(0, 20),
                    random.uniform(-20, 20),
                ]
            )

    def drawRain(self):
        """Draw rain effect as falling particles and update their positions"""
        if not self.RAINING:
            return
        for rain_particle in self.rain:
            glPushMatrix()
            glTranslatef(rain_particle[0], rain_particle[1], rain_particle[2])
            glColor3f(0.7, 0.7, 1.0)  # Light blue color for rain
            glutSolidSphere(0.05, 8, 8)  # Small sphere instead of line
            glPopMatrix()
            # Move rain downward
            rain_particle[1] -= self.RAIN_SPEED
            # Reset rain particle to top when it goes below screen
            if rain_particle[1] < -5:
                rain_particle[1] = 20

    def init_snow(self):
        """Initialize snowflakes at random positions in the game world"""
        self.snow = []
        for _ in range(self.SNOW_PARTICLE_COUNT):
            self.snow.append(
                [
                    random.uniform(-20, 20),  # base x (sways around this)
                    random.uniform(0, 20),  # y
                    random.uniform(-20, 20),  # z
                    random.uniform(0, math.pi * 2),  # sway phase
                ]
            )

    def drawSnow(self):
        """Draw snow effect as gently swaying falling flakes and update them"""
        if not self.SNOWING:
            return
        elapsed_time = self.current_time_seconds()
        for flake in self.snow:
            glPushMatrix()
            sway = 0.5 * math.sin(elapsed_time * 1.2 + flake[3])
            glTranslatef(flake[0] + sway, flake[1], flake[2])
            glColor3f(1.0, 1.0, 1.0)  # White snowflakes
            glutSolidSphere(0.07, 8, 8)
            glPopMatrix()
            # Snow drifts down more slowly than rain
            flake[1] -= self.SNOW_SPEED
            if flake[1] < -5:
                flake[1] = 20

    def update_weather(self):
        """Figure out which weather phase we're in on the recurring cycle
        (snow -> pause -> storm -> pause -> repeat) and flip the relevant
        effect flags on/off for this frame."""
        elapsed = self.current_time_seconds() % self.WEATHER_TOTAL
        t = 0.0
        phase = self.WEATHER_CYCLE[-1][0]
        for name, duration in self.WEATHER_CYCLE:
            if elapsed < t + duration:
                phase = name
                break
            t += duration
        self.weather_phase = phase
        self.RAINING = phase == "storm"
        self.SNOWING = phase == "snow"

    def thunder_flash_active(self, elapsed_time):
        """Deterministic double-flash lightning pattern, repeating every 4s."""
        cycle = elapsed_time % 4.0
        return cycle < 0.12 or 0.25 < cycle < 0.33

    def draw_lightning_bolt(self, elapsed_time):
        """Draw a jagged bolt of lightning across the storm sky."""
        flash_cycle_index = int(elapsed_time / 4.0)
        seed = math.sin(flash_cycle_index * 12.9898) * 43758.5453
        seed -= math.floor(seed)
        bolt_x = -8.0 + seed * 16.0
        top_y, bottom_y = 22.0, 4.0
        bolt_z = -18.0
        segments = 6

        glDisable(GL_LIGHTING)
        glDisable(GL_CULL_FACE)
        glLineWidth(4.0)
        glColor3f(1.0, 1.0, 0.9)
        glBegin(GL_LINE_STRIP)
        for i in range(segments + 1):
            frac = i / segments
            y = top_y - frac * (top_y - bottom_y)
            jag = math.sin((flash_cycle_index * 3 + i) * 7.31) * 0.8
            glVertex3f(bolt_x + jag, y, bolt_z)
        glEnd()
        glLineWidth(1.0)
        glEnable(GL_CULL_FACE)
        glEnable(GL_LIGHTING)

    def init_bomb_boxes(self):
        """Initialize boat obstacles, scattered on the river"""
        self.bomb_boxes = []
        river_half_width = 8  # matches lane_half_width used for the river
        for _ in range(self.BOMB_BOX_COUNT):
            self.bomb_boxes.append(
                [
                    random.uniform(-(river_half_width - 1), river_half_width - 1),
                    0.5,
                    random.uniform(-100, 20),
                ]
            )

    def draw_bullets_and_bombs(self):
        """Draw all fireballs and ground bombs, update their positions"""
        # Draw fireballs (dragon fire-breath projectiles): a glowing white-hot
        # head with a flickering orange-to-red flame trailing behind it.
        # Flat single-sided shapes elsewhere on the model need culling and
        # lighting disabled to look right from every angle - these are solid
        # cones/spheres so normal lighting is fine and actually sells the glow.
        elapsed_time = self.current_time_seconds()
        glPushMatrix()
        glTranslated(self.translation_x, self.translation_y, 0)
        for i, bullet in enumerate(self.bullets):
            # Each fireball flickers on its own phase so a stream of shots
            # doesn't pulse in perfect unison.
            flicker = math.sin(elapsed_time * 22.0 + i * 2.1)
            glPushMatrix()
            glTranslated(bullet[0], bullet[1], bullet[2])

            # Outer red-orange flame - biggest and darkest, sets the
            # overall silhouette and trails back the furthest.
            glColor3f(0.9, 0.3 + 0.05 * flicker, 0.02)
            glPushMatrix()
            glScaled(0.16 + 0.02 * flicker, 0.16 + 0.02 * flicker, 0.55)
            glutSolidCone(0.5, 1.0, 10, 8)
            glPopMatrix()

            # Middle orange flame - smaller and shorter, nested inside the
            # outer layer so the hot core reads through.
            glColor3f(1.0, 0.55 + 0.08 * flicker, 0.05)
            glPushMatrix()
            glScaled(0.115 + 0.015 * flicker, 0.115 + 0.015 * flicker, 0.38)
            glutSolidCone(0.5, 1.0, 10, 8)
            glPopMatrix()

            # Inner core - brightest yellow, shortest of the three cones
            glColor3f(1.0, 0.85, 0.3 + 0.2 * abs(flicker))
            glPushMatrix()
            glScaled(0.07, 0.07, 0.22)
            glutSolidCone(0.5, 1.0, 8, 8)
            glPopMatrix()

            # Glowing white-hot head right at the leading edge
            glColor3f(1.0, 0.97, 0.7 + 0.2 * abs(flicker))
            glPushMatrix()
            glTranslated(0, 0, -0.12)
            glutSolidSphere(0.1, 10, 10)
            glPopMatrix()

            glPopMatrix()
            # Move fireball forward
            bullet[2] -= self.BULLET_SPEED
        glPopMatrix()

        # Draw bombs as speckled dragon eggs (cream ellipsoid shell with a
        # few darker mottled specks)
        glPushMatrix()
        glTranslated(self.translation_x, self.translation_y, 0)
        for bomb in self.bombs:
            glPushMatrix()
            glTranslated(bomb[0], bomb[1], bomb[2])

            glColor3f(0.93, 0.88, 0.72)  # cream eggshell
            glPushMatrix()
            glScaled(0.16, 0.22, 0.16)
            glutSolidSphere(1.0, 12, 12)
            glPopMatrix()

            glColor3f(0.55, 0.42, 0.25)  # darker speckles
            for sx, sy, sz in (
                (0.07, 0.12, 0.05),
                (-0.06, -0.02, 0.08),
                (0.02, -0.13, -0.07),
                (-0.08, 0.05, -0.06),
            ):
                glPushMatrix()
                glTranslated(sx, sy, sz)
                glutSolidSphere(0.02, 6, 6)
                glPopMatrix()

            glPopMatrix()
            # Move bomb downward
            bomb[1] -= self.BOMB_SPEED
        glPopMatrix()

        # Draw boat cannonballs: a dark iron core wrapped in a pulsing
        # red-orange glow with trailing sparks, sized up so it reads clearly
        # against any background - a plain dark sphere was too easy to miss.
        glPushMatrix()
        glTranslated(self.translation_x, self.translation_y, 0)
        for i, shot in enumerate(self.boat_bullets):
            pulse = 0.5 + 0.5 * math.sin(elapsed_time * 14.0 + i * 2.0)
            glPushMatrix()
            glTranslated(shot[0], shot[1], shot[2])

            # Outer glow - bright and pulsing, the main thing the eye catches
            glDisable(GL_LIGHTING)
            glColor3f(1.0, 0.25 + 0.15 * pulse, 0.03)
            glutSolidSphere(0.32, 14, 14)
            glEnable(GL_LIGHTING)

            # Dark iron cannonball core visible through the glow
            glColor3f(0.1, 0.1, 0.11)
            glutSolidSphere(0.17, 10, 10)

            # Bright white-hot highlight
            glColor3f(1.0, 0.95, 0.6)
            glPushMatrix()
            glTranslated(0.09, 0.09, -0.09)
            glutSolidSphere(0.06, 6, 6)
            glPopMatrix()

            glPopMatrix()

            # Trailing sparks behind the cannonball, along the path it came
            # from, so its motion reads even against busy scenery
            glDisable(GL_LIGHTING)
            for spark_index, t_back in enumerate((2.5, 5.0, 7.5)):
                fade = 1.0 - spark_index * 0.28
                glColor3f(1.0, 0.55 * fade, 0.08 * fade)
                glPushMatrix()
                glTranslated(
                    shot[0] - shot[3] * t_back,
                    shot[1] - shot[4] * t_back,
                    shot[2] - shot[5] * t_back,
                )
                glutSolidSphere(0.11 * fade, 8, 8)
                glPopMatrix()
            glEnable(GL_LIGHTING)
        glPopMatrix()

        # Remove bullets and bombs that are out of bounds
        self.bullets = [b for b in self.bullets if -200 < b[2] < 200]
        self.bombs = [b for b in self.bombs if b[1] > -5]

    def init_sky_bombs(self):
        """Initialize bombs falling from sky"""
        self.sky_bombs = []
        for _ in range(self.SKY_BOMB_COUNT):
            self.sky_bombs.append(self._new_sky_bomb())

    def _new_sky_bomb(self):
        """Create a new sky bomb at a random position"""
        x = random.uniform(self.SKY_BOMB_X_MIN, self.SKY_BOMB_X_MAX)
        y = random.uniform(1, 8)
        z = random.uniform(-200, -20)
        return [x, y, z]

    def draw_sky_bombs(self):
        """Draw all sky bombs as small flying birds with flapping wings"""
        elapsed_time = self.current_time_seconds()
        for idx, bomb in enumerate(self.sky_bombs):
            # Stagger each bird's flap cycle so they don't all beat in unison
            wing_flap = math.sin(elapsed_time * 9.0 + idx * 1.7) * 45.0

            glPushMatrix()
            glTranslated(bomb[0], bomb[1], bomb[2])

            # Body (deep red silhouette)
            glColor3f(0.55, 0.03, 0.05)
            glPushMatrix()
            glScaled(0.32, 0.16, 0.16)
            glutSolidSphere(1, 12, 12)
            glPopMatrix()

            # Head
            glPushMatrix()
            glTranslated(0.3, 0.06, 0)
            glScaled(0.15, 0.15, 0.15)
            glutSolidSphere(1, 10, 10)
            glPopMatrix()

            # Beak
            glColor3f(0.9, 0.55, 0.0)
            glPushMatrix()
            glTranslated(0.44, 0.05, 0)
            glRotated(90, 0, 1, 0)
            glScaled(0.07, 0.07, 0.07)
            glutSolidCone(0.5, 1.0, 8, 8)
            glPopMatrix()

            # Wings (flap up and down)
            glColor3f(0.55, 0.03, 0.05)
            for side in (-1, 1):
                glPushMatrix()
                glTranslated(0, 0.02, side * 0.06)
                glRotated(side * (25 + wing_flap), 1, 0, 0)
                glScaled(0.28, 0.03, 0.55)
                glutSolidCube(1)
                glPopMatrix()

            # Tail feathers
            glPushMatrix()
            glTranslated(-0.34, 0, 0)
            glScaled(0.12, 0.04, 0.2)
            glutSolidCube(1)
            glPopMatrix()

            glPopMatrix()

    def draw_bomb_boxes(self):
        """Draw destructible obstacles as small wooden boats bobbing on the
        river, in place of the old red cubes. Collision logic elsewhere only
        reads box[0]/box[1]/box[2], so the swap is purely visual."""
        hull_color = (0.36, 0.22, 0.09)  # weathered wood hull
        deck_color = (0.55, 0.38, 0.16)  # lighter wood deck
        cabin_color = (0.85, 0.85, 0.82)  # off-white cabin
        mast_color = (0.25, 0.15, 0.05)
        sail_color = (0.92, 0.9, 0.85)

        elapsed_time = self.current_time_seconds()
        for i, box in enumerate(self.bomb_boxes):
            # Gentle bob and rock so the boats read as floating, not static.
            bob = 0.06 * math.sin(elapsed_time * 1.6 + i * 1.7)
            rock = 4.0 * math.sin(elapsed_time * 1.1 + i * 2.3)
            glPushMatrix()
            glTranslated(box[0], box[1] + bob, box[2])
            glRotated(rock, 0, 0, 1)

            # Hull: low, elongated body with a tapered, pointed bow.
            glColor3d(*hull_color)
            glPushMatrix()
            glScaled(1.0, 0.5, 2.6)
            glutSolidCube(1.4)
            glPopMatrix()

            glPushMatrix()
            glTranslated(0, 0, 1.6)
            glRotated(-90, 1, 0, 0)
            glScaled(0.7, 0.7, 1.0)
            glutSolidCone(0.7, 1.1, 8, 2)
            glPopMatrix()

            # Deck plank running along the top of the hull.
            glColor3d(*deck_color)
            glPushMatrix()
            glTranslated(0, 0.32, -0.1)
            glScaled(1.3, 0.12, 3.4)
            glutSolidCube(1.0)
            glPopMatrix()

            # Small cabin toward the stern.
            glColor3d(*cabin_color)
            glPushMatrix()
            glTranslated(0, 0.65, -0.7)
            glScaled(0.9, 0.6, 0.9)
            glutSolidCube(1.0)
            glPopMatrix()

            # Mast.
            glColor3d(*mast_color)
            glPushMatrix()
            glTranslated(0, 1.3, 0.4)
            glScaled(0.06, 1.8, 0.06)
            glutSolidCube(1.0)
            glPopMatrix()

            # Sail: a flat triangle, so - like the dragon's wings/tail fins -
            # culling and lighting are disabled while drawing it, otherwise
            # it would only look right from one viewing angle.
            glColor3d(*sail_color)
            glDisable(GL_LIGHTING)
            glDisable(GL_CULL_FACE)
            glBegin(GL_TRIANGLES)
            glNormal3f(1, 0, 0)
            glVertex3f(0, 0.4, 0.4)
            glVertex3f(0, 2.1, 0.4)
            glVertex3f(0, 0.5, 1.1)
            glEnd()
            glEnable(GL_CULL_FACE)
            glEnable(GL_LIGHTING)

            glPopMatrix()

        """Reseting all game variables to initial state for a new game"""

    def start_game(self):
        """Reset everything and begin a fresh round - shared by the G
        key, R after a game over, and clicking the start screen's PLAY
        button, so there's exactly one place that defines "starting"."""
        self.reset_game()
        self.game_start_time = time.time()
        self.START = True

    def reset_game(self):
        self.LIVES = 3
        self.ring_count = 0
        self.score = 0
        self.GAME_OVER = False
        self.time_remaining = self.ROUND_TIME_LIMIT
        self._last_timer_tick = None
        self.START = False
        self.CHEAT_MODE = False
        self.collision_type = None
        self.out_of_bounds_since = None
        self.speed = 0.3
        self.translation_x = 0.0
        self.translation_y = 0.0
        self.rotation_x = 0.0
        self.rotation_y = 0.0
        self.rotation_z = 4.0
        self.zoom = 4.0
        self.first_person = False
        self.SHOW_INSTRUCTIONS = False

        # Reinitialize game world patches
        base_patches = [
            (-8.0, 2),
            (-20.0, 0),
            (-40.0, 3),
            (-60.0, 1),
            (-80.0, 5),
            (-100.0, 4),
            (-120.0, 2),
        ]
        shapes = ["ring", "square", "triangle"]
        self.patches = [
            {"z": z, "n": n, "passed": False, "shape": random.choice(shapes)}
            for (z, n) in base_patches
        ]

        # Clear all game objects
        self.bullets = []
        self.bombs = []
        self.sky_bombs = []
        self.bomb_boxes = []
        self.boat_bullets = []
        self.last_boat_volley_time = 0.0
        self.boat_attack_warning = False
        self.shield_active = False
        self.shield_key_down = False
        self.shield_press_start = None
        self.rain = []
        self.RAINING = True
        self.snow = []
        self.SNOWING = False
        self.weather_phase = "clear"
        self.rot = False
        self.TIME = 0
        self.bullets_fired = 0
        self.bullets_hit = 0
        self.misuse_fire = False
        self.misuse_time = 0.0
        self.cheat_mode = False
        self.CHEAT_MODE = False
        self.auto_daynight = True
        self.force_daynight = None
        # Reinitialize all world objects
        self.init_rain()
        self.init_snow()
        self.init_bomb_boxes()
        self.init_sky_bombs()
        # Reset game timer
        self.game_start_time = time.time()

    def resize(self, width, height):
        """Handle window resize events and update viewport"""
        global window_width, window_height
        if height == 0:
            height = 1
        window_width = width
        window_height = height
        aspect_ratio = width / float(height)
        glViewport(0, 0, width, height)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        glFrustum(-aspect_ratio, aspect_ratio, -1.0, 1.0, 2.0, 1000.0)
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()

    def update_game_state(self):
        """Update all game logic: movement, collisions, boundaries, and game timer"""
        # Get elapsed time from game start
        elapsed_time = self.current_time_seconds()

        # Countdown match clock: ticks down by real elapsed time each frame;
        # hitting 0 ends the game. Rings add time back in check_collisions.
        if self.START and not self.GAME_OVER:
            if self._last_timer_tick is None:
                self._last_timer_tick = elapsed_time
            self.time_remaining -= elapsed_time - self._last_timer_tick
            self._last_timer_tick = elapsed_time
            if self.time_remaining <= 0:
                self.time_remaining = 0
                self.GAME_OVER = True
                self.collision_type = "time_up"

        self.TIME = int(elapsed_time)

        # Check if player has lost all lives
        if self.LIVES <= 0:
            self.GAME_OVER = True

        # Auto-reset game after firing abuse timeout
        if self.misuse_fire:
            if elapsed_time - self.misuse_time > 2.0:
                self.reset_game()
                self.START = True

        # Clamp plane rotation angles within maximum limits
        if self.rotation_x > self.PLANE_MAX_ROLL:
            self.rotation_x = self.PLANE_MAX_ROLL
        if self.rotation_x < -self.PLANE_MAX_ROLL:
            self.rotation_x = -self.PLANE_MAX_ROLL
        if self.rotation_z > self.PLANE_MAX_PITCH:
            self.rotation_z = self.PLANE_MAX_PITCH
        if self.rotation_z < -self.PLANE_MAX_YAW:
            self.rotation_z = -self.PLANE_MAX_YAW

        # Clamp plane position within world boundaries
        if self.translation_x > self.PLANE_BOUNDARY_X:
            self.translation_x = self.PLANE_BOUNDARY_X
        if self.translation_x < -self.PLANE_BOUNDARY_X:
            self.translation_x = -self.PLANE_BOUNDARY_X
        if self.translation_y > self.PLANE_BOUNDARY_Y:
            self.translation_y = self.PLANE_BOUNDARY_Y
        if self.translation_y < -self.PLANE_BOUNDARY_Y:
            self.translation_y = -self.PLANE_BOUNDARY_Y

        # Flying past the mountains on either side starts a 10-second
        # countdown; if the dragon hasn't come back between the mountains
        # by the time it runs out, it dies. plane_world_x uses the same
        # sign convention as the ring/ground collision checks below.
        if not self.CHEAT_MODE:
            plane_world_x = -self.translation_x
            if abs(plane_world_x) > self.MOUNTAIN_BOUNDARY_X:
                if self.out_of_bounds_since is None:
                    self.out_of_bounds_since = elapsed_time
                elif (
                    elapsed_time - self.out_of_bounds_since
                    >= self.OUT_OF_BOUNDS_TIME_LIMIT
                ):
                    self.LIVES = 0
                    self.GAME_OVER = True
                    self.collision_type = "out_of_bounds"
            else:
                self.out_of_bounds_since = None

        # In cheat mode, auto-steer towards the next ring
        if self.cheat_mode:
            target_ring = None
            max_z = -float("inf")
            # Find the closest ring ahead
            for patch in self.patches:
                if patch["n"] != -1 and patch["z"] < 0:
                    if patch["z"] > max_z:
                        max_z = patch["z"]
                        target_ring = patch
            if target_ring:
                # Smoothly move plane towards ring center
                target_x = self.ring_positions_x[target_ring["n"]]
                target_y = self.ring_positions_y[target_ring["n"]]
                desired_translation_x = -target_x
                desired_translation_y = 1 - target_y
                self.translation_x += (
                    desired_translation_x - self.translation_x
                ) * 0.12
                self.translation_y += (
                    desired_translation_y - self.translation_y
                ) * 0.12

        # Move patches (terrain) towards player
        for patch in self.patches:
            patch["z"] += self.speed
            # Reset patch position when it passes player
            if patch["z"] >= 20:
                patch["z"] = -110
                patch["passed"] = False

        # Apply rotation recovery (return plane to neutral angle)
        if self.rotation_x > 0:
            self.rotation_x -= self.rotation_recovery_speed
        if self.rotation_x < 0:
            self.rotation_x += self.rotation_recovery_speed
        if self.rotation_y > 0:
            self.rotation_y -= self.rotation_recovery_speed
        if self.rotation_y < 0:
            self.rotation_y += self.rotation_recovery_speed
        if self.rotation_z > 0:
            self.rotation_z -= self.rotation_recovery_speed
        if self.rotation_z < 0:
            self.rotation_z += self.rotation_recovery_speed

        # Gradually increase forward speed
        self.speed += 0.0002
        if self.speed >= self.MAX_SPEED:
            self.speed = self.MAX_SPEED

        # Update sky bomb positions
        for i in range(len(self.sky_bombs)):
            self.sky_bombs[i][2] += self.speed
            if self.sky_bombs[i][2] > 20:
                self.sky_bombs[i] = self._new_sky_bomb()

        # Update bomb box positions
        for box in self.bomb_boxes:
            box[2] += self.speed
            if box[2] > 20:
                box[2] = random.uniform(-100, -20)

        # Boats fire a cannonball volley at the dragon every
        # BOAT_FIRE_INTERVAL seconds
        self.fire_boat_attacks()

        # Move boat cannonballs (each travels in a straight line toward
        # wherever the dragon was when it was fired)
        for shot in self.boat_bullets:
            shot[0] += shot[3]
            shot[1] += shot[4]
            shot[2] += shot[5]
        self.boat_bullets = [s for s in self.boat_bullets if -200 < s[2] < 200]

        # Flag an on-screen warning whenever some cannonball is close enough
        # to land within BOAT_ATTACK_WARNING_LEAD seconds, using its own
        # known speed (not distance alone) so a slow, far shot doesn't
        # trigger it early and a fast, close one isn't missed.
        plane_world_x = -self.translation_x
        plane_world_y = 1 - self.translation_y
        self.boat_attack_warning = False
        for shot in self.boat_bullets:
            distance = math.sqrt(
                (plane_world_x - shot[0]) ** 2
                + (plane_world_y - shot[1]) ** 2
                + (shot[2]) ** 2
            )
            frames_remaining = distance / self.BOAT_BULLET_SPEED
            seconds_remaining = frames_remaining / self.GAME_FPS
            if seconds_remaining <= self.BOAT_ATTACK_WARNING_LEAD:
                self.boat_attack_warning = True
                break

        # Holding the "H" shield key too long overloads the shield and
        # ends the game, so it can't just be held down permanently.
        if self.shield_key_down and self.shield_press_start is not None:
            if elapsed_time - self.shield_press_start > self.SHIELD_HOLD_LIMIT:
                self.GAME_OVER = True
                self.collision_type = "shield_overload"

    def fire_boat_attacks(self):
        """Every BOAT_FIRE_INTERVAL seconds, every boat currently near
        enough to be on-screen fires one cannonball toward wherever the
        dragon is right now."""
        elapsed_time = self.current_time_seconds()
        if elapsed_time - self.last_boat_volley_time < self.BOAT_FIRE_INTERVAL:
            return
        self.last_boat_volley_time = elapsed_time

        plane_world_x = -self.translation_x
        plane_world_y = 1 - self.translation_y
        for box in self.bomb_boxes:
            # Only boats still ahead of the dragon (not yet passed) take a
            # shot, so cannonballs always approach from the front. A boat
            # with box[2] >= 0 has already scrolled past the dragon; firing
            # from there would send a cannonball in from behind. The lower
            # bound matches how far out boats naturally roam, so distant
            # shots have real flight time for the 2-second warning to mean
            # something instead of firing and landing almost at once.
            if not (-100.0 < box[2] < -1.5):
                continue
            dx = plane_world_x - box[0]
            dy = plane_world_y - box[1]
            dz = 0.0 - box[2]
            distance = math.sqrt(dx * dx + dy * dy + dz * dz)
            if distance < 0.001:
                continue
            vx = dx / distance * self.BOAT_BULLET_SPEED
            vy = dy / distance * self.BOAT_BULLET_SPEED
            vz = dz / distance * self.BOAT_BULLET_SPEED
            self.boat_bullets.append([box[0], box[1] + 0.6, box[2], vx, vy, vz])

    def check_collisions(self):
        """Check all collision types: ground, buildings, rings, bombs"""
        # Calculate plane position in world coordinates
        plane_world_x = -self.translation_x
        plane_world_y = 1 - self.translation_y

        # Check collision with ground (below y=0)
        if plane_world_y <= 0:
            self.LIVES = 0
            self.GAME_OVER = True
            self.collision_type = "ground"
            return

        # Check collision with buildings
        lane_half_width = 8
        for patch in self.patches:
            if abs(patch["z"]) < 2.0:
                for i in range(-(self.GRID_SIZE // 2) + 1, (self.GRID_SIZE // 2), 2):
                    if -lane_half_width < i < lane_half_width:
                        continue
                    for j in range(
                        -(self.GRID_SIZE // 2) + 1, (self.GRID_SIZE // 2), 2
                    ):
                        # Get building height at grid position
                        height = self.terrain_grid[i + (self.GRID_SIZE // 2)][
                            j + (self.GRID_SIZE // 2)
                        ]
                        if height > 0:
                            # Check if plane collides with building
                            if (
                                abs(i - plane_world_x) <= 0.6
                                and abs(j - 0) <= 0.6
                                and plane_world_y <= 0.8 + height + 0.2
                            ):
                                self.LIVES = 0
                                self.GAME_OVER = True
                                self.collision_type = "building"
                                return

        # Check collision with rings (positive score event)
        for patch in self.patches[:]:
            if patch["n"] != -1 and not patch["passed"]:
                plane_world_x = -self.translation_x
                plane_world_y = 1 - self.translation_y
                if abs(patch["z"]) <= self.RING_PASS_Z_THRESHOLD:
                    # Calculate distance from plane to ring center
                    distance_x = plane_world_x - self.ring_positions_x[patch["n"]]
                    distance_y = plane_world_y - self.ring_positions_y[patch["n"]]
                    horizontal_distance = math.sqrt(
                        distance_x * distance_x + distance_y * distance_y
                    )

                    # Award points if close enough to ring center
                    if horizontal_distance <= self.RING_PASS_RADIUS:
                        self.ring_count += 1
                        self.score += 5
                        patch["passed"] = True
                        # Flying through a ring target (fire ring, cloud, or
                        # leaf) buys more time on the countdown clock
                        self.time_remaining += self.RING_TIME_BONUS
                        # Adjust speed based on ring type
                        if patch["n"] % 3 == 1:
                            self.speed += self.SPEED_INCREMENT
                        elif patch["n"] % 3 == 2:
                            self.speed -= self.SPEED_DECREMENT

        # Check collision with sky bombs (negative event)
        plane_world_x = -self.translation_x
        plane_y = 1 - self.translation_y
        for bomb in self.sky_bombs:
            distance = math.sqrt(
                (plane_world_x - bomb[0]) ** 2
                + (plane_y - bomb[1]) ** 2
                + (bomb[2]) ** 2
            )
            if distance < self.COLLISION_DISTANCE_BOMB:
                if not self.CHEAT_MODE and not self.shield_active:
                    self.LIVES -= 1
                    if self.LIVES <= 0:
                        self.GAME_OVER = True
                bomb[2] = random.uniform(-100, -20)

        # Check collision with bomb boxes (can be destroyed by bullets)
        plane_world_x = -self.translation_x
        plane_y = 1 - self.translation_y
        for box in self.bomb_boxes:
            distance = math.sqrt(
                (plane_world_x - box[0]) ** 2 + (plane_y - box[1]) ** 2 + (box[2]) ** 2
            )
            # Plane collision with bomb box
            if distance < self.COLLISION_DISTANCE_BOMB:
                if not self.CHEAT_MODE and not self.shield_active:
                    self.LIVES -= 1
                    if self.LIVES <= 0:
                        self.GAME_OVER = True
                box[2] = random.uniform(-100, -20)

            # Check bomb (dropped) collision with box
            for b in self.bombs[:]:
                distance = math.sqrt((b[0] - box[0]) ** 2 + (b[1] - box[1]) ** 2)
                if distance < self.COLLISION_DISTANCE_BOMB and abs(box[2] - b[2]) < 1:
                    box[2] = random.uniform(-100, 20)
                    self.bombs.remove(b)
                    self.bullets_hit += 1
                    self.score += 20

            # Check bullet collision with box
            for b in self.bullets[:]:
                distance = math.sqrt((b[0] - box[0]) ** 2 + (b[1] - box[1]) ** 2)
                if distance < self.COLLISION_DISTANCE_BOMB and abs(box[2] - b[2]) < 1:
                    box[2] = random.uniform(-100, 20)
                    self.bullets.remove(b)

        # Check bullet collision with sky bombs
        for b in self.bullets[:]:
            for idx, bomb in enumerate(self.sky_bombs[:]):
                distance = math.sqrt(
                    (b[0] - bomb[0]) ** 2
                    + (b[1] - bomb[1]) ** 2
                    + (b[2] - bomb[2]) ** 2
                )
                if distance < self.COLLISION_DISTANCE_BOMB + 0.2:
                    if b in self.bullets:
                        self.bullets.remove(b)
                    self.sky_bombs[idx] = self._new_sky_bomb()
                    self.score += 5
                    self.bullets_hit += 1
                    break

        # Check collision with boat cannonballs (boats attacking the dragon)
        plane_world_x = -self.translation_x
        plane_y = 1 - self.translation_y
        for shot in self.boat_bullets[:]:
            distance = math.sqrt(
                (plane_world_x - shot[0]) ** 2
                + (plane_y - shot[1]) ** 2
                + (shot[2]) ** 2
            )
            if distance < self.COLLISION_DISTANCE_BOMB:
                if not self.CHEAT_MODE and not self.shield_active:
                    self.LIVES -= 1
                    if self.LIVES <= 0:
                        self.GAME_OVER = True
                        self.collision_type = "boat_attack"
                self.boat_bullets.remove(shot)

        # Check for firing abuse (too many shots with no hits)
        if self.bullets_fired > 15 and self.bullets_hit == 0 and not self.misuse_fire:
            self.misuse_fire = True
            self.GAME_OVER = True
            self.misuse_time = self.current_time_seconds()

    def render_scene(self):
        """Render all visible game objects"""
        # Sun/moon: real, depth-tested world geometry far in the
        # background, drawn before the rest of the scene (order doesn't
        # matter for depth-tested opaque objects, but drawing it first
        # keeps it clearly "back there" conceptually).
        self.draw_sky_bodies()

        # Render player dragon in center
        glPushMatrix()
        glTranslated(0, 1, 0)
        glRotated(90, 0, 1, 0)
        glRotated(5, 0, 0, 1)
        glRotated(self.rotation_x, 1, 0, 0)
        glRotated(self.rotation_y, 0, 1, 0)
        glRotated(self.rotation_z, 0, 0, 1)
        glScaled(0.4, 0.4, 0.4)
        self.plane()
        glPopMatrix()

        # Render environmental effects (recurring snow / storm cycle)
        self.drawRain()
        self.drawSnow()
        if self.weather_phase == "storm":
            elapsed_now = self.current_time_seconds()
            if self.thunder_flash_active(elapsed_now):
                self.draw_lightning_bolt(elapsed_now)
        self.draw_bullets_and_bombs()

        # Render terrain patches (scrolling ground)
        for patch in self.patches:
            glPushMatrix()
            glTranslated(self.translation_x, self.translation_y, patch["z"])
            if patch["n"] == -1:
                self.soheedMinarEnv(self.GRID_SIZE)
            else:
                self.environment(
                    patch["n"],
                    self.GRID_SIZE,
                    self.terrain_grid,
                    self.ring_positions_x,
                    self.ring_positions_y,
                    patch["shape"],
                )
            glPopMatrix()

        # Render destructible bomb boxes
        glPushMatrix()
        glTranslated(self.translation_x, self.translation_y, 0)
        self.draw_bomb_boxes()
        glPopMatrix()

        # Render falling sky bombs
        glPushMatrix()
        glTranslated(self.translation_x, self.translation_y, 0)
        self.draw_sky_bombs()
        glPopMatrix()

    def draw(self):
        """Main game update loop - skip if game is over"""
        if self.GAME_OVER:
            return
        self.update_game_state()
        self.check_collisions()
        self.render_scene()

    def draw_text(self, x, y, text, font=GLUT_BITMAP_HELVETICA_18, color=(0.0, 0.0, 0.0), bold=False):
        """Draw 2D text on screen at given position. GLUT's bitmap fonts
        only come in a few fixed sizes and have no bold variant, so
        bold=True fakes both a bold weight and a touch of extra size by
        stamping the same glyphs a second time offset by a pixel in x
        and y - thickening every stroke slightly without jumping to a
        visibly larger font."""
        glColor3f(*color)
        glMatrixMode(GL_PROJECTION)
        glPushMatrix()
        glLoadIdentity()
        gluOrtho2D(0, window_width, 0, window_height)

        glMatrixMode(GL_MODELVIEW)
        glPushMatrix()
        glLoadIdentity()

        offsets = [(0, 0), (1, 0), (0, 1), (1, 1)] if bold else [(0, 0)]
        for dx, dy in offsets:
            glRasterPos2f(x + dx, y + dy)
            for character in text:
                glutBitmapCharacter(font, ord(character))

        glPopMatrix()
        glMatrixMode(GL_PROJECTION)
        glPopMatrix()
        glMatrixMode(GL_MODELVIEW)

    def drawStrokeText(self, text_string, x, y, z):
        """Draw 3D stroked text"""
        glPushMatrix()
        glTranslatef(x, y + 8, z)
        glScalef(0.002, 0.002, z if z != 0 else 1)
        glColor3f(1.0, 1.0, 1.0)
        for character in text_string:
            glutStrokeCharacter(GLUT_STROKE_ROMAN, ord(character))
        glPopMatrix()

    def drawStrokeText2(self, text_string, x, y, z):
        """Draw larger 3D stroked text"""
        glPushMatrix()
        glTranslatef(x, y + 8, z)
        glScalef(0.005, 0.005, z if z != 0 else 1)
        glColor3f(1.0, 1.0, 1.0)
        for character in text_string:
            glutStrokeCharacter(GLUT_STROKE_ROMAN, ord(character))
        glPopMatrix()

    def draw_hud_2d(self):
        """Draw in-game HUD with stats and controls"""
        if not self.START or self.GAME_OVER:
            return

        glDisable(GL_LIGHTING)
        glDisable(GL_DEPTH_TEST)

        margin_x = 10
        top_y = window_height - 20
        line_height = 18

        # Plain HUD text is black by day, but black is nearly invisible
        # against the dark night sky, so it switches to white at night.
        # Status colors (red warnings, the shield's red/green) stay as-is
        # since they already read clearly against either sky.
        text_color = (1.0, 1.0, 1.0) if self.is_night else (0.0, 0.0, 0.0)

        # Display score, lives, and ring count
        self.draw_text(
            margin_x,
            top_y,
            f"Score: {self.score}  Lives: {self.LIVES}  Rings: {self.ring_count}",
            font=GLUT_BITMAP_9_BY_15,
            color=text_color,
            bold=True,
        )
        # Display ammunition statistics
        self.draw_text(
            margin_x,
            top_y - line_height,
            f"Bullets: {self.bullets_fired}  Hits: {self.bullets_hit}",
            font=GLUT_BITMAP_9_BY_15,
            color=text_color,
            bold=True,
        )
        # Display remaining time on the countdown clock - ceil so it reads
        # exactly "30" the instant the round starts rather than "29"
        display_time = max(0, math.ceil(self.time_remaining))
        self.draw_text(
            margin_x,
            top_y - 2 * line_height,
            f"Time: {display_time}",
            font=GLUT_BITMAP_9_BY_15,
            color=(1.0, 0.0, 0.0) if display_time <= 5 else text_color,
            bold=True,
        )

        # Warn the player with a countdown while they're past the mountains
        if self.out_of_bounds_since is not None:
            remaining_bounds_time = self.OUT_OF_BOUNDS_TIME_LIMIT - (
                self.current_time_seconds() - self.out_of_bounds_since
            )
            if remaining_bounds_time < 0:
                remaining_bounds_time = 0
            self.draw_text(
                margin_x,
                top_y - 3 * line_height,
                f"OUT OF BOUNDS! Return in {remaining_bounds_time:.1f}s or die",
                font=GLUT_BITMAP_9_BY_15,
                color=(1.0, 0.0, 0.0),
                bold=True,
            )

        # Warn the player a couple of seconds before a boat's cannonball
        # actually lands
        if self.boat_attack_warning:
            self.draw_text(
                margin_x,
                top_y - 4 * line_height,
                "WARNING: Cannonball incoming!",
                font=GLUT_BITMAP_9_BY_15,
                color=(1.0, 0.0, 0.0),
                bold=True,
            )

        # Shield status while "H" is held - turns red as the 5-second
        # overload limit approaches, so holding it forever isn't free
        if self.shield_key_down and self.shield_press_start is not None:
            held_for = self.current_time_seconds() - self.shield_press_start
            remaining_safe = max(0.0, self.SHIELD_HOLD_LIMIT - held_for)
            shield_color = (1.0, 0.0, 0.0) if remaining_safe < 2.0 else (0.0, 0.6, 0.0)
            self.draw_text(
                margin_x,
                top_y - 5 * line_height,
                f"SHIELD UP - overloads in {remaining_safe:.1f}s",
                font=GLUT_BITMAP_9_BY_15,
                color=shield_color,
                bold=True,
            )

        glEnable(GL_DEPTH_TEST)
        glEnable(GL_LIGHTING)

    def draw_gameover_2d(self):
        """Draw game over screen with final statistics"""
        glMatrixMode(GL_PROJECTION)
        glPushMatrix()
        glLoadIdentity()
        gluOrtho2D(0, window_width, 0, window_height)

        glMatrixMode(GL_MODELVIEW)
        glPushMatrix()
        glLoadIdentity()

        glDisable(GL_LIGHTING)
        glDisable(GL_DEPTH_TEST)

        glColor3f(0.0, 0.0, 0.0)

        def draw_centered(y, text, font=GLUT_BITMAP_HELVETICA_18):
            """Helper to draw text centered on screen"""
            char_width = 9
            text_width = len(text) * char_width
            x = (window_width - text_width) / 2
            glRasterPos2f(x, y)
            for character in text:
                glutBitmapCharacter(font, ord(character))

        mid_y = window_height / 2
        line_height = 25

        # Reserve a full line of its own for the death-cause subtitle so it
        # never overlaps "GAME OVER" above or "TOTAL SCORE" below, whether
        # or not a subtitle is actually shown this run.
        draw_centered(mid_y + 2 * line_height, "GAME OVER")
        if self.collision_type == "out_of_bounds":
            draw_centered(mid_y + line_height, "Strayed too far past the mountains")
        elif self.collision_type == "boat_attack":
            draw_centered(mid_y + line_height, "Sunk by a boat's cannonball")
        elif self.collision_type == "shield_overload":
            draw_centered(mid_y + line_height, "Shield overloaded from holding it too long")
        elif self.collision_type == "time_up":
            draw_centered(mid_y + line_height, "Ran out of time")
        draw_centered(mid_y, f"TOTAL SCORE: {self.score}")
        draw_centered(mid_y - line_height, f"TOTAL HITS: {self.bullets_hit}")
        draw_centered(mid_y - 3 * line_height, "Press R to Play Again")
        draw_centered(mid_y - 4 * line_height, "Press E to Exit")

        glEnable(GL_DEPTH_TEST)
        glEnable(GL_LIGHTING)

        glPopMatrix()
        glMatrixMode(GL_PROJECTION)
        glPopMatrix()
        glMatrixMode(GL_MODELVIEW)

    def display(self):
        """Main render function for every frame"""
        global camera_yaw, camera_pitch, camera_distance

        if self.START and not self.GAME_OVER:
            self.update_weather()

            # Sky slowly cycles through a sequence of named sky colors -
            # light blue (day), deep orange (sunset), deep blue (night),
            # ash (overcast dawn), white (bright midday) - then loops.
            # Each stop takes 15s to slowly transform into, then holds
            # steady there for 5s before the next transform begins.
            sky_stops = [
                (0.5, 0.8, 1.0, 1.0),  # light blue
                (0.8, 0.35, 0.05, 1.0),  # deep orange
                (0.03, 0.05, 0.25, 1.0),  # deep blue
                (0.55, 0.55, 0.55, 1.0),  # ash
                (0.95, 0.95, 0.95, 1.0),  # white
            ]
            day_color = sky_stops[0]  # light blue
            night_color = sky_stops[2]  # deep blue

            # Which corner icon to show (sun vs moon) tracks this same sky
            # cycle - only the "deep blue" stop counts as night, the other
            # four (light blue, sunset orange, ash dawn, bright white) all
            # read as daytime lighting.
            NIGHT_STOP_INDEX = 2

            if self.force_daynight == "day":
                current_sky_color = list(day_color)
                self.is_night = False
            elif self.force_daynight == "night":
                current_sky_color = list(night_color)
                self.is_night = True
            elif self.auto_daynight:
                # 15s slow transform, then 5s holding steady at the stop
                # just reached, looping forever. Continuous elapsed time
                # (not the once-a-second self.TIME) keeps it smooth.
                transform_seconds = 15.0
                hold_seconds = 5.0
                segment_seconds = transform_seconds + hold_seconds
                total_cycle = segment_seconds * len(sky_stops)
                cycle_position = self.current_time_seconds() % total_cycle
                stop_index = int(cycle_position / segment_seconds) % len(sky_stops)
                next_index = (stop_index + 1) % len(sky_stops)
                pos_in_segment = cycle_position - stop_index * segment_seconds
                blend = min(pos_in_segment / transform_seconds, 1.0)
                current_sky_color = [
                    sky_stops[stop_index][i] * (1 - blend)
                    + sky_stops[next_index][i] * blend
                    for i in range(4)
                ]
                # Whichever stop currently dominates the blend decides the
                # icon, so it swaps partway through the transform rather
                # than only at the start/end of a segment.
                dominant_index = next_index if blend >= 0.5 else stop_index
                self.is_night = dominant_index == NIGHT_STOP_INDEX
            else:
                current_sky_color = list(day_color)
                self.is_night = False

            if self.weather_phase == "storm":
                # Storm clouds dim and gray out the sky ...
                storm_gray = (0.28, 0.28, 0.32, 1.0)
                storm_mix = 0.55
                current_sky_color = [
                    current_sky_color[i] * (1 - storm_mix) + storm_gray[i] * storm_mix
                    for i in range(4)
                ]
                # ... except for a brief, bright lightning flash.
                if self.thunder_flash_active(self.current_time_seconds()):
                    flash_mix = 0.85
                    current_sky_color = [
                        current_sky_color[i] * (1 - flash_mix) + flash_mix
                        for i in range(4)
                    ]

            # Remember the exact cleared sky color so the moon icon's
            # crescent "shadow" can be painted in that same color and
            # blend seamlessly into the sky behind it, instead of leaving
            # a visible dark patch.
            self._current_sky_rgb = tuple(current_sky_color[:3])
            glClearColor(*current_sky_color)
        else:
            glClearColor(1.0, 1.0, 1.0, 1.0)

        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()

        # Set camera based on view mode
        if self.START and not self.GAME_OVER and self.first_person:
            # First-person view from plane
            eye_x, eye_y, eye_z = 0.0, 2.0, 3.0
            center_x, center_y, center_z = 0.0, 1.5, -10.0
            gluLookAt(eye_x, eye_y, eye_z, center_x, center_y, center_z, 0, 1.0, 0.0)
        elif self.START or self.GAME_OVER:
            # Third-person orbital camera
            radians_yaw = math.radians(camera_yaw)
            radians_pitch = math.radians(camera_pitch)
            eye_x = camera_distance * math.cos(radians_pitch) * math.sin(radians_yaw)
            eye_y = camera_distance * math.sin(radians_pitch) + 4.0
            eye_z = camera_distance * math.cos(radians_pitch) * math.cos(radians_yaw)
            center_x, center_y, center_z = 0.0, 4.0, 0.0
            gluLookAt(eye_x, eye_y, eye_z, center_x, center_y, center_z, 0, 1.0, 0.0)

        # Render scene or menus based on game state
        if self.GAME_OVER:
            self.draw_gameover_2d()
        elif self.START:
            # Game in progress
            glPushMatrix()
            glTranslated(0, 0, 0)
            glScaled(self.zoom, self.zoom, self.zoom)
            glRotated(0, 0, 1, 0)
            self.draw()
            glPopMatrix()
        else:
            # Start menu
            self.draw_start_menu()

        # Draw HUD (score, controls, etc.)
        self.draw_hud_2d()
        glutSwapBuffers()

    def key(self, key_pressed, x, y):
        """Handle keyboard input for game controls"""
        # key_pressed is bytes, e.g. b'e'

        # Exit works everywhere - start menu, mid-flight, or game over -
        # matching the "E exit" hint shown throughout the game.
        #
        # This is called from GLUT's C event loop via a ctypes callback.
        # sys.exit() raises SystemExit, but ctypes swallows exceptions
        # raised inside callbacks (it prints a traceback and keeps the
        # C loop running instead of letting the process die) - so E would
        # silently do nothing. os._exit() terminates the process directly
        # without relying on a Python exception propagating back through
        # the C loop, so it actually quits.
        if key_pressed in (b"e", b"E"):
            os._exit(0)

        # Game over state controls
        if self.GAME_OVER:
            if key_pressed in (b"r", b"R"):
                # Restart game
                self.start_game()
                glutPostRedisplay()
            return

        # Prevent movement input during cheat mode auto-steering
        if self.cheat_mode and key_pressed in b"wsad":
            return

        # Movement and control sensitivity
        movement_fraction = 0.5
        rotation_fraction = 1

        if key_pressed == b"r":
            self.rot = True
        elif key_pressed == b"t":
            self.rot = False
        elif key_pressed == b"z":
            # Zoom in
            self.zoom += 0.05
        elif key_pressed == b"Z":
            # Zoom out
            self.zoom -= 0.05
        elif key_pressed == b"w":
            # Move up/forward
            self.translation_y -= movement_fraction
            self.rotation_z += rotation_fraction
        elif key_pressed == b"s":
            # Move down/backward
            self.translation_y += movement_fraction
            self.rotation_z -= rotation_fraction
        elif key_pressed == b"a":
            # Move left
            self.translation_x += movement_fraction
            self.rotation_x -= rotation_fraction * 3
            self.rotation_y += rotation_fraction / 2
        elif key_pressed == b"d":
            # Move right
            self.translation_x -= movement_fraction
            self.rotation_x += rotation_fraction * 3
            self.rotation_y -= rotation_fraction / 2
        elif key_pressed == b"g":
            # G key - start/restart game
            self.start_game()
        elif key_pressed == b"n":
            # N key - force day
            self.force_daynight = "day"
            self.auto_daynight = False
        elif key_pressed == b"m":
            # M key - force night
            self.force_daynight = "night"
            self.auto_daynight = False
        elif key_pressed in (b"l", b"L"):
            # L key - enable auto day/night cycle
            self.auto_daynight = True
            self.force_daynight = None
        elif key_pressed == b"b":
            # B key - drop bomb
            self.bombs.append([-self.translation_x, 1 - self.translation_y, 0])
        elif key_pressed == b"c":
            # C key - toggle cheat mode
            self.cheat_mode = not self.cheat_mode
            self.CHEAT_MODE = self.cheat_mode
        elif key_pressed == b"v":
            # V key - cheat mode cheats (destroy all enemies and pass all rings)
            if self.CHEAT_MODE:
                # Mark all rings as passed
                for patch in self.patches:
                    if patch.get("n", -1) != -1 and not patch.get("passed", False):
                        patch["passed"] = True
                        self.ring_count += 1
                        self.score += 5
                        if patch["n"] % 3 == 1:
                            self.speed += self.SPEED_INCREMENT
                        elif patch["n"] % 3 == 2:
                            self.speed -= self.SPEED_DECREMENT
                # Destroy all sky bombs
                destroyed = len(self.sky_bombs)
                if destroyed > 0:
                    self.score += destroyed * 2
                    for i in range(len(self.sky_bombs)):
                        self.sky_bombs[i] = self._new_sky_bomb()
        elif key_pressed == b"f":
            # F key - toggle first-person view
            self.first_person = not self.first_person
        elif key_pressed in (b"h", b"H"):
            # H key - raise the shield while held. Guarded so GLUT's
            # keyboard auto-repeat (which keeps re-firing this callback
            # while the key stays down) doesn't reset the hold timer.
            if not self.shield_key_down:
                self.shield_key_down = True
                self.shield_active = True
                self.shield_press_start = self.current_time_seconds()

        glutPostRedisplay()

    def key_up(self, key_pressed, x, y):
        """Handle key-release events - currently just lowers the shield
        when H is let go."""
        if key_pressed in (b"h", b"H"):
            self.shield_key_down = False
            self.shield_active = False
            self.shield_press_start = None
        glutPostRedisplay()

    def timer(self, value):
        """Timer callback for frame updates - 60 FPS"""
        glutPostRedisplay()
        glutTimerFunc(1000 // 60, self.timer, 0)

    def run(self):
        """Initialize OpenGL and start the game loop"""
        glutInit(sys.argv)
        glutInitWindowPosition(0, 0)
        glutInitWindowSize(window_width, window_height)
        glutInitDisplayMode(GLUT_RGB | GLUT_DOUBLE | GLUT_DEPTH | GLUT_RGBA)
        self.window = glutCreateWindow(b"Dragon Racing Game")

        # Initialize game objects
        self.init_rain()
        self.init_snow()
        self.init_bomb_boxes()
        self.init_sky_bombs()

        # Register callback functions
        glutReshapeFunc(self.resize)
        glutDisplayFunc(self.display)
        glutKeyboardFunc(self.key)
        glutKeyboardUpFunc(self.key_up)
        glutMouseFunc(self.mouse)
        glutSpecialFunc(self.special_keys)
        glutTimerFunc(0, self.timer, 0)

        if callable(glEnable):
            safe_call(glEnable, GL_CULL_FACE)
            safe_call(glCullFace, GL_BACK)
            safe_call(glEnable, GL_DEPTH_TEST)
            safe_call(glDepthFunc, GL_LESS)
            safe_call(glEnable, GL_LIGHT0)
            safe_call(glEnable, GL_NORMALIZE)
            safe_call(glEnable, GL_COLOR_MATERIAL)
            safe_call(glEnable, GL_LIGHTING)
            safe_call(glMatrixMode, GL_PROJECTION)
            safe_call(glLoadIdentity)
            aspect_ratio = window_width / float(window_height)
            safe_call(glFrustum, -aspect_ratio, aspect_ratio, -1.0, 1.0, 2.0, 1000.0)
            safe_call(glMatrixMode, GL_MODELVIEW)
        else:
            print()

        # Start game loop
        glutMainLoop()

    def current_time_seconds(self):
        """Get elapsed time in seconds since GLUT initialization"""
        return time.time() - self.game_start_time

    def mouse(self, button, state, x, y):
        """Handle mouse clicks: shooting in-game, or the start screen's
        "i" info icon before the game has started."""
        if state != GLUT_DOWN:
            return

        if not self.START and not self.GAME_OVER:
            # Start screen: GLUT's y is measured from the top of the
            # window, but the icon and button (like draw_text) are
            # positioned in bottom-up gl coordinates, so flip it before
            # hit-testing.
            gl_x = x
            gl_y = window_height - y
            icon_cx = window_width - self.INFO_ICON_MARGIN
            icon_cy = window_height - self.INFO_ICON_MARGIN
            if button == GLUT_LEFT_BUTTON:
                btn_rect = getattr(self, "_start_button_rect", None)
                on_button = btn_rect is not None and (
                    btn_rect[0] <= gl_x <= btn_rect[1] and btn_rect[2] <= gl_y <= btn_rect[3]
                )
                on_icon = (gl_x - icon_cx) ** 2 + (
                    gl_y - icon_cy
                ) ** 2 <= self.INFO_ICON_RADIUS**2
                if on_button:
                    # Clicking PLAY starts the game, same as pressing G
                    self.start_game()
                elif on_icon:
                    self.SHOW_INSTRUCTIONS = not self.SHOW_INSTRUCTIONS
                elif self.SHOW_INSTRUCTIONS:
                    # Clicking anywhere else closes an open panel
                    self.SHOW_INSTRUCTIONS = False
            glutPostRedisplay()
            return

        if self.GAME_OVER:
            return

        if button == GLUT_LEFT_BUTTON:
            # Fire bullet from lower gun
            bullet_x = -self.translation_x + self.LOWER_GUN_WORLD_OFFSET_X
            bullet_y = 1 - self.translation_y + self.LOWER_GUN_WORLD_OFFSET_Y
            bullet_z = self.LOWER_GUN_WORLD_OFFSET_Z
            self.bullets.append([bullet_x, bullet_y, bullet_z])
            self.bullets_fired += 1
        elif button == GLUT_RIGHT_BUTTON:
            # Drop bomb
            self.bombs.append([-self.translation_x, 1 - self.translation_y, 0])

        glutPostRedisplay()

    def draw_start_menu(self):
        """Draw the start screen: a warm banner behind a drop-shadowed
        title, a welcome line, a button-styled start prompt, and the
        info icon. Replaces the old bare white screen with plain text."""
        glDisable(GL_LIGHTING)
        glDisable(GL_DEPTH_TEST)

        cx = window_width / 2
        cy = window_height / 2

        # --- Warm banner band behind the title, with a thin accent rule
        # along its bottom edge ---
        glMatrixMode(GL_PROJECTION)
        glPushMatrix()
        glLoadIdentity()
        gluOrtho2D(0, window_width, 0, window_height)
        glMatrixMode(GL_MODELVIEW)
        glPushMatrix()
        glLoadIdentity()

        banner_top = cy + 110
        banner_bottom = cy - 10
        glBegin(GL_QUADS)
        glColor3f(1.0, 0.93, 0.78)
        glVertex2f(0, banner_top)
        glVertex2f(window_width, banner_top)
        glColor3f(1.0, 1.0, 1.0)
        glVertex2f(window_width, banner_bottom)
        glVertex2f(0, banner_bottom)
        glEnd()

        glColor3f(0.75, 0.15, 0.08)
        glLineWidth(2.0)
        glBegin(GL_LINES)
        glVertex2f(0, banner_bottom)
        glVertex2f(window_width, banner_bottom)
        glEnd()

        glPopMatrix()
        glMatrixMode(GL_PROJECTION)
        glPopMatrix()
        glMatrixMode(GL_MODELVIEW)

        # --- Title, with a soft drop shadow for some depth ---
        title = "DRAGON RACING GAME"
        title_font = GLUT_BITMAP_TIMES_ROMAN_24
        title_char_w = 13.0
        title_x = cx - len(title) * title_char_w / 2
        title_y = cy + 55
        self.draw_text(title_x + 2, title_y - 2, title, font=title_font, color=(0.55, 0.5, 0.45), bold=True)
        self.draw_text(title_x, title_y, title, font=title_font, color=(0.72, 0.12, 0.05), bold=True)

        # --- Welcome subtitle ---
        subtitle = "Welcome to Dragon Racing Game"
        sub_font = GLUT_BITMAP_HELVETICA_18
        sub_char_w = 9.5
        sub_x = cx - len(subtitle) * sub_char_w / 2
        sub_y = cy + 15
        self.draw_text(sub_x, sub_y, subtitle, font=sub_font, color=(0.3, 0.24, 0.18))

        # --- "PLAY" button - also clickable (see mouse()), so the
        # rect is stashed on self for hit-testing there.
        btn_w, btn_h = 160.0, 50.0
        btn_left = cx - btn_w / 2
        btn_right = cx + btn_w / 2
        btn_bottom = cy - 75.0
        btn_top = btn_bottom + btn_h
        self._start_button_rect = (btn_left, btn_right, btn_bottom, btn_top)

        glMatrixMode(GL_PROJECTION)
        glPushMatrix()
        glLoadIdentity()
        gluOrtho2D(0, window_width, 0, window_height)
        glMatrixMode(GL_MODELVIEW)
        glPushMatrix()
        glLoadIdentity()

        glColor3f(0.1, 0.55, 0.22)
        glBegin(GL_QUADS)
        glVertex2f(btn_left, btn_bottom)
        glVertex2f(btn_right, btn_bottom)
        glVertex2f(btn_right, btn_top)
        glVertex2f(btn_left, btn_top)
        glEnd()

        glColor3f(1.0, 1.0, 1.0)
        glLineWidth(2.0)
        glBegin(GL_LINE_LOOP)
        glVertex2f(btn_left, btn_bottom)
        glVertex2f(btn_right, btn_bottom)
        glVertex2f(btn_right, btn_top)
        glVertex2f(btn_left, btn_top)
        glEnd()

        glPopMatrix()
        glMatrixMode(GL_PROJECTION)
        glPopMatrix()
        glMatrixMode(GL_MODELVIEW)

        btn_text = "PLAY"
        btn_font = GLUT_BITMAP_HELVETICA_18
        btn_char_w = 11.0
        btn_text_x = cx - len(btn_text) * btn_char_w / 2
        btn_text_y = btn_bottom + btn_h / 2 - 6
        self.draw_text(btn_text_x, btn_text_y, btn_text, font=btn_font, color=(1.0, 1.0, 1.0), bold=True)

        # --- Info icon, a label pointing at it, and its instructions
        # panel (which now also lists E - exit) ---
        icon_cx = window_width - self.INFO_ICON_MARGIN
        icon_cy = window_height - self.INFO_ICON_MARGIN

        hint_text = "Click this icon for game details."
        hint_font = GLUT_BITMAP_9_BY_15
        hint_char_w = 9.0
        hint_gap = 12.0
        hint_x = icon_cx - self.INFO_ICON_RADIUS - hint_gap - len(hint_text) * hint_char_w
        hint_y = icon_cy - 5.0
        self.draw_text(hint_x, hint_y, hint_text, font=hint_font, color=(0.3, 0.3, 0.3))

        self.draw_info_icon(icon_cx, icon_cy, self.INFO_ICON_RADIUS)
        if self.SHOW_INSTRUCTIONS:
            self.draw_instructions_panel()

        glEnable(GL_DEPTH_TEST)
        glEnable(GL_LIGHTING)

    def draw_info_icon(self, cx, cy, radius):
        """Draw a small circular "i" info button in 2D screen space."""
        glMatrixMode(GL_PROJECTION)
        glPushMatrix()
        glLoadIdentity()
        gluOrtho2D(0, window_width, 0, window_height)
        glMatrixMode(GL_MODELVIEW)
        glPushMatrix()
        glLoadIdentity()

        glColor3f(0.15, 0.35, 0.78)
        glBegin(GL_TRIANGLE_FAN)
        glVertex2f(cx, cy)
        for i in range(25):
            angle = 2 * math.pi * i / 24
            glVertex2f(cx + radius * math.cos(angle), cy + radius * math.sin(angle))
        glEnd()

        glColor3f(1.0, 1.0, 1.0)
        glLineWidth(2.0)
        glBegin(GL_LINE_LOOP)
        for i in range(24):
            angle = 2 * math.pi * i / 24
            glVertex2f(cx + radius * math.cos(angle), cy + radius * math.sin(angle))
        glEnd()

        glPopMatrix()
        glMatrixMode(GL_PROJECTION)
        glPopMatrix()
        glMatrixMode(GL_MODELVIEW)

        self.draw_text(cx - 3, cy - 6, "i", font=GLUT_BITMAP_HELVETICA_18, color=(1.0, 1.0, 1.0))

    def draw_sky_bodies(self):
        """Draw the sun (day) or moon (night) as a real object out in
        the world - not a 2D screen overlay. Because it's genuine 3D
        geometry rendered with the normal depth test (like everything
        else in the scene), mountains and trees drawn elsewhere in the
        render correctly occlude it whenever they're actually in front
        of it, the same way they occlude a boat or a ring target. And
        because its position is a fixed point in world space rather than
        anything tied to self.translation_x/y, it only shifts on screen
        when the camera itself turns (arrow keys, or the first-person
        toggle) - never from plain WASD steering, which only scrolls the
        nearby terrain past a dragon and camera that never actually
        move. That matches how a real sun or moon behaves: it doesn't
        drift because you glanced left, only because you actually turned
        your head."""
        glDisable(GL_LIGHTING)
        if self.is_night:
            self.draw_moon()
        else:
            self.draw_sun()
        glEnable(GL_LIGHTING)

    def draw_sun(self):
        """The sun: a soft glow sphere behind a smaller solid core
        sphere, both unlit so they read as bright regardless of the
        scene's lighting."""
        glPushMatrix()
        glTranslated(*self.SUN_WORLD_POS)
        glColor3f(1.0, 0.95, 0.55)
        glutSolidSphere(self.SKY_BODY_RADIUS * 1.35, 20, 20)
        glColor3f(1.0, 0.78, 0.05)
        glutSolidSphere(self.SKY_BODY_RADIUS, 20, 20)
        glPopMatrix()

    def draw_moon(self):
        """The moon: a pale sphere with a second sphere offset toward
        the camera and painted in the sky's current color, cutting a
        crescent shape out of it - since that cutout only ever shows up
        where the pale sphere itself was actually visible (i.e. real
        open sky, nothing already drawn there), painting it in the
        current sky color blends it in seamlessly rather than leaving a
        visible patch."""
        radius = self.SKY_BODY_RADIUS
        glPushMatrix()
        glTranslated(*self.MOON_WORLD_POS)
        glColor3f(0.92, 0.92, 0.88)
        glutSolidSphere(radius, 24, 24)

        glColor3f(*getattr(self, "_current_sky_rgb", (0.03, 0.05, 0.25)))
        glPushMatrix()
        glTranslated(radius * 0.55, radius * 0.32, radius * 0.55)
        glutSolidSphere(radius * 0.92, 24, 24)
        glPopMatrix()
        glPopMatrix()

    def draw_instructions_panel(self):
        """Draw the instructions overlay opened from the start screen's
        "i" button."""
        panel_left = window_width / 2 - 250
        panel_right = window_width / 2 + 250
        panel_bottom = window_height / 2 - 190
        panel_top = window_height / 2 + 190

        glMatrixMode(GL_PROJECTION)
        glPushMatrix()
        glLoadIdentity()
        gluOrtho2D(0, window_width, 0, window_height)
        glMatrixMode(GL_MODELVIEW)
        glPushMatrix()
        glLoadIdentity()

        # Fully opaque so the "DRAGON GAME" / "Press G to Start" text drawn
        # underneath on the start screen can't ghost through the panel.
        glColor3f(0.05, 0.05, 0.08)
        glBegin(GL_QUADS)
        glVertex2f(panel_left, panel_bottom)
        glVertex2f(panel_right, panel_bottom)
        glVertex2f(panel_right, panel_top)
        glVertex2f(panel_left, panel_top)
        glEnd()

        glColor3f(1.0, 1.0, 1.0)
        glLineWidth(2.0)
        glBegin(GL_LINE_LOOP)
        glVertex2f(panel_left, panel_bottom)
        glVertex2f(panel_right, panel_bottom)
        glVertex2f(panel_right, panel_top)
        glVertex2f(panel_left, panel_top)
        glEnd()

        glPopMatrix()
        glMatrixMode(GL_PROJECTION)
        glPopMatrix()
        glMatrixMode(GL_MODELVIEW)

        lines = [
            "HOW TO PLAY",
            "",
            "W / S / A / D - move up / down / left / right",
            "Mouse left-click - breathe fire (shoot)",
            "Mouse right-click / B - drop an egg bomb",
            "H (hold) - raise a golden shield, but don't",
            "  hold it more than 5 seconds or it overloads",
            "F - toggle first-person view",
            "N / M / L - force day / night / auto-cycle",
            "E - exit the game (works any time)",
            "",
            "Fly through fire rings, clouds, and leaves for",
            "score and +10 seconds on the clock",
            "Avoid birds, boats, and their cannonballs -",
            "watch for the on-screen warning before a hit",
            "",
            "Click the i icon again to close",
        ]
        line_height = 20
        start_y = window_height / 2 + 170
        for idx, line in enumerate(lines):
            self.draw_text(
                window_width / 2 - 240,
                start_y - idx * line_height,
                line,
                font=GLUT_BITMAP_9_BY_15,
                color=(1.0, 1.0, 1.0),
            )

    def _draw_wing_membrane(self, side):
        """Draw one wide, bat-style wing as a fan of triangles from the
        shoulder out to the wingtip, with a scalloped (notched) trailing
        edge between finger bones — this is what makes it read as a
        membrane wing instead of a flat panel.

        Local coordinates here (before the caller's rotations are applied):
        x = chordwise (positive = toward the leading edge / front),
        z = spanwise (distance out from the shoulder toward the tip).
        """
        # Leading edge bulges forward at the "elbow" partway out, then
        # curves into a rounded tip, then the trailing edge comes back
        # with broad, rounded scalloped lobes (not thin needle spikes) -
        # a stout, broad panel rather than a narrow blade.
        boundary = [
            (0.5, 0.2),
            (0.65, 1.0),  # forward elbow bulge
            (0.5, 1.9),
            (0.1, 2.6),
            (-0.25, 2.85),  # rounded wingtip
            (-0.95, 2.5),  # outer trailing lobe
            (-0.65, 2.05),  # notch
            (-1.15, 1.7),  # lobe
            (-0.8, 1.2),  # notch
            (-1.05, 0.75),  # lobe
            (-0.7, 0.35),  # notch
            (-0.85, 0.05),  # lobe, near the root
        ]
        # Mirroring the wing by negating z also flips its winding order, so
        # walk the boundary in reverse on the mirrored side to keep both
        # wings wound the same way.
        ordered_boundary = boundary if side > 0 else list(reversed(boundary))

        # The membrane is a single flat sheet with one normal direction, so
        # it can only ever be "correct" (backface-culled and properly lit)
        # from one side - that's what made it look different depending on
        # which way the camera or the dragon itself was facing. Since this
        # is a thin membrane rather than a solid, there's no real "back" to
        # hide: draw it with culling and lighting both off so it renders as
        # the same flat wing_color shape from every angle, consistently.
        glDisable(GL_LIGHTING)
        glDisable(GL_CULL_FACE)
        glBegin(GL_TRIANGLE_FAN)
        glNormal3f(0, 1, 0)
        glVertex3f(0, 0, 0)
        for x, z in ordered_boundary:
            # Slight upward camber toward the tip so the membrane isn't dead flat
            y = 0.05 * (z / 2.85)
            glVertex3f(x, y, side * z)
        glEnd()
        glEnable(GL_CULL_FACE)
        glEnable(GL_LIGHTING)

    def plane(self):
        """Draw the player's dragon: a sleek, low black dragon with wide
        bat-style wings, big round eyes and a short flat-snouted head."""
        elapsed_time = self.current_time_seconds()
        # Rest angle is a shallow dihedral (wings mostly spread out to the
        # sides, tips slightly up) with the flap swinging above and below
        # it - not a fold that hides the wing under the body.
        wing_flap = math.sin(elapsed_time * 6.0) * 25.0
        tail_sway = math.sin(elapsed_time * 3.0) * 8.0

        if self.shield_active:
            # Shield up (holding "H"): the whole dragon glows gold so the
            # protection is obvious at a glance, not just the HUD readout.
            body_color = (1.0, 0.78, 0.1)  # golden scales
            belly_color = (1.0, 0.9, 0.55)  # pale gold underbelly
            horn_color = (0.75, 0.52, 0.05)  # bronze-gold horns/ear-fins
            eye_color = (1.0, 0.95, 0.7)  # bright, near-white glow
            wing_color = (0.85, 0.62, 0.05)  # gold wing membrane
            claw_color = (0.55, 0.38, 0.04)  # dark gold claws
        else:
            body_color = (0.04, 0.04, 0.045)  # black scales, full body
            belly_color = (0.14, 0.14, 0.16)  # slightly lighter charcoal underbelly
            horn_color = (0.55, 0.03, 0.05)  # deep red horns/ear-fins
            eye_color = (1.0, 0.78, 0.05)  # golden eyes, kept for contrast
            wing_color = (0.02, 0.02, 0.02)  # black wing membrane
            claw_color = (0.05, 0.05, 0.05)  # near-black claws

        # Body: slim, elongated torso (longer and narrower than before)
        glColor3d(*body_color)
        glPushMatrix()
        glScaled(2.15, 0.6, 0.6)
        glutSolidSphere(1, 28, 28)
        glPopMatrix()

        # Belly (slightly lighter underside)
        glColor3d(*belly_color)
        glPushMatrix()
        glTranslated(0, -0.35, 0)
        glScaled(1.8, 0.24, 0.4)
        glutSolidSphere(1, 20, 20)
        glPopMatrix()

        # Head: short and wide, sitting almost directly on the body
        glColor3d(*body_color)
        glPushMatrix()
        glTranslated(2.0, 0.35, 0)
        glScaled(0.85, 0.6, 0.75)
        glutSolidSphere(1, 22, 22)
        glPopMatrix()

        # Flat, short snout/jaw (not a pointed cone - Toothless-style flat face)
        glPushMatrix()
        glTranslated(2.75, 0.18, 0)
        glScaled(0.55, 0.3, 0.58)
        glutSolidCube(1)
        glPopMatrix()

        # Small triangular ear fins on top of the head. Flat single-sided
        # triangles, same as the wings - lighting/culling off so they look
        # the same dark horn color from every viewing angle.
        glColor3d(*horn_color)
        glDisable(GL_LIGHTING)
        glDisable(GL_CULL_FACE)
        for side in (-1, 1):
            glPushMatrix()
            glTranslated(1.85, 0.85, side * 0.35)
            glRotated(-15, 0, 0, 1)
            glRotated(side * 30, 1, 0, 0)
            glBegin(GL_TRIANGLES)
            glNormal3f(0, 0, 1)
            glVertex3f(0, 0, 0)
            glVertex3f(0.1, 0.5, -0.15)
            glVertex3f(-0.05, 0.5, 0.2)
            glEnd()
            glPopMatrix()
        glEnable(GL_CULL_FACE)
        glEnable(GL_LIGHTING)

        # Big round eyes (golden, with a black pupil)
        for side in (-1, 1):
            glColor3d(*eye_color)
            glPushMatrix()
            glTranslated(2.28, 0.45, side * 0.44)
            glutSolidSphere(0.14, 12, 12)
            glPopMatrix()
            glColor3d(0.0, 0.0, 0.0)
            glPushMatrix()
            glTranslated(2.37, 0.45, side * 0.5)
            glutSolidSphere(0.06, 8, 8)
            glPopMatrix()

        # Wings: broad bat-style membranes with rounded, scalloped lobes,
        # spread out nearly flat to the sides (like a soaring dragon seen
        # from above) rather than swept back into thin trailing blades.
        glColor3d(*wing_color)
        for side in (-1, 1):
            glPushMatrix()
            glTranslated(0.4, 0.5, side * 0.4)
            glRotated(side * (8 + wing_flap), 1, 0, 0)  # shallow dihedral + flap
            glRotated(side * 8, 0, 1, 0)  # only a slight sweep, not swept-back
            glScaled(1.5, 1.3, 1.6)  # bigger, but keeping the broad proportions
            self._draw_wing_membrane(side)
            glPopMatrix()

        # Legs: four sturdy, slightly bent legs with clawed paws
        glColor3d(*body_color)
        leg_specs = [
            (1.1, -0.5, 0.42),
            (1.1, -0.5, -0.42),
            (-0.9, -0.5, 0.38),
            (-0.9, -0.5, -0.38),
        ]
        for lx, ly, lz in leg_specs:
            side = 1 if lz > 0 else -1
            glPushMatrix()
            glTranslated(lx, ly, lz)
            glScaled(0.28, 0.55, 0.28)
            glutSolidCube(1)
            glPopMatrix()
            # Paw
            glPushMatrix()
            glTranslated(lx, ly - 0.32, lz + side * 0.15)
            glScaled(0.3, 0.12, 0.35)
            glutSolidCube(1)
            glPopMatrix()
            # Claws (three small cones per paw)
            glColor3d(*claw_color)
            for claw_offset in (-0.1, 0.0, 0.1):
                glPushMatrix()
                glTranslated(lx + 0.15, ly - 0.38, lz + side * 0.15 + claw_offset)
                glRotated(90, 0, 1, 0)
                glScaled(0.05, 0.05, 0.05)
                glutSolidCone(0.4, 0.6, 6, 6)
                glPopMatrix()
            glColor3d(*body_color)

        # Tail: long tapering tail that sways, ending in twin fin flukes
        glColor3d(*body_color)
        tail_segments = 6
        for i in range(tail_segments):
            t = (i + 1) / float(tail_segments)
            seg_x = -1.8 - t * 2.6
            seg_z = math.sin(math.radians(tail_sway) * t * 2.0) * 0.5
            scale = 0.4 * (1 - t * 0.7)
            glPushMatrix()
            glTranslated(seg_x, -0.05, seg_z)
            glScaled(scale, scale, scale)
            glutSolidSphere(1, 12, 12)
            glPopMatrix()

        tail_tip_z = math.sin(math.radians(tail_sway) * 2.0) * 0.5
        glColor3d(*wing_color)
        # Same flat single-sided triangle as the wings and ear fins -
        # lighting/culling off so both fin flukes look the same from any
        # viewing angle instead of one going dark or vanishing.
        glDisable(GL_LIGHTING)
        glDisable(GL_CULL_FACE)
        glPushMatrix()
        glTranslated(-4.4, -0.05, tail_tip_z)
        for side in (-1, 1):
            glPushMatrix()
            glRotated(side * 30, 1, 0, 0)
            glBegin(GL_TRIANGLES)
            glNormal3f(0, 1, 0)
            # Same z-mirroring winding-flip as the wings above - swap the
            # last two vertices on the mirrored side so both flukes are
            # wound the same way.
            if side > 0:
                glVertex3f(0, 0, 0)
                glVertex3f(-0.7, 0.0, side * 0.7)
                glVertex3f(-0.3, 0.0, side * 0.15)
            else:
                glVertex3f(0, 0, 0)
                glVertex3f(-0.3, 0.0, side * 0.15)
                glVertex3f(-0.7, 0.0, side * 0.7)
            glEnd()
            glPopMatrix()
        glPopMatrix()
        glEnable(GL_CULL_FACE)
        glEnable(GL_LIGHTING)

    def draw_leaf_square_target(self, tint):
        """Draw the square target as a pointed, veined leaf blade. The base
        leaf-green is blended with the gameplay tint color (green/orange/
        blue) so the ring's speed effect is still readable at a glance."""
        leaf_color = (
            0.15 * 0.6 + tint[0] * 0.4,
            0.55 * 0.6 + tint[1] * 0.4,
            0.1 * 0.6 + tint[2] * 0.4,
        )
        vein_color = (leaf_color[0] * 0.6, leaf_color[1] * 0.6, leaf_color[2] * 0.6)

        # Leaf blade boundary: pointed tip and base, bulging sides -
        # roughly matches the old square target's -2..2 extents.
        boundary = [
            (0.0, 2.2),
            (1.1, 1.3),
            (1.6, 0.3),
            (1.1, -1.0),
            (0.0, -2.2),
            (-1.1, -1.0),
            (-1.6, 0.3),
            (-1.1, 1.3),
        ]

        glDisable(GL_LIGHTING)
        glDisable(GL_CULL_FACE)
        glColor3f(*leaf_color)
        glBegin(GL_TRIANGLE_FAN)
        glVertex3f(0.0, 0.0, 0.0)
        for x, y in boundary + [boundary[0]]:
            glVertex3f(x, y, 0.0)
        glEnd()

        # Center vein plus a few side veins
        glColor3f(*vein_color)
        glLineWidth(3.0)
        glBegin(GL_LINE_STRIP)
        glVertex3f(0.0, 2.2, 0.0)
        glVertex3f(0.0, -2.2, 0.0)
        glEnd()
        for y in (1.0, 0.2, -0.7):
            glBegin(GL_LINE_STRIP)
            glVertex3f(0.0, y, 0.0)
            glVertex3f(1.2, y - 0.6, 0.0)
            glEnd()
            glBegin(GL_LINE_STRIP)
            glVertex3f(0.0, y, 0.0)
            glVertex3f(-1.2, y - 0.6, 0.0)
            glEnd()

        glEnable(GL_CULL_FACE)
        glEnable(GL_LIGHTING)

    def draw_cloud_triangle_target(self, tint):
        """Draw the triangle target as a hollow ring of cloud puffs - like
        the fire ring, a passable hoop with an open middle, not a filled-in
        cloud blob the dragon would have to fly into."""
        cloud_radius = 2.0
        puff_count = 14

        # Tinted base hoop (same treatment as the fire ring) so the
        # gameplay speed-effect color still reads through the puffs.
        glDisable(GL_LIGHTING)
        glColor3f(*tint)
        glLineWidth(5.0)
        glBegin(GL_LINE_LOOP)
        for i in range(36):
            angle = 2 * math.pi * i / 36
            glVertex3f(cloud_radius * math.cos(angle), cloud_radius * math.sin(angle), 0.0)
        glEnd()
        glEnable(GL_LIGHTING)

        # Puffs traced only around the rim, leaving the center empty.
        glColor3f(0.95, 0.95, 0.97)
        for i in range(puff_count):
            angle = 2 * math.pi * i / puff_count
            wobble = 0.15 * math.sin(angle * 3.0 + 1.0)
            r = cloud_radius + wobble
            puff_size = 0.55 + 0.15 * math.sin(angle * 5.0 + 2.0)
            x = r * math.cos(angle)
            y = r * math.sin(angle)
            glPushMatrix()
            glTranslated(x, y, 0.0)
            glutSolidSphere(puff_size, 10, 10)
            glPopMatrix()

    def draw_fire_ring_target(self, tint):
        """Draw the circular target as a hoop of flickering fire. The
        flame's base color is blended toward the gameplay tint color so the
        green/orange/blue speed-effect coding stays readable."""
        elapsed_time = self.current_time_seconds()
        ring_radius = 2.0
        flame_count = 20

        glDisable(GL_LIGHTING)
        glDisable(GL_CULL_FACE)

        # Base hoop of embers the flames rise from
        glColor3f(
            0.35 * 0.5 + tint[0] * 0.5,
            0.08 * 0.5 + tint[1] * 0.5,
            0.02 * 0.5 + tint[2] * 0.5,
        )
        glLineWidth(6.0)
        glBegin(GL_LINE_LOOP)
        for i in range(36):
            angle = 2 * math.pi * i / 36
            glVertex3f(ring_radius * math.cos(angle), ring_radius * math.sin(angle), 0.0)
        glEnd()

        # Flame tongues licking outward from the hoop, each with its own
        # flicker phase so the ring doesn't pulse in perfect unison.
        for i in range(flame_count):
            angle = 2 * math.pi * i / flame_count
            flicker = math.sin(elapsed_time * 9.0 + i * 2.1)
            length = 0.5 + 0.25 * abs(flicker)
            lean = 0.12 * flicker
            cos_a, sin_a = math.cos(angle), math.sin(angle)
            base_l_angle = angle - 0.09
            base_r_angle = angle + 0.09
            base_l = (
                ring_radius * math.cos(base_l_angle),
                ring_radius * math.sin(base_l_angle),
            )
            base_r = (
                ring_radius * math.cos(base_r_angle),
                ring_radius * math.sin(base_r_angle),
            )
            tip = (
                (ring_radius + length) * cos_a - lean * sin_a,
                (ring_radius + length) * sin_a + lean * cos_a,
            )

            glColor3f(
                0.85 * 0.6 + tint[0] * 0.4,
                (0.25 + 0.1 * abs(flicker)) * 0.6 + tint[1] * 0.4,
                0.03 * 0.6 + tint[2] * 0.4,
            )
            glBegin(GL_TRIANGLES)
            glVertex3f(base_l[0], base_l[1], 0.0)
            glVertex3f(base_r[0], base_r[1], 0.0)
            glVertex3f(tip[0], tip[1], 0.0)
            glEnd()

            # Bright core lick nested inside the outer flame
            core_tip = (
                (ring_radius + length * 0.55) * cos_a - lean * 0.5 * sin_a,
                (ring_radius + length * 0.55) * sin_a + lean * 0.5 * cos_a,
            )
            glColor3f(1.0, 0.85, 0.35)
            glBegin(GL_TRIANGLES)
            glVertex3f(base_l[0] * 0.97 + cos_a * 0.03, base_l[1] * 0.97 + sin_a * 0.03, 0.0)
            glVertex3f(base_r[0] * 0.97 + cos_a * 0.03, base_r[1] * 0.97 + sin_a * 0.03, 0.0)
            glVertex3f(core_tip[0], core_tip[1], 0.0)
            glEnd()

        glEnable(GL_CULL_FACE)
        glEnable(GL_LIGHTING)

    def environment(
        self,
        ring_index,
        grid_size,
        terrain_grid,
        ring_x_positions,
        ring_y_positions,
        shape,
    ):
        """Draw a game world patch with terrain, a river, buildings, and ring target"""
        # Width of the flight corridor between the mountains on each side -
        # shared with the mountain-placement loop below so the river lines
        # up exactly with the gap between the two mountain ranges.
        lane_half_width = 8

        # River running down the flight corridor (replaces the flat road)
        elapsed_time = self.current_time_seconds()
        shimmer = 0.06 * math.sin(elapsed_time * 2.0)
        glColor3d(0.09 + shimmer, 0.4 + shimmer, 0.68 + shimmer * 0.6)
        glPushMatrix()
        glTranslated(0, 0, 0)
        glScaled(lane_half_width * 2, 0.3, grid_size * 2)
        glutSolidCube(1)
        glPopMatrix()

        # Grassy banks on either side of the river (tan/brown color)
        bank_width = grid_size - lane_half_width
        bank_center = (grid_size + lane_half_width) / 2.0
        glColor3d(0.82, 0.71, 0.55)
        for bank_side in (-1, 1):
            glPushMatrix()
            glTranslated(bank_side * bank_center, 0, 0)
            glScaled(bank_width, 0.3, grid_size * 2)
            glutSolidCube(1)
            glPopMatrix()

        # Select ring color based on ring index
        ring_color = [0.0, 1.0, 0.1]  # Green default
        if ring_index % 3 == 1:
            ring_color = [1.0, 0.5, 0.0]  # Orange (speed boost)
        elif ring_index % 3 == 2:
            ring_color = [0.0, 0.5, 1.0]  # Blue (speed decrease)

        # Draw the ring target: a fire ring for "ring", a cloud for
        # "triangle", a leaf for "square" - each still tinted by ring_color
        # so the speed-boost/decrease coding stays readable.
        glPushMatrix()
        glTranslated(ring_x_positions[ring_index], ring_y_positions[ring_index], 0)
        glScaled(0.3, 0.3, 0.3)
        if shape == "ring":
            self.draw_fire_ring_target(ring_color)
        elif shape == "square":
            self.draw_leaf_square_target(ring_color)
        elif shape == "triangle":
            self.draw_cloud_triangle_target(ring_color)
        glPopMatrix()

        # Draw buildings and mountains in grid pattern
        for i in range(-(grid_size // 2) + 1, (grid_size // 2), 2):
            if -lane_half_width < i < lane_half_width:
                continue  # Skip center lane (flight path)
            for j in range(-(grid_size // 2) + 1, (grid_size // 2), 2):
                if abs(i) > 4 or abs(j) > 4:
                    # Draw mountain at this position
                    glPushMatrix()
                    glTranslated(i, 0, j)
                    self.drawTree(i, j)
                    glPopMatrix()
                elif terrain_grid[i + (grid_size // 2)][j + (grid_size // 2)] != 0:
                    # Draw building with existing height
                    glPushMatrix()
                    glTranslated(i, 0, j)
                    height = terrain_grid[i + (grid_size // 2)][j + (grid_size // 2)]
                    # self.house(height, i, j)
                    glPopMatrix()
                else:
                    # Generate and draw new building
                    height = (abs(i * j) % 5) + 1
                    terrain_grid[i + (grid_size // 2)][j + (grid_size // 2)] = height
                    glPushMatrix()
                    glTranslated(i, 0, j)
                    # self.house(height, i, j)
                    glPopMatrix()

        # Beyond that first mountain row was just bare, empty bank ground
        # all the way out to the edge of the world - fill it in with more
        # mountains instead of leaving it open. These use a much cheaper,
        # lower-detail mountain (drawDistantMountain) rather than stamping
        # more full-detail drawTree() copies, since drawTree is already
        # fairly expensive (8 tessellated cones each) and multiplying that
        # by several more columns per side visibly tanks the frame rate.
        for i in range(grid_size // 2, grid_size, 2):
            for side in (-1, 1):
                gx = side * i
                for j in range(-(grid_size // 2) + 1, (grid_size // 2), 2):
                    glPushMatrix()
                    glTranslated(gx, 0, j)
                    self.drawDistantMountain(gx, j)
                    glPopMatrix()

    def _peak_rand(self, gx, gz, salt):
        """Deterministic pseudo-random value in [0, 1) seeded by grid position.

        Using a hash instead of random.random() keeps each mountain's shape
        stable across frames (environment() redraws every frame) while still
        giving every grid position its own look.
        """
        value = math.sin(gx * 12.9898 + gz * 78.233 + salt * 37.719) * 43758.5453
        return value - math.floor(value)

    def drawTree(self, gx=0, gz=0):
        """Draw one irregular, uneven mountain: a cluster of overlapping,
        unevenly sized peaks, some rocky and bare, some green and forested."""
        rnd = lambda salt: self._peak_rand(gx, gz, salt)

        is_forested = rnd(0) < 0.45

        if is_forested:
            # Green, tree-covered slopes with exposed brownish rock near the top
            base_color = (0.16 + rnd(1) * 0.08, 0.32 + rnd(2) * 0.16, 0.11 + rnd(3) * 0.06)
            cap_color = (0.40 + rnd(4) * 0.08, 0.36 + rnd(4) * 0.06, 0.28 + rnd(4) * 0.05)
        else:
            # Bare rocky stone, capped with lighter, almost-snowy stone at the peak
            gray = 0.38 + rnd(1) * 0.22
            base_color = (gray, gray * 0.94, gray * 0.9)
            cap_color = (min(gray + 0.4, 0.97), min(gray + 0.4, 0.97), min(gray + 0.45, 1.0))

        main_height = 2.6 + rnd(5) * 2.6
        main_radius = 1.0 + rnd(6) * 0.7

        # A handful of overlapping, unevenly sized/offset cones reads as a
        # single jagged, irregular mountain instead of one perfect cone.
        peak_specs = [
            (0.0, 0.0, main_radius, main_height, 1.0),
            (
                rnd(7) * 1.4 - 0.7,
                rnd(8) * 1.4 - 0.7,
                main_radius * (0.55 + rnd(9) * 0.25),
                main_height * (0.55 + rnd(10) * 0.3),
                0.92,
            ),
            (
                rnd(11) * 1.6 - 0.8,
                rnd(12) * 1.6 - 0.8,
                main_radius * (0.4 + rnd(13) * 0.25),
                main_height * (0.35 + rnd(14) * 0.3),
                0.84,
            ),
            (
                rnd(15) * 1.6 - 0.8,
                rnd(16) * 1.6 - 0.8,
                main_radius * (0.3 + rnd(17) * 0.2),
                main_height * (0.3 + rnd(18) * 0.25),
                0.78,
            ),
        ]

        for dx, dz, radius, height, shade in peak_specs:
            # Rocky/wooded body of this peak
            glColor3d(base_color[0] * shade, base_color[1] * shade, base_color[2] * shade)
            glPushMatrix()
            glTranslated(dx, 0, dz)
            glRotated(-90, 1, 0, 0)
            glutSolidCone(radius, height, 10, 8)
            glPopMatrix()

            # Lighter cap near the summit (bare rock or snow, depending on type)
            glColor3d(cap_color[0] * shade, cap_color[1] * shade, cap_color[2] * shade)
            glPushMatrix()
            glTranslated(dx, 0, dz)
            glRotated(-90, 1, 0, 0)
            glTranslated(0, 0, height * 0.66)
            glutSolidCone(radius * 0.4, height * 0.36, 10, 8)
            glPopMatrix()

    def drawDistantMountain(self, gx=0, gz=0):
        """Cheap, low-detail mountain for the far outer band beyond the
        first mountain row. A single low-tessellation cone instead of
        drawTree()'s 4 overlapping peaks (8 cones total) - filling in a lot
        more ground this way costs far less per mountain, which matters
        since this gets stamped many more times than the near row."""
        rnd = lambda salt: self._peak_rand(gx, gz, salt)
        is_forested = rnd(0) < 0.45
        if is_forested:
            color = (0.16 + rnd(1) * 0.08, 0.32 + rnd(2) * 0.16, 0.11 + rnd(3) * 0.06)
        else:
            gray = 0.4 + rnd(1) * 0.24
            color = (gray, gray * 0.94, gray * 0.9)
        height = 3.0 + rnd(5) * 3.2
        radius = 1.1 + rnd(6) * 0.9

        glColor3d(*color)
        glPushMatrix()
        glRotated(-90, 1, 0, 0)
        glutSolidCone(radius, height, 6, 3)
        glPopMatrix()

    def special_keys(self, key, x, y):
        """Handling special keys (arrow keys) for camera control"""
        if self.GAME_OVER or not self.START:
            return

        global camera_yaw, camera_pitch, camera_distance
        step_angle = 5.0
        step_pitch = 5.0

        # Camera rotation with arrow keys
        if key == GLUT_KEY_LEFT:
            camera_yaw -= step_angle
        elif key == GLUT_KEY_RIGHT:
            camera_yaw += step_angle
        elif key == GLUT_KEY_UP:
            camera_pitch += step_pitch
            if camera_pitch > 80:
                camera_pitch = 80
        elif key == GLUT_KEY_DOWN:
            camera_pitch -= step_pitch
            if camera_pitch < -10:
                camera_pitch = -10
        glutPostRedisplay()


# Main game initialization and startup
game = Game()
game.run()