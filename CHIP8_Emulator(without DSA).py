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
class cpu (pyglet.window.Window):
    #@Override
    def on_key_press(self, symbol, modifiers):

    #@Override
    def on_ket_release(self, symbol, modifiers):

    def main(self): #just about every emulator has a main
        self.initialize()
        self.load_rom(sys.argv[1])
        while not self.has_exit:
            self.dispatch_events()
            self.cycle()
            self.draw()
    
    def initialize(self):
        self.clear() # clears pyglet window
        self.memory = [0]*4096 # max 4096
        self.gpio = [0]*16 # max 16
        self.display_buffer = [0]*64*32 # 64*32
        self.stack = []
        self.key_inputs = [0]*16
        self.opcode = 0
        self.index = 0

        self.delay_timer = 0
        self.sound_timer = 0
        self.should_draw = False #so that we only update the display when needed

        self.pc = 0x200 #offset is equal to 0x200 (Cogwood's reference)

        i = 0
        while i < 80:
            #load 80-char font set
            self.memory[i] = self.fonts[i]
            i += 1

    #read ROM bianary and read into memory
    def load_rom(self, rom_path):
        log("Loading %s..." % rom_path) #log is so that user can turn on/off log messages when running
        binary = open(rom_path, "rb") .read()
        i = 0
        while i < len(bianary):
            self.memory[i = 0x200] = ord(binary[i])
            i += 1