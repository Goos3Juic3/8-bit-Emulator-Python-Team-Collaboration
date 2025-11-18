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
# We're going to be subclassing pyglet (that'll handel graphics, sound output, and keyboard handeling)
# and Overriding what ever def we need from there.

import sys
import pyglet
from pyglet.window import key

#map binding keys
KEYMAP = {
    key._1: 0x1, key._2: 0x2, key._3: 0x3, key._4: 0xC,
    key.Q: 0x4, key.W: 0x5, key.E: 0x6, key.R: 0xD,
    key.A: 0x7, key.S: 0x8, key.D: 0x9, key.F: 0xE,
    key.Z: 0xA, key.X: 0x0, key.C: 0xB, key.V: 0xF,
}

# set fonts (binary pixel patterns)
FONTSET = [
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


class Chip8(pyglet.window.Window):

    def __init__(self, romname):
        super().__init__(
            width=640,
            height=320,
            caption="CHIP-8 Emulator",
            vsync=False          #VSync ON or OFF 
        )

        # CHIP-8 components
        self.memory = [0] * 4096
        self.vram = [0] * (64 * 32)     # framebuffer (replaces "display")
        self.V = [0] * 16               # registers
        self.I = 0
        self.pc = 0x200                 # program counter starts at 0x200
        self.stack = []
        self.keys = [0] * 16
        self.delay = 0
        self.sound = 0
        self.push_handlers(self) #required for dispatch_event('on_draw')
        self.should_draw = True

        # Load fontset
        for i in range(80):
            self.memory[i] = FONTSET[i]

        # Load ROM
        print("Loading ROM:", romname)
        rom = open(romname, "rb").read()
        for i, b in enumerate(rom):
            self.memory[0x200 + i] = b

        # Pixel image (10x10)
        self.pixel = pyglet.image.SolidColorImagePattern((255, 255, 255, 255)).create_image(10, 10)

        # CPU runs at ~600 Hz
        pyglet.clock.schedule_interval(self.tick, 1 / 600.0)

        # Screen redraw at a stable 60 FPS
        pyglet.clock.schedule_interval(self.draw_frame, 1 / 60.0)

    
    # Draw loop (60 FPS)-
    def draw_frame(self, dt):
        if self.should_draw:
            self.dispatch_event('on_draw')   # forces on_draw()

    
    # CPU (runs at 600 Hz)
    def tick(self, dt):

        opcode = self.memory[self.pc] << 8 | self.memory[self.pc + 1]
        self.pc += 2

        nnn = opcode & 0x0FFF
        n = opcode & 0x000F
        x = (opcode >> 8) & 0xF
        y = (opcode >> 4) & 0xF
        kk = opcode & 0xFF

        # opcodes 
        if opcode == 0x00E0:           # CLS
            self.vram = [0] * (64 * 32)
            self.should_draw = True

        elif opcode == 0x00EE:         # RET
            self.pc = self.stack.pop()

        elif opcode & 0xF000 == 0x1000:  # JP
            self.pc = nnn

        elif opcode & 0xF000 == 0x2000:  # CALL
            self.stack.append(self.pc)
            self.pc = nnn

        elif opcode & 0xF000 == 0x3000:  # SE Vx, byte
            if self.V[x] == kk:
                self.pc += 2

        elif opcode & 0xF000 == 0x4000:  # SNE Vx, byte
            if self.V[x] != kk:
                self.pc += 2

        elif opcode & 0xF00F == 0x5000:  # SE Vx, Vy
            if self.V[x] == self.V[y]:
                self.pc += 2

        elif opcode & 0xF000 == 0x6000:  # LD Vx, byte
            self.V[x] = kk

        elif opcode & 0xF000 == 0x7000:  # ADD Vx, byte
            self.V[x] = (self.V[x] + kk) & 0xFF

        elif opcode & 0xF00F == 0x8000:  # LD Vx, Vy
            self.V[x] = self.V[y]

        elif opcode & 0xF00F == 0x8001:  # OR
            self.V[x] |= self.V[y]

        elif opcode & 0xF00F == 0x8002:  # AND
            self.V[x] &= self.V[y]

        elif opcode & 0xF00F == 0x8003:  # XOR
            self.V[x] ^= self.V[y]

        elif opcode & 0xF00F == 0x8004:  # ADD + carry
            total = self.V[x] + self.V[y]
            self.V[0xF] = 1 if total > 0xFF else 0
            self.V[x] = total & 0xFF

        elif opcode & 0xF00F == 0x8005:  # SUB
            self.V[0xF] = 1 if self.V[x] > self.V[y] else 0
            self.V[x] = (self.V[x] - self.V[y]) & 0xFF

        elif opcode & 0xF00F == 0x8006:  # SHR
            self.V[0xF] = self.V[x] & 1
            self.V[x] >>= 1

        elif opcode & 0xF00F == 0x8007:  # SUBN
            self.V[0xF] = 1 if self.V[y] > self.V[x] else 0
            self.V[x] = (self.V[y] - self.V[x]) & 0xFF

        elif opcode & 0xF00F == 0x800E:  # SHL
            self.V[0xF] = (self.V[x] >> 7) & 1
            self.V[x] = (self.V[x] << 1) & 0xFF

        elif opcode & 0xF00F == 0x9000:  # SNE Vx, Vy
            if self.V[x] != self.V[y]:
                self.pc += 2

        elif opcode & 0xF000 == 0xA000:  # LD I, addr
            self.I = nnn

        elif opcode & 0xF000 == 0xD000:  # DRW Vx, Vy, n
            px = self.V[x]
            py = self.V[y]
            self.V[0xF] = 0

            for row in range(n):
                sprite = self.memory[self.I + row]
                for bit in range(8):
                    if sprite & (0x80 >> bit):
                        vx = (px + bit) % 64
                        vy = (py + row) % 32
                        index = vx + vy * 64

                        if self.vram[index] == 1:
                            self.V[0xF] = 1

                        self.vram[index] ^= 1

            self.should_draw = True

        elif opcode & 0xF0FF == 0xE09E:  # SKP
            if self.keys[self.V[x]]:
                self.pc += 2

        elif opcode & 0xF0FF == 0xE0A1:  # SKNP
            if not self.keys[self.V[x]]:
                self.pc += 2

        elif opcode & 0xF0FF == 0xF007:  # LD Vx, DT
            self.V[x] = self.delay

        elif opcode & 0xF0FF == 0xF00A:  # WAIT KEY
            for i in range(16):
                if self.keys[i]:
                    self.V[x] = i
                    return
            self.pc -= 2

        elif opcode & 0xF0FF == 0xF015:  # LD DT, Vx
            self.delay = self.V[x]

        elif opcode & 0xF0FF == 0xF018:  # LD ST, Vx
            self.sound = self.V[x]

        elif opcode & 0xF0FF == 0xF01E:  # ADD I, Vx
            self.I = (self.I + self.V[x]) & 0xFFF

        elif opcode & 0xF0FF == 0xF029:  # FONT
            self.I = self.V[x] * 5

        elif opcode & 0xF0FF == 0xF033:  # BCD
            v = self.V[x]
            self.memory[self.I] = v // 100
            self.memory[self.I + 1] = (v // 10) % 10
            self.memory[self.I + 2] = v % 10

        elif opcode & 0xF0FF == 0xF055:  # STORE
            for i in range(x + 1):
                self.memory[self.I + i] = self.V[i]

        elif opcode & 0xF0FF == 0xF065:  # LOAD
            for i in range(x + 1):
                self.V[i] = self.memory[self.I + i]

        # Timers
        if self.delay > 0:
            self.delay -= 1
        if self.sound > 0:
            self.sound -= 1

   
    # Draw (only when needed this time)
   
    def on_draw(self):
        if not self.should_draw:
            return

        self.clear()

        for i in range(2048):
            if self.vram[i]:
                x = (i % 64) * 10
                y = 310 - (i // 64) * 10
                self.pixel.blit(x, y)

        self.should_draw = False

    
    # keyboard(may impliment simultaneous key press in next edit)
    def on_key_press(self, symbol, modifiers):
        if symbol in KEYMAP:
            self.keys[KEYMAP[symbol]] = 1

    def on_key_release(self, symbol, modifiers):
        if symbol in KEYMAP:
            self.keys[KEYMAP[symbol]] = 0


#Main
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python chip8_emulator.py romfile")
        sys.exit(1)

    window = Chip8(sys.argv[1])
    pyglet.app.run()

#NOTES: at the moment this code has flikering issues. next patch should work on stabilization. Vsynce fixes most of the flikering issue but slow performance(to be addressed)
