import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
from tkinter.font import Font
import struct

class NESHexEditor:
    def __init__(self, root):
        self.root = root
        self.root.title("NES Hex Editor")
        self.root.geometry("1200x800")
        
        self.rom_data = bytearray()  # Stores PRG-ROM and CHR-ROM data
        self.filename = ""
        self.header = None
        self.prg_size = 0
        self.chr_size = 0
        self.page_size = 4096  # 4KB per page
        self.current_page = 0  # Current page index
        self.total_pages = 0
        
        # UI Setup
        self.setup_ui()
        
    def setup_ui(self):
        # Menu
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Open NES ROM", command=self.open_file)
        file_menu.add_command(label="Save", command=self.save_file)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        
        # Toolbar
        toolbar = tk.Frame(self.root)
        toolbar.pack(fill=tk.X, padx=5, pady=5)
        
        tk.Button(toolbar, text="Open", command=self.open_file).pack(side=tk.LEFT, padx=2)
        tk.Button(toolbar, text="Save", command=self.save_file).pack(side=tk.LEFT, padx=2)
        tk.Button(toolbar, text="Search", command=self.search_dialog).pack(side=tk.LEFT, padx=2)
        tk.Button(toolbar, text="Go to Address", command=self.goto_dialog).pack(side=tk.LEFT, padx=2)
        
        # Page navigation
        nav_frame = tk.Frame(self.root)
        nav_frame.pack(fill=tk.X, padx=5)
        tk.Button(nav_frame, text="<< Prev", command=self.prev_page).pack(side=tk.LEFT, padx=2)
        self.page_label = tk.Label(nav_frame, text="Page 0/0")
        self.page_label.pack(side=tk.LEFT, padx=5)
        tk.Button(nav_frame, text="Next >>", command=self.next_page).pack(side=tk.LEFT, padx=2)
        
        # Main frame with hex view
        main_frame = tk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Hex display
        self.hex_text = scrolledtext.ScrolledText(main_frame, font=Font(family="Courier", size=10), wrap=tk.NONE)
        self.hex_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.hex_text.bind('<KeyRelease>', self.on_hex_key_release)
        self.hex_text.bind('<Button-1>', self.on_hex_click)
        self.hex_text.tag_configure("highlight", background="yellow")
        
        # ASCII sidebar
        ascii_frame = tk.Frame(main_frame)
        ascii_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(5,0))
        
        tk.Label(ascii_frame, text="ASCII", font=("Arial", 10, "bold")).pack()
        self.ascii_text = tk.Text(ascii_frame, height=40, width=16, font=Font(family="Courier", size=10))
        self.ascii_text.pack(fill=tk.Y)
        self.ascii_text.bind('<KeyRelease>', self.on_ascii_key_release)
        self.ascii_text.bind('<Button-1>', self.on_ascii_click)
        self.ascii_text.tag_configure("highlight", background="yellow")
        
        # Status bar
        self.status = tk.Label(self.root, text="Ready", relief=tk.SUNKEN, anchor=tk.W)
        self.status.pack(side=tk.BOTTOM, fill=tk.X)
        
    def parse_nes_header(self, data):
        """Parse iNES or NES 2.0 header and return header info."""
        if len(data) < 16:
            raise ValueError("File too small to be a valid .nes file")
        
        if data[:4] != b'NES\x1A':
            raise ValueError("Invalid .nes file: Missing NES header")
        
        prg_rom_size = data[4] * 16384
        chr_rom_size = data[5] * 8192
        flags_6 = data[6]
        flags_7 = data[7]
        
        is_nes2 = (flags_7 & 0x0C) == 0x08
        if is_nes2:
            prg_rom_size = ((data[9] & 0x0F) << 8 | data[4]) * 16384
            chr_rom_size = ((data[9] >> 4) << 8 | data[5]) * 8192
        
        trainer_size = 512 if (flags_6 & 0x04) else 0
        
        return {
            'prg_size': prg_rom_size,
            'chr_size': chr_rom_size,
            'trainer_size': trainer_size,
            'is_nes2': is_nes2,
            'header_size': 16
        }
    
    def open_file(self):
        filename = filedialog.askopenfilename(filetypes=[("NES ROMs", "*.nes")])
        if filename:
            try:
                with open(filename, 'rb') as f:
                    data = f.read()
                
                self.header = self.parse_nes_header(data)
                header_size = self.header['header_size']
                trainer_size = self.header['trainer_size']
                self.prg_size = self.header['prg_size']
                self.chr_size = self.header['chr_size']
                
                rom_start = header_size + trainer_size
                expected_size = rom_start + self.prg_size + self.chr_size
                if len(data) < expected_size:
                    raise ValueError(f"File too small: Expected {expected_size} bytes, got {len(data)}")
                
                self.rom_data = bytearray(data[rom_start:rom_start + self.prg_size + self.chr_size])
                self.filename = filename
                self.total_pages = (len(self.rom_data) + self.page_size - 1) // self.page_size
                self.current_page = 0
                self.update_display()
                self.status.config(text=f"Loaded: {filename} (PRG: {self.prg_size} bytes, CHR: {self.chr_size} bytes)")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load: {e}")
                self.rom_data = bytearray()
                self.header = None
                self.current_page = 0
                self.total_pages = 0
                self.update_display()
    
    def save_file(self):
        if not self.rom_data or not self.header:
            messagebox.showwarning("Warning", "No file loaded.")
            return
        filename = filedialog.asksaveasfilename(defaultextension=".nes", filetypes=[("NES ROMs", "*.nes")])
        if filename:
            try:
                with open(self.filename, 'rb') as f:
                    original_data = f.read()
                
                header_size = self.header['header_size']
                trainer_size = self.header['trainer_size']
                output_data = bytearray(original_data[:header_size + trainer_size])
                output_data.extend(self.rom_data)
                
                with open(filename, 'wb') as f:
                    f.write(output_data)
                self.status.config(text=f"Saved: {filename}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save: {e}")
    
    def update_display(self):
        self.hex_text.delete(1.0, tk.END)
        self.ascii_text.delete(1.0, tk.END)
        
        if not self.rom_data:
            self.hex_text.insert(tk.END, "No ROM loaded.")
            self.ascii_text.insert(tk.END, "")
            self.ascii_text.config(state=tk.DISABLED)
            self.page_label.config(text="Page 0/0")
            return
        
        self.ascii_text.config(state=tk.NORMAL)
        start = self.current_page * self.page_size
        end = min(start + self.page_size, len(self.rom_data))
        lines = []
        for i in range(start, end, 16):
            chunk = self.rom_data[i:i+16]
            hex_str = ' '.join(f'{b:02X}' for b in chunk)
            pad = '   ' * (16 - len(chunk))
            ascii_str = ''.join(chr(b) if 32 <= b <= 126 else '.' for b in chunk)
            
            line = f"{i:08X}: {hex_str}{pad} {ascii_str}"
            lines.append(line)
            self.ascii_text.insert(tk.END, ascii_str + '\n')
        
        self.hex_text.insert(tk.END, '\n'.join(lines))
        self.ascii_text.config(state=tk.NORMAL)  # Keep ASCII editable
        self.page_label.config(text=f"Page {self.current_page + 1}/{self.total_pages}")
        self.hex_text.see(1.0)
    
    def prev_page(self):
        if self.current_page > 0:
            self.current_page -= 1
            self.update_display()
    
    def next_page(self):
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            self.update_display()
    
    def on_hex_key_release(self, event):
        if not self.rom_data:
            return
        try:
            line, col = self.get_cursor_pos(self.hex_text)
            if col < 57:
                byte_idx = self.current_page * self.page_size + line * 16 + (col // 3)
                if byte_idx < len(self.rom_data):
                    char = self.hex_text.get(f"{line+1}.0 + {col}c", f"{line+1}.0 + {col+2}c").strip()
                    if len(char) == 2 and all(c in '0123456789ABCDEFabcdef' for c in char):
                        val = int(char, 16)
                        self.rom_data[byte_idx] = val
                        self.update_byte_display(byte_idx, val)
                        self.highlight_byte(byte_idx)
        except:
            pass
    
    def on_ascii_key_release(self, event):
        if not self.rom_data:
            return
        try:
            line, col = self.get_cursor_pos(self.ascii_text)
            byte_idx = self.current_page * self.page_size + line * 16 + col
            if byte_idx < len(self.rom_data):
                char = self.ascii_text.get(f"{line+1}.{col}", f"{line+1}.{col+1}")
                if char:
                    val = ord(char)
                    self.rom_data[byte_idx] = val
                    self.update_byte_display(byte_idx, val)
                    self.highlight_byte(byte_idx)
        except:
            pass
    
    def on_hex_click(self, event):
        line, col = self.get_cursor_pos(self.hex_text)
        if col < 57:
            byte_idx = self.current_page * self.page_size + line * 16 + (col // 3)
            if byte_idx < len(self.rom_data):
                self.highlight_byte(byte_idx)
    
    def on_ascii_click(self, event):
        line, col = self.get_cursor_pos(self.ascii_text)
        byte_idx = self.current_page * self.page_size + line * 16 + col
        if byte_idx < len(self.rom_data):
            self.highlight_byte(byte_idx)
    
    def update_byte_display(self, byte_idx, value):
        """Update only the edited byte in both hex and ASCII views."""
        line = (byte_idx % self.page_size) // 16
        hex_col = (byte_idx % 16) * 3
        ascii_col = byte_idx % 16
        
        self.hex_text.delete(f"{line+1}.{hex_col}", f"{line+1}.{hex_col+2}")
        self.hex_text.insert(f"{line+1}.{hex_col}", f"{value:02X}")
        
        self.ascii_text.config(state=tk.NORMAL)
        self.ascii_text.delete(f"{line+1}.{ascii_col}", f"{line+1}.{ascii_col+1}")
        self.ascii_text.insert(f"{line+1}.{ascii_col}", chr(value) if 32 <= value <= 126 else '.')
        self.ascii_text.config(state=tk.NORMAL)
    
    def highlight_byte(self, byte_idx):
        """Highlight the byte in both hex and ASCII views."""
        if byte_idx < self.current_page * self.page_size or byte_idx >= (self.current_page + 1) * self.page_size:
            return
        line = (byte_idx % self.page_size) // 16
        hex_col = (byte_idx % 16) * 3
        ascii_col = byte_idx % 16
        
        self.hex_text.tag_remove("highlight", 1.0, tk.END)
        self.ascii_text.tag_remove("highlight", 1.0, tk.END)
        
        self.hex_text.tag_add("highlight", f"{line+1}.{hex_col}", f"{line+1}.{hex_col+2}")
        self.ascii_text.tag_add("highlight", f"{line+1}.{ascii_col}", f"{line+1}.{ascii_col+1}")
    
    def get_cursor_pos(self, widget):
        index = widget.index(tk.INSERT)
        line = int(index.split('.')[0]) - 1
        col = int(index.split('.')[1])
        return line, col
    
    def search_dialog(self):
        if not self.rom_data:
            messagebox.showwarning("Warning", "No file loaded.")
            return
        search_win = tk.Toplevel(self.root)
        search_win.title("Search")
        search_win.geometry("300x150")
        
        tk.Label(search_win, text="Search hex (e.g., FF or DE AD BE EF):").pack(pady=5)
        entry = tk.Entry(search_win)
        entry.pack(pady=5)
        
        def do_search():
            query = entry.get().upper().strip().replace(" ", "")
            if len(query) % 2 != 0 or not all(c in '0123456789ABCDEF' for c in query):
                messagebox.showerror("Error", "Invalid hex query. Use pairs of hex digits.")
                return
            bytes_query = bytes.fromhex(query)
            results = []
            for i in range(len(self.rom_data) - len(bytes_query) + 1):
                if self.rom_data[i:i+len(bytes_query)] == bytes_query:
                    results.append(i)
            if results:
                self.current_page = results[0] // self.page_size
                self.update_display()
                self.highlight_byte(results[0])
                self.status.config(text=f"Found {len(results)} matches for {query}")
            else:
                self.status.config(text=f"No matches for {query}")
            search_win.destroy()
        
        tk.Button(search_win, text="Search", command=do_search).pack(pady=5)
    
    def goto_dialog(self):
        if not self.rom_data:
            messagebox.showwarning("Warning", "No file loaded.")
            return
        goto_win = tk.Toplevel(self.root)
        goto_win.title("Go to Address")
        goto_win.geometry("300x100")
        
        tk.Label(goto_win, text="Enter address (hex, e.g., 8000):").pack(pady=5)
        entry = tk.Entry(goto_win)
        entry.pack(pady=5)
        
        def do_goto():
            try:
                address = int(entry.get(), 16)
                if 0 <= address < len(self.rom_data):
                    self.current_page = address // self.page_size
                    self.update_display()
                    self.highlight_byte(address)
                    self.status.config(text=f"Jumped to address {address:08X}")
                else:
                    messagebox.showerror("Error", "Address out of range.")
            except ValueError:
                messagebox.showerror("Error", "Invalid hex address.")
            goto_win.destroy()
        
        tk.Button(goto_win, text="Go", command=do_goto).pack(pady=5)

if __name__ == "__main__":
    root = tk.Tk()
    app = NESHexEditor(root)
    root.mainloop()
