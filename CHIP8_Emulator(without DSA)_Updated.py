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

#added the imports we need eventually
import pyglet
import sys

class cpu(pyglet.window.Window):
    #@Override
    def on_key_press(self, symbol, modifiers):
        # Placeholder: Add key handling logic here
        pass


    
    #@Override
    def on_key_release(self, symbol, modifiers):
        # Placeholder: Add key handling logic here
        pass

    def main(self):  # just about every emulator has a main
        self.initialize()
        self.load_rom(sys.argv[1])
        while not self.has_exit:
            self.dispatch_events()
            self.cycle()
            self.draw()
    
    def initialize(self):
        self.clear()  # clears pyglet window
        self.memory = [0]*4096  # max 4096
        self.gpio = [0]*16  # max 16
        self.display_buffer = [0]*64*32  # 64*32
        self.stack = []
        self.key_inputs = [0]*16
        self.opcode = 0
        self.index = 0

        self.delay_timer = 0
        self.sound_timer = 0
        self.should_draw = False  #so that we only update the display when needed

        self.pc = 0x200  #offset is equal to 0x200 (Cogwood's reference)

        i = 0
        while i < 80:
            #load 80-char font set
            self.memory[i] = self.fonts[i]
            i += 1

    #read ROM binary and read into memory
    def load_rom(self, rom_path):
        log("Loading %s..." % rom_path)  #log is so that user can turn on/off log messages when running
        binary = open(rom_path, "rb").read()
        i = 0
        while i < len(binary):
            self.memory[i + 0x200] = ord(binary[i])
            i += 1



    #Create a dictionary that maps opcode prefixes to methods.
    def setup_funcmap(self):
        self.funcmap = {
            0x0000: self.op_0xxx,
            0x1000: self.op_1nnn,
            0x2000: self.op_2nnn,
            0x3000: self.op_3xkk,
            0x4000: self.op_4xkk,
            0x5000: self.op_5xy0,
            0x6000: self.op_6xkk,
            0x7000: self.op_7xkk,
            0x8000: self.op_8xyx,
            0x9000: self.op_9xy0,
            0xA000: self.op_annn,
            0xB000: self.op_bnnn,
            0xC000: self.op_cxkk,
            0xD000: self.op_dxyn,
            0xE000: self.op_exxx,
            0xF000: self.op_fxxx
        }

    def cycle(self):
        # Fetch 2-byte opcode (CHIP8 opcodes are 2 bytes)
        self.opcode = (self.memory[self.pc] << 8) | self.memory[self.pc + 1]

        # Extract Vx and Vy for easy use
        self.vx = (self.opcode & 0x0F00) >> 8
        self.vy = (self.opcode & 0x00F0) >> 4

        # Move PC ahead (will be adjusted if jump/call)
        self.pc += 2

        # Extract first nibble to determine instruction
        extracted_op = self.opcode & 0xF000
        try:
            self.funcmap[extracted_op]()  # call mapped method
        except KeyError:
            print("Unknown instruction: %04X" % self.opcode)

        # Decrement timers
        if self.delay_timer > 0:
            self.delay_timer -= 1
        if self.sound_timer > 0:
            self.sound_timer -= 1
            if self.sound_timer == 0:
                # Play a sound using pyglet here
                log("sound plays")

#opcode handlers (Not confident that any or all of this is done correctly btw)

def op_0xxx(self):
    if self.opcode == 0x00E0:
        self.display_buffer = [0]*64*32
        self.should_draw = True
        log("Clear screen: all pixels set to 0")
    elif self.opcode == 0x00EE:
        self.pc = self.stack.pop()
        log(f"Return from subroutine: PC set to {self.pc} (from stack)")
    else:
        log(f"Ignored unknown 0x0??? opcode: {self.opcode:04X}")

def op_1nnn(self):
    addr = self.opcode & 0x0FFF
    self.pc = addr
    log(f"Jumping to address {addr} (decimal) / {addr:03X} (hex)")

def op_2nnn(self):
    addr = self.opcode & 0x0FFF
    self.stack.append(self.pc)
    self.pc = addr
    log(f"Calling subroutine at {addr} (decimal) / {addr:03X} (hex), return address pushed to stack")

def op_3xkk(self):
    kk = self.opcode & 0x00FF
    if self.gpio[self.vx] == kk:
        self.pc += 2
        log(f"Skipping next instruction because V{self.vx} ({self.gpio[self.vx]}) == {kk}")
    else:
        log(f"Not skipping: V{self.vx} ({self.gpio[self.vx]}) != {kk}")

def op_4xkk(self):
    kk = self.opcode & 0x00FF
    if self.gpio[self.vx] != kk:
        self.pc += 2
        log(f"Skipping next instruction because V{self.vx} ({self.gpio[self.vx]}) != {kk}")
    else:
        log(f"Not skipping: V{self.vx} ({self.gpio[self.vx]}) == {kk}")

def op_5xy0(self):
    if self.gpio[self.vx] == self.gpio[self.vy]:
        self.pc += 2
        log(f"Skipping next instruction because V{self.vx} ({self.gpio[self.vx]}) == V{self.vy} ({self.gpio[self.vy]})")
    else:
        log(f"Not skipping: V{self.vx} ({self.gpio[self.vx]}) != V{self.vy} ({self.gpio[self.vy]})")

def op_6xkk(self):
    kk = self.opcode & 0x00FF
    self.gpio[self.vx] = kk
    log(f"Set V{self.vx} to {kk} (decimal) / {kk:02X} (hex)")

def op_7xkk(self):
    kk = self.opcode & 0x00FF
    old_val = self.gpio[self.vx]
    self.gpio[self.vx] = (self.gpio[self.vx] + kk) & 0xFF
    log(f"Added {kk} to V{self.vx}: {old_val} + {kk} = {self.gpio[self.vx]} (decimal) / {self.gpio[self.vx]:02X} (hex)")

def op_8xyx(self):
    subcode = self.opcode & 0x000F
    x = self.vx
    y = self.vy

    if subcode == 0x0:  # LD Vx, Vy
        self.gpio[x] = self.gpio[y]
        log(f"Set V{x} = V{y} ({self.gpio[y]})")
    elif subcode == 0x1:  # OR
        self.gpio[x] |= self.gpio[y]
        log(f"V{x} = V{x} | V{y} ({self.gpio[x]})")
    elif subcode == 0x2:  # AND
        self.gpio[x] &= self.gpio[y]
        log(f"V{x} = V{x} & V{y} ({self.gpio[x]})")
    elif subcode == 0x3:  # XOR
        self.gpio[x] ^= self.gpio[y]
        log(f"V{x} = V{x} ^ V{y} ({self.gpio[x]})")
    elif subcode == 0x4:  # ADD Vx, Vy with carry
        res = self.gpio[x] + self.gpio[y]
        self.gpio[0xF] = 1 if res > 0xFF else 0
        self.gpio[x] = res & 0xFF
        log(f"V{x} = V{x} + V{y} ({self.gpio[x]}), carry={self.gpio[0xF]}")
    elif subcode == 0x5:  # SUB Vx, Vy
        self.gpio[0xF] = 1 if self.gpio[x] > self.gpio[y] else 0
        self.gpio[x] = (self.gpio[x] - self.gpio[y]) & 0xFF
        log(f"V{x} = V{x} - V{y} ({self.gpio[x]}), borrow flag={self.gpio[0xF]}")
    elif subcode == 0x6:  # SHR Vx
        self.gpio[0xF] = self.gpio[x] & 0x1
        self.gpio[x] >>= 1
        log(f"V{x} shifted right by 1, LSB stored in VF={self.gpio[0xF]}")
    elif subcode == 0x7:  # SUBN Vx, Vy
        self.gpio[0xF] = 1 if self.gpio[y] > self.gpio[x] else 0
        self.gpio[x] = (self.gpio[y] - self.gpio[x]) & 0xFF
        log(f"V{x} = V{y} - V{x} ({self.gpio[x]}), borrow flag={self.gpio[0xF]}")
    elif subcode == 0xE:  # SHL Vx
        self.gpio[0xF] = (self.gpio[x] >> 7) & 0x1
        self.gpio[x] = (self.gpio[x] << 1) & 0xFF
        log(f"V{x} shifted left by 1, MSB stored in VF={self.gpio[0xF]}")
    else:
        log(f"Unknown 8XY? opcode: {self.opcode:04X}")

def op_9xy0(self):
    if self.gpio[self.vx] != self.gpio[self.vy]:
        self.pc += 2
        log(f"Skipping next instruction because V{self.vx} ({self.gpio[self.vx]}) != V{self.vy} ({self.gpio[self.vy]})")
    else:
        log(f"Not skipping: V{self.vx} ({self.gpio[self.vx]}) == V{self.vy} ({self.gpio[self.vy]})")

def op_annn(self):
    self.index = self.opcode & 0x0FFF
    log(f"Set index register I = {self.index} (decimal) / {self.index:03X} (hex)")

def op_bnnn(self):
    addr = self.opcode & 0x0FFF
    self.pc = addr + self.gpio[0]
    log(f"Jumping to V0 + {addr} = {self.pc} (decimal) / {self.pc:03X} (hex)")

def op_cxkk(self):
    import random
    kk = self.opcode & 0x00FF
    val = random.randint(0, 255) & kk
    self.gpio[self.vx] = val
    log(f"Set V{self.vx} = random_byte & {kk} = {val}")

def op_dxyn(self):
    x_coord = self.gpio[self.vx]
    y_coord = self.gpio[self.vy]
    height = self.opcode & 0x000F
    self.gpio[0xF] = 0

    for row in range(height):
        sprite_byte = self.memory[self.index + row]
        for col in range(8):
            sprite_pixel = (sprite_byte >> (7 - col)) & 1
            idx = ((x_coord + col) % 64) + ((y_coord + row) % 32) * 64
            if sprite_pixel:
                if self.display_buffer[idx] == 1:
                    self.gpio[0xF] = 1
                self.display_buffer[idx] ^= 1

    self.should_draw = True
    log(f"Drew sprite at (V{self.vx}={x_coord}, V{self.vy}={y_coord}), height={height}, VF={self.gpio[0xF]}")

def op_exxx(self):
    kk = self.opcode & 0x00FF
    key = self.gpio[self.vx]
    if kk == 0x9E:  # SKP Vx
        if self.key_inputs[key]:
            self.pc += 2
        log(f"Skip next if key {key} is pressed: key state={self.key_inputs[key]}")
    elif kk == 0xA1:  # SKNP Vx
        if not self.key_inputs[key]:
            self.pc += 2
        log(f"Skip next if key {key} is NOT pressed: key state={self.key_inputs[key]}")

def op_fxxx(self):
    kk = self.opcode & 0x00FF
    x = self.vx

    if kk == 0x07:  # LD Vx, DT
        self.gpio[x] = self.delay_timer
        log(f"Set V{x} = delay_timer ({self.delay_timer})")
    elif kk == 0x0A:  # LD Vx, K
        pressed = False
        for i, state in enumerate(self.key_inputs):
            if state:
                self.gpio[x] = i
                pressed = True
                break
        if not pressed:
            self.pc -= 2  # repeat instruction
        log(f"Wait for key press, store in V{x}: {self.gpio[x] if pressed else 'waiting'}")
    elif kk == 0x15:  # LD DT, Vx
        self.delay_timer = self.gpio[x]
        log(f"Set delay_timer = V{x} ({self.gpio[x]})")
    elif kk == 0x18:  # LD ST, Vx
        self.sound_timer = self.gpio[x]
        log(f"Set sound_timer = V{x} ({self.gpio[x]})")
    elif kk == 0x1E:  # ADD I, Vx
        old_index = self.index
        self.index = (self.index + self.gpio[x]) & 0xFFFF
        log(f"Add V{x} ({self.gpio[x]}) to I: {old_index} -> {self.index}")
    elif kk == 0x29:  # LD F, Vx
        self.index = self.gpio[x] * 5
        log(f"Set I to sprite location for digit V{x} ({self.gpio[x]}) -> I={self.index}")
    elif kk == 0x33:  # LD B, Vx
        val = self.gpio[x]
        self.memory[self.index] = val // 100
        self.memory[self.index + 1] = (val // 10) % 10
        self.memory[self.index + 2] = val % 10
        log(f"Store BCD of V{x} ({val}) at memory I ({self.index})")
    elif kk == 0x55:  # LD [I], V0..Vx
        for i in range(x + 1):
            self.memory[self.index + i] = self.gpio[i]
        log(f"Store V0..V{x} into memory starting at I ({self.index})")
    elif kk == 0x65:  # LD V0..Vx, [I]
        for i in range(x + 1):
            self.gpio[i] = self.memory[self.index + i]
        log(f"Load V0..V{x} from memory starting at I ({self.index})")
