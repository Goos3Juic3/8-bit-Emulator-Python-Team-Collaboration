# CHIP8 Virtual Machine Steps:
# Input - store key input states and check these per cycle.
# Output - 64x32 display(array of pixels are either in the on of off state(0 || 1)) & sound buzzer. 
# CPU - Cogwoods CHIP8 Technical reference http://devernay.free.fr/hacks/chip8/C8TECH10.HTM#0.0
# Memory - can hold up to 4096 bytes which includes: the interpreter, fonts, and inputted ROM.
#----------------------------------------------------------------------------------------------
# We will be storing register values as 16 zeros. Also, we will have two time registers 
# defined by two variables that we decrement per cycle. We will also be dealing with a 
# stack of 16 elements that we'll just need to make into a list.
#----------------------------------------------------------------------------------------------
# We're going to be subclassing pyglet (that'll handle graphics, sound output, and keyboard handling)
# and Overriding whatever def we need from there.

import pyglet
import sys
import random
from pyglet.media import synthesis


# ---- Configuration ----
scale = 10
width, height = 64, 32
window_width, window_height = width * scale, height * scale
cpu_hz = 500
timer_HZ = 60

#make it true if you want the logs
logsOn = False

def log(*args):
    if logsOn:
        print(*args)

def generate_beep(duration=0.1, frequency=440, sample_rate=44100):
    # Use a Sine waveform from pyglet.media.synthesis
    wave = synthesis.Sine(duration=duration, frequency=frequency, sample_rate=sample_rate)
    return pyglet.media.StaticSource(wave)

# Standard CHIP-8 fontset (80 bytes)
fontset = [
    0xF0,0x90,0x90,0x90,0xF0,
    0x20,0x60,0x20,0x20,0x70,
    0xF0,0x10,0xF0,0x80,0xF0,
    0xF0,0x10,0xF0,0x10,0xF0,
    0x90,0x90,0xF0,0x10,0x10,
    0xF0,0x80,0xF0,0x10,0xF0,
    0xF0,0x80,0xF0,0x90,0xF0,
    0xF0,0x10,0x20,0x40,0x40,
    0xF0,0x90,0xF0,0x90,0xF0,
    0xF0,0x90,0xF0,0x10,0xF0,
    0xF0,0x90,0xF0,0x90,0x90,
    0xE0,0x90,0xE0,0x90,0xE0,
    0xF0,0x80,0x80,0x80,0xF0,
    0xE0,0x90,0x90,0x90,0xE0,
    0xF0,0x80,0xF0,0x80,0xF0,
    0xF0,0x80,0xF0,0x80,0x80
]

# Key mapping - maps physical keyboard keys to CHIP-8 keypad
keymap = {
    pyglet.window.key._1: 0x1,  # 1 -> CHIP-8 key 0x1
    pyglet.window.key._2: 0x2,  # 2 -> CHIP-8 key 0x2
    pyglet.window.key._3: 0x3,  # 3 -> CHIP-8 key 0x3
    pyglet.window.key._4: 0xC,  # 4 -> CHIP-8 key 0xC (top-right)

    pyglet.window.key.Q: 0x4,   # Q -> CHIP-8 key 0x4
    pyglet.window.key.W: 0x5,   # W -> CHIP-8 key 0x5
    pyglet.window.key.E: 0x6,   # E -> CHIP-8 key 0x6
    pyglet.window.key.R: 0xD,   # R -> CHIP-8 key 0xD

    pyglet.window.key.A: 0x7,   # A -> CHIP-8 key 0x7
    pyglet.window.key.S: 0x8,   # S -> CHIP-8 key 0x8
    pyglet.window.key.D: 0x9,   # D -> CHIP-8 key 0x9
    pyglet.window.key.F: 0xE,   # F -> CHIP-8 key 0xE

    pyglet.window.key.Z: 0xA,   # Z -> CHIP-8 key 0xA
    pyglet.window.key.X: 0x0,   # X -> CHIP-8 key 0x0
    pyglet.window.key.C: 0xB,   # C -> CHIP-8 key 0xB
    pyglet.window.key.V: 0xF    # V -> CHIP-8 key 0xF
}

class Chip8(pyglet.window.Window):
    def __init__(self):
        super().__init__(window_width, window_height, caption="CHIP-8 Emulator", resizable=False)

        # ---- CPU state ----
        self.memory = [0]*4096  # max 4096 bytes
        self.gpio = [0]*16      # 16 general-purpose registers
        self.index = 0          # I register (memory pointer)
        self.pc = 0x200         # program counter starts at 0x200
        self.stack = []         # stack for subroutine calls
        self.delay_timer = 0
        self.sound_timer = 0
        self.display_buffer = [0]*(width*height)  # 64x32 screen
        self.key_inputs = [0]*16
        self.opcode = 0
        self.vx = 0
        self.vy = 0
        self.should_draw = True
        self.has_exit = False

        # Load fontset into memory
        for i, b in enumerate(fontset):
            self.memory[i] = b

        # ---- Performance Counters ----
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

        self.cycle_count = 0
        self.cycles_per_second = 0

        pyglet.clock.schedule_interval(self._update_cps, 1.0)
        pyglet.clock.schedule_interval(self._update_fps, 1.0)

        # Prepare opcode function map
        self.setup_funcmap()

        # Schedule CPU and timer ticks
        pyglet.clock.schedule_interval(self._cpu_tick, 1.0/cpu_hz)
        pyglet.clock.schedule_interval(self._timer_tick, 1.0/timer_HZ)

        # Pre-create a pixel sprite for drawing
        self.pixel = pyglet.image.SolidColorImagePattern((255, 255, 255, 255)).create_image(scale, scale)

        self.beep_sound = generate_beep(frequency=440, duration=0.5)
        self.beep_player = None
        self.sound_playing = False  # Track if beep is currently playing

    def _play_beep(self, base_freq=440, duration=0.5, pitch_variation=50):
        freq = base_freq + random.randint(-pitch_variation, pitch_variation)
        wave = synthesis.Sine(duration=duration, frequency=freq, sample_rate=44100)
        
        player = pyglet.media.Player()
        player.queue(wave)
        player.play()
        self.sound_playing = True

        # Ensure the sound stops after the requested duration
        def on_eos():
            self.sound_playing = False
            player.delete()

        player.on_eos = on_eos


    def _update_fps(self, dt):
        self.fps = 1.0 / dt
        self.fps_label.text = f"FPS: {self.fps:.3f}"

    def _update_cps(self, dt):
        self.cycles_per_second = self.cycle_count
        self.cycle_count = 0

    # ---- Input ----
    def on_key_press(self, symbol, modifiers):
        #@Override
        if symbol == pyglet.window.key.ESCAPE:
            self.close()
        if symbol in keymap:
            self.key_inputs[keymap[symbol]] = 1
        if symbol == pyglet.window.key.F1:
            global logsOn
            logsOn = not logsOn
            log("logsOn:", logsOn)

    def on_key_release(self, symbol, modifiers):
        #@Override
        if symbol in keymap:
            self.key_inputs[keymap[symbol]] = 0

    # ---- Drawing ----
    def on_draw(self):
        self.clear()

        if self.should_draw:
            for i in range(width*height):
                if self.display_buffer[i] == 1:
                    x = (i % width) * scale
                    y = (height - 1 - (i // width)) * scale
                    self.pixel.blit(x, y)
            self.should_draw = False

        # ---- FPS label ----
        self.fps_label.draw()

        # ---- CPS label ----
        cps_label = pyglet.text.Label(
            f"Cycles/s: {self.cycles_per_second}",
            font_size=12,
            x=5,
            y=window_height - 30,
            anchor_x='left',
            anchor_y='center',
            color=(255, 255, 255, 255)
        )
        cps_label.draw()

    # ---- CPU cycle ----
    def _cpu_tick(self, dt):
        if not self.has_exit:
            try:
                self.cycle()
            except Exception as e:
                print("Emulation error:", e)
                self.has_exit = True
                self.close()

    # ---- timers ----
    def _timer_tick(self, dt):
        # Delay timer
        if self.delay_timer > 0:
            self.delay_timer -= 1
        # Sound timer
        if self.sound_timer > 0:
            self.sound_timer -= 1

            # Play beep only if it hasn't started yet
            if not self.sound_playing:
                self._play_beep(base_freq=440, duration=0.2, pitch_variation=15)
        else:
            # Sound timer reached 0, reset flag
            self.sound_playing = False

    # ---- Load ROM ----
    def load_rom(self, path):
        log("Loading ROM:", path)
        with open(path, "rb") as f:
            data = f.read()
        for i, b in enumerate(data):
            if 0x200 + i < 4096:
                self.memory[0x200+i] = b

    # ---- Cycle ----
    def cycle(self):
        self.cycle_count += 1  # Count cycle

        # Fetch opcode
        # guard pc bounds
        if self.pc < 0 or self.pc+1 >= len(self.memory):
            raise Exception("PC out of bounds: 0x%03X" % self.pc)
        self.opcode = (self.memory[self.pc]<<8)|self.memory[self.pc+1]

        # Extract registers
        self.vx = (self.opcode & 0x0F00)>>8
        self.vy = (self.opcode & 0x00F0)>>4

        # Instruction decode & dispatch (correct decoding)
        prefix = self.opcode & 0xF000

        # Special-case 0x0000 group (00E0, 00EE, 0nnn)
        if prefix == 0x0000:
            if self.opcode == 0x00E0:
                self._0E0()
            elif self.opcode == 0x00EE:
                self._00EE()
            else:
                self._0nnn()
        else:
            handler = self.funcmap.get(prefix)
            if handler:
                handler()
            else:
                print("Unknown opcode: %04X" % self.opcode)

        # Default PC increment
        self.pc = (self.pc+2)&0xFFF

        # timers (redundant with scheduled _timer_tick but harmless)
        if self.delay_timer>0: self.delay_timer-=1
        if self.sound_timer>0:
            self.sound_timer-=1
            if self.sound_timer == 0:
                log("Sound plays!")

    # ---- Opcode function map ----
    def setup_funcmap(self):
        self.funcmap = {
            0x1000: self._1nnn,  # 1nnn - Jump to a specific memory address
            0x2000: self._2nnn,  # 2nnn - Call a function (subroutine) at a memory address
            0x3000: self._3xkk,  # 3xkk - Skip next instruction if a register equals a specific number
            0x4000: self._4xkk,  # 4xkk - Skip next instruction if a register does NOT equal a number
            0x5000: self._5xy0,  # 5xy0 - Skip next instruction if two registers are equal
            0x6000: self._6xkk,  # 6xkk - Set a register to a specific number
            0x7000: self._7xkk,  # 7xkk - Add a number to a register
            0x8000: self._8xxx,  # 8xy0..8xyE - Math and logic operations between two registers
            0x9000: self._9xy0,  # 9xy0 - Skip next instruction if two registers are NOT equal
            0xA000: self._Annn,  # Annn - Set a special memory pointer (I) to a specific address
            0xB000: self._Bnnn,  # Bnnn - Jump to an address plus the value of register V0
            0xC000: self._Cxkk,  # Cxkk - Set a register to a random number ANDed with a value
            0xD000: self._Dxyn,  # Dxyn - Draw a small image (sprite) on the screen at X,Y coordinates
            0xE000: self._Exxx,  # Ex9E / ExA1 - Skip next instruction if a key is pressed or not pressed
            0xF000: self._Fxxx,  # Fx07..Fx65 - timers, memory storage, and waiting for keys
        }

    # ---- Opcode Handlers ----
    
    # 0nnn / 00E0 / 00EE - SYS call / Clear Screen / Return from subroutine
    def _0nnn(self):
        # 0nnn is ignored on modern interpreters
        log("SYS call ignored (0nnn)")

    def _0E0(self):
        # CLS
        self.display_buffer = [0] * (width * height)
        self.should_draw = True
        log("Clear the display (all pixels turned off)")

    def _00EE(self):
        # RET
        if not self.stack:
            raise Exception("Stack underflow on 00EE")
        addr = self.stack.pop()
        self.pc = addr
        log("Return to", hex(addr))

    # 1nnn - Jump to address NNN
    def _1nnn(self):
        self.pc = (self.opcode & 0x0FFF) - 2
        log("Jump to address", hex((self.opcode & 0x0FFF)))

    # 2nnn - Call subroutine at NNN
    def _2nnn(self):
        if len(self.stack) >= 16:
            raise Exception("Stack overflow on CALL")
        self.stack.append(self.pc)
        self.pc = (self.opcode & 0x0FFF) - 2
        log("Call subroutine at", hex(self.pc + 2))

    # 3xkk - Skip next instruction if Vx == kk
    def _3xkk(self):
        kk = self.opcode & 0xFF
        if self.gpio[self.vx] == kk:
            self.pc = (self.pc + 2) & 0xFFF
            log(f"Skip next instruction: V{self.vx} == {kk}")

    # 4xkk - Skip next instruction if Vx != kk
    def _4xkk(self):
        kk = self.opcode & 0xFF
        if self.gpio[self.vx] != kk:
            self.pc = (self.pc + 2) & 0xFFF
            log(f"Skip next instruction: V{self.vx} != {kk}")

    # 5xy0 - Skip next instruction if Vx == Vy
    def _5xy0(self):
        if (self.opcode & 0xF) != 0:
            return
        if self.gpio[self.vx] == self.gpio[self.vy]:
            self.pc = (self.pc + 2) & 0xFFF
            log(f"Skip next instruction: V{self.vx} == V{self.vy}")

    # 6xkk - Set Vx = kk
    def _6xkk(self):
        self.gpio[self.vx] = self.opcode & 0xFF
        log(f"Set V{self.vx} = {self.gpio[self.vx]}")

    # 7xkk - Add immediate
    def _7xkk(self):
        self.gpio[self.vx] = (self.gpio[self.vx] + (self.opcode & 0xFF)) & 0xFF
        log(f"Add {self.opcode & 0xFF} to V{self.vx}: {self.gpio[self.vx]}")

    # 8xy0..8xyE
    def _8xxx(self):
        x, y = self.vx, self.vy
        sub = self.opcode & 0xF

        if sub == 0x0:
            self.gpio[x] = self.gpio[y]
            log(f"Copy V{y} ({self.gpio[y]}) into V{x}")
        elif sub == 0x1:
            self.gpio[x] |= self.gpio[y]
            log(f"V{x} = V{x} OR V{y} -> {self.gpio[x]}")
        elif sub == 0x2:
            self.gpio[x] &= self.gpio[y]
            log(f"V{x} = V{x} AND V{y} -> {self.gpio[x]}")
        elif sub == 0x3:
            self.gpio[x] ^= self.gpio[y]
            log(f"V{x} = V{x} XOR V{y} -> {self.gpio[x]}")
        elif sub == 0x4:
            s = self.gpio[x] + self.gpio[y]
            self.gpio[0xF] = 1 if s > 0xFF else 0
            self.gpio[x] = s & 0xFF
            log(f"Add V{y} to V{x}: result {self.gpio[x]}, carry={self.gpio[0xF]}")
        elif sub == 0x5:
            self.gpio[0xF] = 1 if self.gpio[x] > self.gpio[y] else 0
            self.gpio[x] = (self.gpio[x] - self.gpio[y]) & 0xFF
            log(f"Subtract V{y} from V{x}: result {self.gpio[x]}, NOT borrow={self.gpio[0xF]}")
        elif sub == 0x6:
            self.gpio[0xF] = self.gpio[x] & 1
            self.gpio[x] >>= 1
            log(f"Shift V{x} right by 1: {self.gpio[x]}, least significant bit={self.gpio[0xF]}")
        elif sub == 0x7:
            self.gpio[0xF] = 1 if self.gpio[y] > self.gpio[x] else 0
            self.gpio[x] = (self.gpio[y] - self.gpio[x]) & 0xFF
            log(f"Set V{x} = V{y} - V{x}: result {self.gpio[x]}, NOT borrow={self.gpio[0xF]}")
        elif sub == 0xE:
            self.gpio[0xF] = (self.gpio[x] >> 7) & 1
            self.gpio[x] = (self.gpio[x] << 1) & 0xFF
            log(f"Shift V{x} left by 1: {self.gpio[x]}, most significant bit={self.gpio[0xF]}")

    # 9xy0 - Skip next instruction if Vx != Vy
    def _9xy0(self):
        if (self.opcode & 0xF) != 0:
            return
        if self.gpio[self.vx] != self.gpio[self.vy]:
            self.pc = (self.pc + 2) & 0xFFF
            log(f"Skip next instruction: V{self.vx} != V{self.vy}")

    # Annn - Set I = NNN
    def _Annn(self):
        self.index = self.opcode & 0x0FFF
        log(f"Set I = {self.index:03X}")

    # Bnnn - Jump to address NNN + V0
    def _Bnnn(self):
        self.pc = ((self.opcode & 0x0FFF) + self.gpio[0] - 2) & 0xFFF
        log(f"Jump to address V0 + {self.opcode & 0x0FFF:03X} = {self.pc + 2:03X}")

    # Cxkk - RND Vx, byte
    def _Cxkk(self):
        self.gpio[self.vx] = random.getrandbits(8) & (self.opcode & 0xFF)
        log(f"Set V{self.vx} = random_byte & {self.opcode & 0xFF} -> {self.gpio[self.vx]}")

    # Dxyn - DRW Vx, Vy, nibble
    def _Dxyn(self):
        x = self.gpio[(self.opcode >> 8) & 0xF] % width
        y = self.gpio[(self.opcode >> 4) & 0xF] % height
        n = self.opcode & 0xF
        buf = self.display_buffer
        collision = 0
        for row in range(n):
            if self.index + row >= 4096:
                continue
            sprite = self.memory[self.index + row]
            if sprite == 0:
                continue
            base = ((y + row) & 0x1F) * 64
            if sprite & 0x80:
                idx = base + ((x + 0) & 0x3F); collision |= buf[idx]; buf[idx] ^= 1
            if sprite & 0x40:
                idx = base + ((x + 1) & 0x3F); collision |= buf[idx]; buf[idx] ^= 1
            if sprite & 0x20:
                idx = base + ((x + 2) & 0x3F); collision |= buf[idx]; buf[idx] ^= 1
            if sprite & 0x10:
                idx = base + ((x + 3) & 0x3F); collision |= buf[idx]; buf[idx] ^= 1
            if sprite & 0x08:
                idx = base + ((x + 4) & 0x3F); collision |= buf[idx]; buf[idx] ^= 1
            if sprite & 0x04:
                idx = base + ((x + 5) & 0x3F); collision |= buf[idx]; buf[idx] ^= 1
            if sprite & 0x02:
                idx = base + ((x + 6) & 0x3F); collision |= buf[idx]; buf[idx] ^= 1
            if sprite & 0x01:
                idx = base + ((x + 7) & 0x3F); collision |= buf[idx]; buf[idx] ^= 1
        self.gpio[0xF] = 1 if collision else 0
        self.should_draw = True
        log(f"Drew sprite, collision={self.gpio[0xF]}")

    # Ex9E / ExA1 - SKP / SKNP
    def _Exxx(self):
        x = (self.opcode >> 8) & 0xF
        kk = self.opcode & 0xFF
        key = self.gpio[x] & 0xF
        if kk == 0x9E:
            if key < len(self.key_inputs) and self.key_inputs[key]:
                self.pc = (self.pc + 2) & 0x0FFF
        elif kk == 0xA1:
            if key < len(self.key_inputs) and not self.key_inputs[key]:
                self.pc = (self.pc + 2) & 0x0FFF

    # Fx07..Fx65 - timers, memory, I, and key input
    def _Fxxx(self):
        x = (self.opcode >> 8) & 0xF
        kk = self.opcode & 0xFF

        if kk == 0x07:
            # Vx = delay_timer
            self.gpio[x] = self.delay_timer
        elif kk == 0x0A:
            # LD Vx, K: wait for a key press (stall)
            pressed = None
            for i, s in enumerate(self.key_inputs):
                if s:
                    pressed = i
                    break
            if pressed is None:
                self.pc = (self.pc - 2) & 0xFFF  # stall (PC will re-execute this instr)
            else:
                self.gpio[x] = pressed
        elif kk == 0x15:
            self.delay_timer = self.gpio[x]
        elif kk == 0x18:
            self.sound_timer = self.gpio[x]
            if self.sound_timer > 0:
                # Only play if not already playing
                if not self.sound_playing:
                    self._play_beep(base_freq=440, duration=0.2, pitch_variation=15)
        elif kk == 0x1E:
            new_i = (self.index + self.gpio[x])
            self.gpio[0xF] = 1 if new_i > 0xFFF else 0
            self.index = new_i & 0xFFFF
        elif kk == 0x29:
            self.index = (self.gpio[x] & 0xF) * 5
        elif kk == 0x33:
            val = self.gpio[x]
            if self.index < 4094:
                self.memory[self.index]     = val // 100
                self.memory[self.index + 1] = (val // 10) % 10
                self.memory[self.index + 2] = val % 10
        elif kk == 0x55:
            for i in range(x + 1):
                if self.index + i < 4096:
                    self.memory[self.index + i] = self.gpio[i]
        elif kk == 0x65:
            for i in range(x + 1):
                if self.index + i < 4096:
                    self.gpio[i] = self.memory[self.index + i]

# ---- Entry point ----
def main():
    if len(sys.argv)<2:
        print("Usage: python chip8.py <rom-file>")
        sys.exit(1)
    rom = sys.argv[1]
    window = Chip8()
    window.load_rom(rom)
    pyglet.app.run()

if __name__=="__main__":
    main()
