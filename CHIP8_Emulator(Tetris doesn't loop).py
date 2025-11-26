# CHIP8 Virtual Machine Steps:
# Input - store key input states and check these per cycle.
# Output - 64x32 display(array of pixels are either in the on or off state(0 || 1)) & sound buzzer.
# CPU - CowGods CHIP8 Technical reference http://devernay.free.fr/hacks/chip8/C8TECH10.HTM#0.0
# Memory - can hold up to 4096 bytes which includes: the interpreter, fonts, and inputted ROM.
#----------------------------------------------------------------------------------------------
# We will be storing register values as 16 zeros. Also, we will have two time registers
# defined by two variables that we decrement per cycle. We will also be dealing with a
# stack of 16 elements that we'll just need to make into a list.
#----------------------------------------------------------------------------------------------
# We're going to be subclassing pyglet (that'll handle graphics, sound output, and keyboard handling)
# and Overriding whatever def we need from there.
# Added numpy to several functions
# Updates: opcode, on_draw(), and controls

import sys
import random
import pyglet
from pyglet.window import key
from pyglet.media import synthesis
import numpy as np

random.seed()

#map binding keys
keymap = {
    key._1: 0x1, key._2: 0x2, key._3: 0x3, key._4: 0xC,
    key.Q: 0x4, key.W: 0x5, key.E: 0x6, key.R: 0xD,
    key.A: 0x7, key.S: 0x8, key.D: 0x9, key.F: 0xE,
    key.Z: 0xA, key.X: 0x0, key.C: 0xB, key.V: 0xF,
}

# set fonts (binary pixel patterns)
fontset = [
    0xF0, 0x90, 0x90, 0x90, 0xF0,  # 0
    0x20, 0x60, 0x20, 0x20, 0x70,  # 1
    0xF0, 0x10, 0xF0, 0x80, 0xF0,  # 2
    0xF0, 0x10, 0xF0, 0x10, 0xF0,  # 3
    0x90, 0x90, 0xF0, 0x10, 0x10,  # 4
    0xF0, 0x80, 0xF0, 0x10, 0xF0,  # 5
    0xF0, 0x80, 0xF0, 0x90, 0xF0,  # 6
    0xF0, 0x10, 0x20, 0x40, 0x40,  # 7
    0xF0, 0x90, 0xF0, 0x90, 0xF0,  # 8
    0xF0, 0x90, 0xF0, 0x10, 0xF0,  # 9
    0xF0, 0x90, 0xF0, 0x90, 0x90,  # A
    0xE0, 0x90, 0xE0, 0x90, 0xE0,  # B
    0xF0, 0x80, 0x80, 0x80, 0xF0,  # C
    0xE0, 0x90, 0x90, 0x90, 0xE0,  # D
    0xF0, 0x80, 0xF0, 0x80, 0xF0,  # E
    0xF0, 0x80, 0xF0, 0x80, 0x80   # F
] #notice 80 bytes

#  configuration
scale = 10
width, height = 64, 32
window_width, window_height = width * scale, height * scale
CPU_HZ = 600
timer_HZ = 60

def generate_beep(duration=0.1, frequency=440, sample_rate=44100):
    wave = synthesis.Sine(duration=duration, frequency=frequency, sample_rate=sample_rate)
    return pyglet.media.StaticSource(wave)


class Chip8(pyglet.window.Window):

    def __init__(self, romname):
        super().__init__(
            width=window_width,
            height=window_height,
            caption="CHIP-8 Emulator",
            vsync=False
        )

        #
        #replaced Python lists with NumPy arrays for memory, vram and registers
        self.memory = bytearray(4096)
        self.vram = bytearray(width * height)
        self.V = [0] * 16
        self.I = 0
        self.pc = 0x200

        self.stack = np.zeros(16, dtype=np.uint16)
        self.sp = 0

        self.keys = np.zeros(16, dtype=np.uint8)
        self.delay = 0
        self.sound = 0
        self.control_labels = []
        self.set_controls(romname)
        self.should_draw = True
        self.push_handlers(self)

        # Performance tracking
        self.cycle_count = 0
        self.cycles_per_second = 0
        self.fps = 0.0
        self.fps_label = pyglet.text.Label(
            "FPS: 0.000",
            font_size=12,
            x=5,
            y=window_height - 15,
            anchor_x='left',
            anchor_y='center',
            color=(255, 255, 255, 255)
        )

        # Pixel image
        self.pixel = pyglet.image.SolidColorImagePattern((255, 255, 255, 255)).create_image(scale, scale)

        # Load fontset into memory
        self.memory[:len(fontset)] = fontset

        # Load ROM
        print("Loading ROM:", romname)
        with open(romname, "rb") as f:
            rom = f.read()
        self.memory[0x200:0x200 + len(rom)] = rom

        # Beep sound
        self.sound_playing = True

        # Pre-allocated small framebuffer (64x32 RGBA). We'll upscale on CPU using numpy.repeat
        self._small_framebuf = np.zeros((height, width, 4), dtype=np.uint8)
        self._small_framebuf[..., 3] = 255

        #creating ImageData once (initialized empty)
        self.image = pyglet.image.ImageData(
            window_width,
            window_height,
            'RGBA',
            self._small_framebuf.tobytes()
        )

        # Schedule the loops
        pyglet.clock.schedule_interval(self.tick, 1 / CPU_HZ)       # CPU cycles
        pyglet.clock.schedule(self.draw_frame)   # Screen redraw (at 60Hz)
        pyglet.clock.schedule_interval(self._timer_tick, 1 / timer_HZ)

        # Performance tracking counters
        self._fps_counter = 0          # counts frames drawn in current second
        self._cps_counter = 0          # counts CPU cycles in current second
        self._bench_time = pyglet.clock.get_default().time()  # start time reference

        # Labels for HUD
        self.fps_label = pyglet.text.Label(
            "FPS: 0",
            font_size=12,
            x=5,
            y=window_height - 15,
            anchor_x='left',
            anchor_y='center',
            color=(255, 255, 255, 255)
        )
        self.cps_label = pyglet.text.Label(
            "Cycles/s: 0",
            font_size=12,
            x=5,
            y=window_height - 30,
            anchor_x='left',
            anchor_y='center',
            color=(255, 255, 255, 255)
        )
        pyglet.clock.schedule_interval(self._update_bench, 1.0)  # update FPS/CPS every second


        # dispatch table
        self.opcodes = [
            (0xFFFF, 0x00E0, self.op_CLS),
            (0xFFFF, 0x00EE, self.op_RET),

            (0xF000, 0x1000, self.op_JP),
            (0xF000, 0x2000, self.op_CALL),
            (0xF000, 0x3000, self.op_SE_Vx_kk),
            (0xF000, 0x4000, self.op_SNE_Vx_kk),
            (0xF00F, 0x5000, self.op_SE_Vx_Vy),
            (0xF000, 0x6000, self.op_LD_Vx_kk),
            (0xF000, 0x7000, self.op_ADD_Vx_kk),

            (0xF00F, 0x8000, self.op_LD_Vx_Vy),
            (0xF00F, 0x8001, self.op_OR),
            (0xF00F, 0x8002, self.op_AND),
            (0xF00F, 0x8003, self.op_XOR),
            (0xF00F, 0x8004, self.op_ADD),
            (0xF00F, 0x8005, self.op_SUB),
            (0xF00F, 0x8006, self.op_SHR),
            (0xF00F, 0x8007, self.op_SUBN),
            (0xF00F, 0x800E, self.op_SHL),

            (0xF00F, 0x9000, self.op_SNE_Vx_Vy),
            (0xF000, 0xA000, self.op_LD_I),
            (0xF000, 0xD000, self.op_DRW),

            (0xF0FF, 0xE09E, self.op_SKP),
            (0xF0FF, 0xE0A1, self.op_SKNP),

            (0xF0FF, 0xF007, self.op_LD_Vx_DT),
            (0xF0FF, 0xF00A, self.op_WAITKEY),
            (0xF0FF, 0xF015, self.op_LD_DT_Vx),
            (0xF0FF, 0xF018, self.op_LD_ST_Vx),
            (0xF0FF, 0xF01E, self.op_ADD_I_Vx),
            (0xF0FF, 0xF029, self.op_FONT),
            (0xF0FF, 0xF033, self.op_BCD),
            (0xF0FF, 0xF055, self.op_STORE),
            (0xF0FF, 0xF065, self.op_LOAD),
            (0xF000, 0xC000, self.op_RND),
        ]

    # Control scheme for each game
    def set_controls(self, game_name):
        """Sets the on-screen controls based on the game."""
        x_pos = window_width - 150  # adjust horizontal position to the right side
        if game_name.lower() == "pong":
            self.control_labels = [
                pyglet.text.Label("PONG CONTROLS:", font_size=12, x=x_pos, y=window_height - 45, anchor_x='left', anchor_y='center', color=(255,255,255,255)),
                pyglet.text.Label("Player 1: 1 / Q", font_size=12, x=x_pos, y=window_height - 60, anchor_x='left', anchor_y='center', color=(255,255,255,255)),
                pyglet.text.Label("Player 2: 4 / R", font_size=12, x=x_pos, y=window_height - 75, anchor_x='left', anchor_y='center', color=(255,255,255,255)),
            ]
        elif game_name.lower() == "tank":
            self.control_labels = [
                pyglet.text.Label("TANK CONTROLS:", font_size=12, x=x_pos, y=window_height - 45, anchor_x='left', anchor_y='center', color=(255,255,255,255)),
                pyglet.text.Label("Up: S", font_size=12, x=x_pos, y=window_height - 60, anchor_x='left', anchor_y='center', color=(255,255,255,255)),
                pyglet.text.Label("Down: 2", font_size=12, x=x_pos, y=window_height - 75, anchor_x='left', anchor_y='center', color=(255,255,255,255)),
                pyglet.text.Label("Left: Q", font_size=12, x=x_pos, y=window_height - 90, anchor_x='left', anchor_y='center', color=(255,255,255,255)),
                pyglet.text.Label("Right: E", font_size=12, x=x_pos, y=window_height - 105, anchor_x='left', anchor_y='center', color=(255,255,255,255)),
                pyglet.text.Label("Shoot: W", font_size=12, x=x_pos, y=window_height - 120, anchor_x='left', anchor_y='center', color=(255,255,255,255)),
            ]
        elif game_name.lower() == "tetris":
            self.control_labels = [
                pyglet.text.Label("TETRIS CONTROLS:", font_size=12, x=x_pos, y=window_height - 45, anchor_x='left', anchor_y='center', color=(255,255,255,255)),
                pyglet.text.Label("Rotate: Q", font_size=12, x=x_pos, y=window_height - 60, anchor_x='left', anchor_y='center', color=(255,255,255,255)),
                pyglet.text.Label("Left: W", font_size=12, x=x_pos, y=window_height - 75, anchor_x='left', anchor_y='center', color=(255,255,255,255)),
                pyglet.text.Label("Right: E", font_size=12, x=x_pos, y=window_height - 90, anchor_x='left', anchor_y='center', color=(255,255,255,255)),
                pyglet.text.Label("Drop: A", font_size=12, x=x_pos, y=window_height - 105, anchor_x='left', anchor_y='center', color=(255,255,255,255)),
            ]
        else:
            self.control_labels = [
                pyglet.text.Label("Controls: Unknown", font_size=12, x=x_pos, y=window_height - 45, anchor_x='left', anchor_y='center', color=(255,255,255,255))
            ]

    # FPS / CPS
    def _update_bench(self, dt):
        now = pyglet.clock.get_default().time()
        elapsed = now - self._bench_time
        if elapsed >= 1.0:
            self.fps_label.text = f"FPS: {self._fps_counter / elapsed:.1f}"
            self.cps_label.text = f"Cycles/s: {self._cps_counter}"

            self._fps_counter = 0
            self._cps_counter = 0
            self._bench_time = now

    # draw loop
    def draw_frame(self, dt):
        if self.should_draw:
            self.dispatch_event('on_draw')

    # opcode handlers
    def op_CLS(self, opcode):
        self.vram[:] = b'\x00' * len(self.vram)
        self.should_draw = True

    def op_RET(self, opcode):
        if self.sp == 0:
            self.pc = np.uint16(0x200)
        else:
            self.sp -= 1
            self.pc = self.stack[self.sp]

    def op_JP(self, opcode):
        self.pc = np.uint16(opcode & 0x0FFF)

    def op_CALL(self, opcode):
        if self.sp < 16:
            self.stack[self.sp] = self.pc
            self.sp += 1
        self.pc = np.uint16(opcode & 0x0FFF)

    def op_SE_Vx_kk(self, opcode):
        x = (opcode >> 8) & 0xF
        kk = opcode & 0xFF
        if self.V[x] == kk:
            self.pc = np.uint16(self.pc + 2)

    def op_SNE_Vx_kk(self, opcode):
        x = (opcode >> 8) & 0xF
        kk = opcode & 0xFF
        if self.V[x] != kk:
            self.pc = np.uint16(self.pc + 2)

    def op_SE_Vx_Vy(self, opcode):
        x = (opcode >> 8) & 0xF
        y = (opcode >> 4) & 0xF
        if self.V[x] == self.V[y]:
            self.pc = np.uint16(self.pc + 2)

    def op_LD_Vx_kk(self, opcode):
        x = (opcode >> 8) & 0xF
        self.V[x] = opcode & 0xFF

    def op_ADD_Vx_kk(self, opcode):
        x = (opcode >> 8) & 0xF
        kk = opcode & 0xFF
        self.V[x] = (self.V[x] + kk) & 0xFF

    def op_LD_Vx_Vy(self, opcode):
        x = (opcode >> 8) & 0xF
        y = (opcode >> 4) & 0xF
        self.V[x] = self.V[y]

    def op_OR(self, opcode):
        x = (opcode >> 8) & 0xF
        y = (opcode >> 4) & 0xF
        self.V[x] |= self.V[y]

    def op_AND(self, opcode):
        x = (opcode >> 8) & 0xF
        y = (opcode >> 4) & 0xF
        self.V[x] &= self.V[y]

    def op_XOR(self, opcode):
        x = (opcode >> 8) & 0xF
        y = (opcode >> 4) & 0xF
        self.V[x] ^= self.V[y]

    def op_ADD(self, opcode):
        x = (opcode >> 8) & 0xF
        y = (opcode >> 4) & 0xF
        total = int(self.V[x]) + int(self.V[y])
        self.V[0xF] = 1 if total > 0xFF else 0
        self.V[x] = total & 0xFF

    def op_SUB(self, opcode):
        x = (opcode >> 8) & 0xF
        y = (opcode >> 4) & 0xF
        self.V[0xF] = 1 if self.V[x] > self.V[y] else 0
        self.V[x] = (self.V[x] - self.V[y]) & 0xFF

    def op_SHR(self, opcode):
        x = (opcode >> 8) & 0xF
        self.V[0xF] = self.V[x] & 1
        self.V[x] >>= 1

    def op_SUBN(self, opcode):
        x = (opcode >> 8) & 0xF
        y = (opcode >> 4) & 0xF
        self.V[0xF] = 1 if self.V[y] > self.V[x] else 0
        self.V[x] = (self.V[y] - self.V[x]) & 0xFF

    def op_SHL(self, opcode):
        x = (opcode >> 8) & 0xF
        self.V[0xF] = (self.V[x] >> 7) & 1
        self.V[x] = (self.V[x] << 1) & 0xFF

    def op_SNE_Vx_Vy(self, opcode):
        x = (opcode >> 8) & 0xF
        y = (opcode >> 4) & 0xF
        if self.V[x] != self.V[y]:
            self.pc = np.uint16(self.pc + 2)

    def op_LD_I(self, opcode):
        self.I = np.uint16(opcode & 0x0FFF)

    def op_DRW(self, opcode):
        x = (opcode >> 8) & 0xF
        y = (opcode >> 4) & 0xF
        n = opcode & 0xF
        px = int(self.V[x])
        py = int(self.V[y])
        self.V[0xF] = 0
        for row in range(n):
            sprite = int(self.memory[self.I + row])
            for bit in range(8):
                if sprite & (0x80 >> bit):
                    vx = (px + bit) % 64
                    vy = (py + row) % 32
                    index = vx + vy * 64
                    if self.vram[index] == 1:
                        self.V[0xF] = 1
                    self.vram[index] ^= 1
        self.should_draw = True

    def op_SKP(self, opcode):
        x = (opcode >> 8) & 0xF
        if self.keys[self.V[x]]:
            self.pc = np.uint16(self.pc + 2)

    def op_SKNP(self, opcode):
        x = (opcode >> 8) & 0xF
        if not self.keys[self.V[x]]:
            self.pc = np.uint16(self.pc + 2)

    def op_LD_Vx_DT(self, opcode):
        x = (opcode >> 8) & 0xF
        self.V[x] = self.delay

    def op_WAITKEY(self, opcode):
        x = (opcode >> 8) & 0xF
        for i in range(16):
            if self.keys[i]:
                self.V[x] = i
                return
        self.pc = np.uint16(self.pc - 2)

    def op_LD_DT_Vx(self, opcode):
        x = (opcode >> 8) & 0xF
        self.delay = self.V[x]

    def op_LD_ST_Vx(self, opcode):
        x = (opcode >> 8) & 0xF
        self.sound = self.V[x]

    def op_ADD_I_Vx(self, opcode):
        x = (opcode >> 8) & 0xF
        self.I = (self.I + self.V[x]) & 0xFFF

    def op_FONT(self, opcode):
        x = (opcode >> 8) & 0xF
        self.I = self.V[x] * 5

    def op_BCD(self, opcode):
        x = (opcode >> 8) & 0xF
        v = int(self.V[x])
        self.memory[self.I] = v // 100
        self.memory[self.I + 1] = (v // 10) % 10
        self.memory[self.I + 2] = v % 10

    def op_STORE(self, opcode):
        x = (opcode >> 8) & 0xF
        self.memory[self.I:self.I + x + 1] = self.V[:x + 1]

    def op_LOAD(self, opcode):
        x = (opcode >> 8) & 0xF
        self.V[:x + 1] = self.memory[self.I:self.I + x + 1]

    def op_RND(self, opcode):
        x = (opcode >> 8) & 0xF
        kk = opcode & 0xFF
        self.V[x] = random.randint(0, 255) & kk

    # cup tick(replaced)
    def tick(self, dt):
        self._cps_counter += 1

        opcode = (int(self.memory[self.pc]) << 8) | int(self.memory[self.pc + 1])
        self.pc = np.uint16(self.pc + 2)

        for mask, pattern, handler in self.opcodes:
            if (opcode & mask) == pattern:
                handler(opcode)
                return

        print(f"Unknown opcode: {opcode:04X}")

    # sound
    def _play_beep(self, duration=0.2, frequency=440, pitch_variation=30):
        freq = frequency + random.randint(-pitch_variation, pitch_variation)
        wave = synthesis.Sine(duration=duration, frequency=freq, sample_rate=44100)
        player = pyglet.media.Player()
        player.queue(wave)
        player.play()
        self.sound_playing = True

        def on_eos():
            self.sound_playing = False
            player.delete()

        player.on_eos = on_eos

    # draw
    def on_draw(self):
        if not self.should_draw:
            return

        self.clear()
        for y in range(height):
            for x in range(width):
                pixel_value = self.vram[x + (height - 1 - y) * width] * 255
                self._small_framebuf[y, x, :3] = pixel_value

        if scale != 1:
            scaled = np.repeat(np.repeat(self._small_framebuf, scale, axis=0), scale, axis=1)
        else:
            scaled = self._small_framebuf

        #updates existing image without creating new object
        self.image.set_data('RGBA', window_width * 4, scaled.tobytes())
        self.image.blit(0, 0)

        #draw FPS and CPS
        self.fps_label.draw()
        self.cps_label.draw()

        #draw control labels
        for label in self.control_labels:
            label.draw()

        self.should_draw = False

        #self.should_draw = False
        self._fps_counter += 1

    # keyboard
    def on_key_press(self, symbol, modifiers):
        if symbol in keymap:
            self.keys[keymap[symbol]] = 1

    def on_key_release(self, symbol, modifiers):
        if symbol in keymap:
            self.keys[keymap[symbol]] = 0

    # timers
    def _timer_tick(self, dt):
        if self.delay > 0:
            self.delay -= 1

        if self.sound > 0:
            self.sound -= 1
            if not self.sound_playing:
                self._play_beep()
        else:
            self.sound_playing = False


# Main
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python chip8_emulator.py romfile")
        sys.exit(1)

    window = Chip8(sys.argv[1])
    pyglet.app.run()
