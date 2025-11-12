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

    # Cycle
    def cycle(self):
        # Fetch opcode
        self.opcode = (self.memory[self.pc] << 8) | self.memory[self.pc + 1]

        # Extract registers
        self.vx = (self.opcode & 0x0f00) >> 8
        self.vy = (self.opcode & 0x00f0) >> 4

        # Special case for 0x0XXX
        if (self.opcode & 0xF000) == 0x0000:
            extracted_op = self.opcode & 0xF0FF
            try:
                self.funcmap[extracted_op]()
            except KeyError:
                print("Unknown instruction: %04X" % self.opcode)
        else:
            extracted_op = self.opcode & 0xF000
            try:
                self.funcmap[extracted_op]()
            except KeyError:
                print("Unknown instruction: %04X" % self.opcode)

        # Default increment
        self.pc += 2

        # Timers
        if self.delay_timer > 0:
            self.delay_timer -= 1
        if self.sound_timer > 0:
            self.sound_timer -= 1
            if self.sound_timer == 0:
                log("Sound plays!")

        # Opcode Handlers
    def setup_funcmap(self):
        # Maps the first nibble or pattern of each opcode to a handler function
        self.funcmap = {
            0x0000: self._0xxx,    # 0nnn / 00E0 / 00EE - SYS call (ignored), clear screen, return from subroutine
            0x1000: self._1nnn,    # 1nnn - Jump to a specific memory address
            0x2000: self._2nnn,    # 2nnn - Call a function (subroutine) at a memory address
            0x3000: self._3xkk,    # 3xkk - Skip next instruction if a register equals a specific number
            0x4000: self._4xkk,    # 4xkk - Skip next instruction if a register does NOT equal a number
            0x5000: self._5xy0,    # 5xy0 - Skip next instruction if two registers are equal
            0x6000: self._6xkk,    # 6xkk - Set a register to a specific number
            0x7000: self._7xkk,    # 7xkk - Add a number to a register
            0x8000: self._8xxx,    # 8xy0..8xyE - Math and logic operations between two registers
            0x9000: self._9xy0,    # 9xy0 - Skip next instruction if two registers are NOT equal
            0xA000: self._Annn,    # Annn - Set a special memory pointer (I) to a specific address
            0xB000: self._Bnnn,    # Bnnn - Jump to an address plus the value of register V0
            0xC000: self._Cxkk,    # Cxkk - Set a register to a random number ANDed with a value
            0xD000: self._Dxyn,    # Dxyn - Draw a small image (sprite) on the screen at X,Y coordinates
            0xE000: self._Exxx,    # Ex9E / ExA1 - Skip next instruction if a key is pressed or not pressed
            0xF000: self._Fxxx,    # Fx07..Fx65 - Timers, memory storage, and waiting for keys
        }
    
    # 0nnn / 00E0 / 00EE - SYS / Clear Screen / Return from Subroutine
    def _0xxx(self):
        if self.opcode == 0x00E0:  # 00E0 - Clear screen
            self.display_buffer = [0] * (64 * 32)
            self.should_draw = True
            log("Clear the display (all pixels turned off)")
        elif self.opcode == 0x00EE:  # 00EE - Return from subroutine
            self.pc = self.stack.pop()
            log("Return from subroutine (go back to the instruction after the CALL)")
        else:  # 0nnn - SYS call (ignored)
            addr = self.opcode & 0x0FFF
            log(f"SYS call to {addr:03X} ignored (old instruction, does nothing)")
    
    # 1nnn - Jump to address
    def _1nnn(self):
        self.pc = self.opcode & 0x0FFF
        log(f"Jump to memory address {self.pc:03X}")
    
    # 2nnn - Call subroutine
    def _2nnn(self):
        self.stack.append(self.pc)
        self.pc = self.opcode & 0x0FFF
        log(f"Call subroutine at address {self.pc:03X} (save return address on stack)")
    
    # 3xkk - Skip next instruction if register equals a number
    def _3xkk(self):
        kk = self.opcode & 0x00FF
        if self.gpio[self.vx] == kk:
            self.pc += 2
            log(f"Skip next instruction: V{self.vx} == {kk}")
    
    # 4xkk - Skip next instruction if register does NOT equal a number
    def _4xkk(self):
        kk = self.opcode & 0x00FF
        if self.gpio[self.vx] != kk:
            self.pc += 2
            log(f"Skip next instruction: V{self.vx} != {kk}")
    
    # 5xy0 - Skip next instruction if two registers are equal
    def _5xy0(self):
        if self.gpio[self.vx] == self.gpio[self.vy]:
            self.pc += 2
            log(f"Skip next instruction: V{self.vx} == V{self.vy}")
    
    # 6xkk - Set a register to a specific number
    def _6xkk(self):
        kk = self.opcode & 0x00FF
        self.gpio[self.vx] = kk
        log(f"Set V{self.vx} = {kk}")
    
    # 7xkk - Add a number to a register
    def _7xkk(self):
        kk = self.opcode & 0x00FF
        old_val = self.gpio[self.vx]
        self.gpio[self.vx] = (old_val + kk) & 0xFF
        log(f"Add {kk} to V{self.vx}: {old_val} + {kk} -> {self.gpio[self.vx]}")
    
    # 8xy0..8xyE - Math and logic operations between two registers
    def _8xxx(self):
        x, y = self.vx, self.vy
        subcode = self.opcode & 0x000F
        if subcode == 0x0:   # LD Vx, Vy
            self.gpio[x] = self.gpio[y]
            log(f"Copy value of V{y} ({self.gpio[y]}) into V{x}")
        elif subcode == 0x1: # OR Vx, Vy
            self.gpio[x] |= self.gpio[y]
            log(f"V{x} = V{x} OR V{y} -> {self.gpio[x]}")
        elif subcode == 0x2: # AND Vx, Vy
            self.gpio[x] &= self.gpio[y]
            log(f"V{x} = V{x} AND V{y} -> {self.gpio[x]}")
        elif subcode == 0x3: # XOR Vx, Vy
            self.gpio[x] ^= self.gpio[y]
            log(f"V{x} = V{x} XOR V{y} -> {self.gpio[x]}")
        elif subcode == 0x4: # ADD Vx, Vy
            res = self.gpio[x] + self.gpio[y]
            self.gpio[0xF] = 1 if res > 0xFF else 0
            self.gpio[x] = res & 0xFF
            log(f"Add V{y} to V{x}: result {self.gpio[x]}, carry={self.gpio[0xF]}")
        elif subcode == 0x5: # SUB Vx, Vy
            self.gpio[0xF] = 1 if self.gpio[x] > self.gpio[y] else 0
            self.gpio[x] = (self.gpio[x] - self.gpio[y]) & 0xFF
            log(f"Subtract V{y} from V{x}: result {self.gpio[x]}, NOT borrow={self.gpio[0xF]}")
        elif subcode == 0x6: # SHR Vx
            self.gpio[0xF] = self.gpio[x] & 1
            self.gpio[x] >>= 1
            log(f"Shift V{x} right by 1: {self.gpio[x]}, least significant bit={self.gpio[0xF]}")
        elif subcode == 0x7: # SUBN Vx, Vy
            self.gpio[0xF] = 1 if self.gpio[y] > self.gpio[x] else 0
            self.gpio[x] = (self.gpio[y] - self.gpio[x]) & 0xFF
            log(f"Set V{x} = V{y} - V{x}: result {self.gpio[x]}, NOT borrow={self.gpio[0xF]}")
        elif subcode == 0xE: # SHL Vx
            self.gpio[0xF] = (self.gpio[x] >> 7) & 1
            self.gpio[x] = (self.gpio[x] << 1) & 0xFF
            log(f"Shift V{x} left by 1: {self.gpio[x]}, most significant bit={self.gpio[0xF]}")
    
    # 9xy0 - Skip next instruction if registers are not equal
    def _9xy0(self):
        if self.gpio[self.vx] != self.gpio[self.vy]:
            self.pc += 2
            log(f"Skip next instruction: V{self.vx} != V{self.vy}")
    
    # Annn - Set I to a memory address
    def _Annn(self):
        self.index = self.opcode & 0x0FFF
        log(f"Set memory pointer I = {self.index:03X}")
    
    # Bnnn - Jump to address plus V0
    def _Bnnn(self):
        addr = self.opcode & 0x0FFF
        self.pc = addr + self.gpio[0]
        log(f"Jump to address V0 + {addr:03X} = {self.pc:03X}")
    
    # Cxkk - Set Vx to random number ANDed with value
    def _Cxkk(self):
        kk = self.opcode & 0x00FF
        val = random.randint(0, 255) & kk
        self.gpio[self.vx] = val
        log(f"Set V{self.vx} = random_byte & {kk} -> {val}")
    
    # Dxyn - Draw sprite at coordinates Vx,Vy
    def _Dxyn(self):
        x_coord = self.gpio[self.vx]
        y_coord = self.gpio[self.vy]
        height = self.opcode & 0x000F
        self.gpio[0xF] = 0
        for row in range(height):
            sprite_byte = self.memory[self.index + row]
            for col in range(8):
                pixel = (sprite_byte >> (7 - col)) & 1
                idx = ((x_coord + col) % 64) + ((y_coord + row) % 32) * 64
                if pixel:
                    if self.display_buffer[idx] == 1:
                        self.gpio[0xF] = 1  # collision flag
                    self.display_buffer[idx] ^= 1
        self.should_draw = True
        log(f"Drew sprite at ({x_coord},{y_coord}), height={height}, collision={self.gpio[0xF]}")
    
    # Ex9E / ExA1 - Skip next instruction if key pressed / not pressed
    def _Exxx(self):
        last_byte = self.opcode & 0x00FF
        key = self.gpio[self.vx]
        if last_byte == 0x9E:  # SKP Vx
            if self.key_inputs[key]:
                self.pc += 2
                log(f"Skip next instruction: key {key} is pressed")
        elif last_byte == 0xA1:  # SKNP Vx
            if not self.key_inputs[key]:
                self.pc += 2
                log(f"Skip next instruction: key {key} is NOT pressed")
    
    # Fx07..Fx65 - Timers, memory, and input
    def _Fxxx(self):
        last_byte = self.opcode & 0x00FF
        x = self.vx
        if last_byte == 0x07:    # LD Vx, DT
            self.gpio[x] = self.delay_timer
            log(f"Set V{x} = delay timer ({self.delay_timer})")
        elif last_byte == 0x0A:  # LD Vx, K
            pressed = False
            for i, state in enumerate(self.key_inputs):
                if state:
                    self.gpio[x] = i
                    pressed = True
                    break
            if not pressed:
                self.pc -= 2
            log(f"Wait for key press -> V{x}: {self.gpio[x] if pressed else 'waiting'}")
        elif last_byte == 0x15:  # LD DT, Vx
            self.delay_timer = self.gpio[x]
            log(f"Set delay timer = V{x} ({self.gpio[x]})")
        elif last_byte == 0x18:  # LD ST, Vx
            self.sound_timer = self.gpio[x]
            log(f"Set sound timer = V{x} ({self.gpio[x]})")
        elif last_byte == 0x1E:  # ADD I, Vx
            old_index = self.index
            self.index = (self.index + self.gpio[x]) & 0xFFFF
            log(f"Increment I by V{x}: {old_index} -> {self.index}")
        elif last_byte == 0x29:  # LD F, Vx
            self.index = self.gpio[x] * 5
            log(f"Set I to the memory location of sprite for digit V{x} ({self.gpio[x]})")
        elif last_byte == 0x33:  # LD B, Vx
            val = self.gpio[x]
            self.memory[self.index] = val // 100
            self.memory[self.index + 1] = (val // 10) % 10
            self.memory[self.index + 2] = val % 10
            log(f"Store BCD of V{x} ({val}) at I, I+1, I+2")
        elif last_byte == 0x55:  # LD [I], Vx
            for i in range(x + 1):
                self.memory[self.index + i] = self.gpio[i]
            log(f"Store registers V0..V{x} in memory starting at I")
        elif last_byte == 0x65:  # LD Vx, [I]
            for i in range(x + 1):
                self.gpio[i] = self.memory[self.index + i]
            log(f"Load registers V0..V{x} from memory starting at I")
