import multiprocess
import threading
import time
import tkinter as tk
from tkinter import ttk, filedialog
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from stockfish_bot import StockfishBot
from selenium.common import WebDriverException


class GUI:
    def __init__(self, master):
        self.master = master

        # Used for closing the threads
        self.exit = False

        # The Selenium Chrome driver
        self.chrome = None

        # # Used for storing the Stockfish Bot class Instance
        # self.stockfish_bot = None
        self.chrome_url = None
        self.chrome_session_id = None

        # Used for the communication between the GUI
        # and the Stockfish Bot process
        self.stockfish_bot_pipe = None

        # The Stockfish Bot process
        self.stockfish_bot_process = None

        # Used for storing the match moves
        self.match_moves = []

        # Set the window properties
        master.title("Chess")
        master.geometry("370x320")
        master.iconphoto(True, tk.PhotoImage(file="assets/pawn_32x32.png"))
        master.resizable(False, False)
        master.attributes('-topmost', True)
        master.protocol("WM_DELETE_WINDOW", self.on_close_listener)

        # Change the style
        style = ttk.Style()
        style.theme_use('clam')

        # Separator
        ttk.Separator(master, orient='horizontal').place(x=0, y=0, width=350)

        # Create the status text
        tk.Label(master, text="Status:").place(x=0, y=5)
        self.status_text = tk.Label(master, text="Inactive", fg="red")
        self.status_text.place(x=45, y=5)

        # Create the website chooser radio buttons
        self.website = tk.StringVar(value="chesscom")
        self.chesscom_radio_button = tk.Radiobutton(master, text="Chess.com", variable=self.website, value="chesscom")
        self.chesscom_radio_button.place(x=0, y=25)
        self.lichess_radio_button = tk.Radiobutton(master, text="Lichess.org", variable=self.website, value="lichess")
        self.lichess_radio_button.place(x=0, y=45)

        # Create the open browser button
        self.opening_browser = False
        self.opened_browser = False
        self.open_browser_button = tk.Button(master, text="Open Browser", command=self.on_open_browser_button_listener)
        self.open_browser_button.place(x=5, y=70)

        # Create the start button
        self.running = False
        self.start_button = tk.Button(master, text="Start", command=self.on_start_button_listener)
        self.start_button["state"] = "disabled"
        self.start_button.place(x=5, y=100)

        # Create the Slow mover entry field
        tk.Label(master, text="Slow Mover").place(x=0, y=130)
        self.slow_mover = tk.IntVar(value=100)
        self.slow_mover_entry = tk.Entry(master, textvariable=self.slow_mover, width=35)
        self.slow_mover_entry.place(x=5, y=155, width=50)

        # Create the bongcloud check button
        self.enable_bongcloud = tk.IntVar()
        self.bongcloud_check_button = tk.Checkbutton(window, text='Bongcloud', variable=self.enable_bongcloud, onvalue=1, offvalue=0)
        self.bongcloud_check_button.place(x=0, y=180)

        # Separator
        ttk.Separator(master, orient='horizontal').place(x=0, y=205, width=195)

        # Create the topmost check button
        self.enable_topmost = tk.IntVar(value=1)
        self.topmost_check_button = tk.Checkbutton(window, text='Window stays on top', variable=self.enable_topmost, onvalue=1, offvalue=0, command=self.on_topmost_check_button_listener)
        self.topmost_check_button.place(x=0, y=210)

        # Create the select stockfish button
        self.stockfish_path = ""
        self.select_stockfish_button = tk.Button(master, text="Select Stockfish", command=self.on_select_stockfish_button_listener)
        self.select_stockfish_button.place(x=5, y=235)

        # Create the stockfish path text
        self.stockfish_path_text = tk.Label(master, text="", wraplength=180)
        self.stockfish_path_text.place(x=5, y=261)

        # Create the moves Treeview
        self.tree = ttk.Treeview(master, column=("#", "White", "Black"), show='headings', height=13, selectmode='browse')
        self.tree.place(x=195, y=0)

        # Add the scrollbar to the Treeview
        self.vsb = ttk.Scrollbar(master, orient="vertical", command=self.tree.yview)
        self.vsb.place(x=195 + 155 + 5, y=0, height=130 * 2 + 29)
        self.tree.configure(yscrollcommand=self.vsb.set)

        # Create the columns
        self.tree.column("# 1", anchor=tk.CENTER, width=35)
        self.tree.heading("# 1", text="#")
        self.tree.column("# 2", anchor=tk.CENTER, width=60)
        self.tree.heading("# 2", text="White")
        self.tree.column("# 3", anchor=tk.CENTER, width=60)
        self.tree.heading("# 3", text="Black")

        # Create the export PGN button
        self.export_pgn_button = tk.Button(master, text="Export PGN", command=self.on_export_pgn_button_listener)
        self.export_pgn_button.place(x=195, y=290, width=174)

        # Start the process checker thread
        process_checker_thread = threading.Thread(target=self.process_checker_thread)
        process_checker_thread.start()

        # Start the browser checker thread
        browser_checker_thread = threading.Thread(target=self.browser_checker_thread)
        browser_checker_thread.start()

        # Start the process communicator thread
        process_communicator_thread = threading.Thread(target=self.process_communicator_thread)
        process_communicator_thread.start()

    # Detects if the user pressed the close button
    def on_close_listener(self):
        # Set self.exit to True so that the threads will stop
        self.exit = True
        self.master.destroy()

    # Detects if the Stockfish Bot process is running
    def process_checker_thread(self):
        while not self.exit:
            if self.running and self.stockfish_bot_process is not None and not self.stockfish_bot_process.is_alive():
                self.stockfish_bot_process = None
                if self.stockfish_bot_pipe is not None:
                    self.stockfish_bot_pipe.close()
                self.stockfish_bot_pipe = None
                self.on_stop_button_listener()
            time.sleep(0.1)

    # Detects if Selenium Chromedriver is running
    def browser_checker_thread(self):
        while not self.exit:
            try:
                if self.opened_browser and self.chrome is not None and "target window already closed" in self.chrome.get_log('driver')[-1]["message"]:
                    self.opened_browser = False

                    # Set Opening Browser button state to closed
                    self.open_browser_button["text"] = "Open Browser"
                    self.open_browser_button["state"] = "normal"
                    self.open_browser_button.update()

                    self.on_stop_button_listener()
                    self.chrome = None
            except IndexError:
                pass
            time.sleep(0.1)

    # Responsible for communicating with the Stockfish Bot process
    # The pipe can receive the following commands:
    # - "START": Resets and starts the Stockfish Bot
    # - "S_MOVE": Sends the Stockfish Bot a single move to make
    #   Ex. "S_MOVEe4
    # - "M_MOVE": Sends the Stockfish Bot multiple moves to make
    #   Ex. "S_MOVEe4,c5,Nf3
    # - "ERR_EXE": Notifies the GUI that the Stockfish Bot can't initialize Stockfish
    # - "ERR_PERM": Notifies the GUI that the Stockfish Bot can't execute the Stockfish executable
    # - "ERR_BOARD": Notifies the GUI that the Stockfish Bot can't find the board
    # - "ERR_COLOR": Notifies the GUI that the Stockfish Bot can't find the player color
    # - "ERR_MOVES": Notifies the GUI that the Stockfish Bot can't find the moves list
    # - "ERR_GAMEOVER": Notifies the GUI that the current game is already over
    def process_communicator_thread(self):
        while not self.exit:
            try:
                if self.stockfish_bot_pipe is not None and self.stockfish_bot_pipe.poll():
                    data = self.stockfish_bot_pipe.recv()
                    if data == "START":
                        self.clear_tree()
                        self.match_moves = []

                        # Update the status text
                        self.status_text["text"] = "Running"
                        self.status_text["fg"] = "green"
                        self.status_text.update()

                        # Update the run button
                        self.start_button["text"] = "Stop"
                        self.start_button["state"] = "normal"
                        self.start_button["command"] = self.on_stop_button_listener
                        self.start_button.update()
                    elif data[:6] == "S_MOVE":
                        move = data[6:]
                        self.match_moves.append(move)
                        self.insert_move(move)
                        self.tree.yview_moveto(1)
                    elif data[:6] == "M_MOVE":
                        moves = data[6:].split(",")
                        self.match_moves += moves
                        self.set_moves(moves)
                        self.tree.yview_moveto(1)
                    elif data[:7] == "ERR_EXE":
                        tk.messagebox.showerror("Error", "Stockfish path provided is not valid!")
                    elif data[:8] == "ERR_PERM":
                        tk.messagebox.showerror("Error", "Stockfish path provided is not executable!")
                    elif data[:9] == "ERR_BOARD":
                        tk.messagebox.showerror("Error", "Cant find board!")
                    elif data[:9] == "ERR_COLOR":
                        tk.messagebox.showerror("Error", "Cant find player color!")
                    elif data[:9] == "ERR_MOVES":
                        tk.messagebox.showerror("Error", "Cant find moves list!")
                    elif data[:12] == "ERR_GAMEOVER":
                        tk.messagebox.showerror("Error", "Game has already finished!")
            except (BrokenPipeError, OSError):
                self.stockfish_bot_pipe = None

            time.sleep(0.1)

    def on_open_browser_button_listener(self):
        # Set Opening Browser button state to opening
        self.opening_browser = True
        self.open_browser_button["text"] = "Opening Browser..."
        self.open_browser_button["state"] = "disabled"
        self.open_browser_button.update()

        # Open Webdriver
        options = webdriver.ChromeOptions()
        options.add_experimental_option("excludeSwitches", ["enable-logging", "enable-automation"])
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option('useAutomationExtension', False)
        try:
            self.chrome = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        except WebDriverException:
            # No chrome installed
            self.opening_browser = False
            self.open_browser_button["text"] = "Open Browser"
            self.open_browser_button["state"] = "normal"
            self.open_browser_button.update()
            tk.messagebox.showerror("Error", "Cant find Chrome. You need to have Chrome installed for this to work.")
            return

        # Open chess.com
        if self.website.get() == "chesscom":
            self.chrome.get("https://www.chess.com")
        else:
            self.chrome.get("https://www.lichess.org")

        # Build Stockfish Bot
        self.chrome_url = self.chrome.service.service_url
        self.chrome_session_id = self.chrome.session_id

        # Set Opening Browser button state to opened
        self.opening_browser = False
        self.opened_browser = True
        self.open_browser_button["text"] = "Browser is open"
        self.open_browser_button["state"] = "disabled"
        self.open_browser_button.update()

        # Enable run button
        self.start_button["state"] = "normal"
        self.start_button.update()

    def on_start_button_listener(self):
        # Check if Slow mover value is valid
        slow_mover = self.slow_mover.get()
        if slow_mover < 10 or slow_mover > 1000:
            tk.messagebox.showerror("Error", "Slow Mover must be between 10 and 1000")
            return

        # Check if stockfish path is not empty
        if self.stockfish_path == "":
            tk.messagebox.showerror("Error", "Stockfish path is empty")
            return

        # Create the pipes used for the communication
        # between the GUI and the Stockfish Bot process
        parent_conn, child_conn = multiprocess.Pipe()
        self.stockfish_bot_pipe = parent_conn

        # Create the Stockfish Bot process
        self.stockfish_bot_process = StockfishBot(self.chrome_url, self.chrome_session_id, self.website.get(), child_conn, self.stockfish_path, self.enable_bongcloud.get() == 1, self.slow_mover.get())
        # self.stockfish_bot_process = multiprocess.Process(target=self.stockfish_bot.run, args=(child_conn, self.stockfish_path, self.enable_bongcloud.get() == 1, self.slow_mover.get()))
        self.stockfish_bot_process.start()

        # Update the run button
        self.running = True
        self.start_button["text"] = "Starting..."
        self.start_button["state"] = "disabled"
        self.start_button.update()

    def on_stop_button_listener(self):
        # Stop the Stockfish Bot process
        if self.stockfish_bot_process is not None:
            self.stockfish_bot_process.kill()
            self.stockfish_bot_process = None

        # Close the Stockfish Bot pipe
        if self.stockfish_bot_pipe is not None:
            self.stockfish_bot_pipe.close()
            self.stockfish_bot_pipe = None

        # Update the status text
        self.running = False
        self.status_text["text"] = "Inactive"
        self.status_text["fg"] = "red"
        self.status_text.update()

        # Update the run button
        self.start_button["text"] = "Start"
        self.start_button["state"] = "normal"
        self.start_button["command"] = self.on_start_button_listener
        self.start_button.update()

    def on_topmost_check_button_listener(self):
        if self.enable_topmost.get() == 1:
            self.master.attributes("-topmost", True)
        else:
            self.master.attributes("-topmost", False)

    def on_export_pgn_button_listener(self):
        # Create the file dialog
        f = filedialog.asksaveasfile(initialfile='match.pgn', defaultextension=".pgn", filetypes=[("Portable Game Notation", "*.pgn"), ("All Files", "*.*")])
        if f is None:
            return

        # Write the PGN to the file
        data = ""
        for i in range(len(self.match_moves) // 2 + 1):
            if len(self.match_moves) % 2 == 0 and i == len(self.match_moves) // 2:
                continue
            data += str(i + 1) + ". "
            data += self.match_moves[i * 2] + " "
            if (i * 2) + 1 < len(self.match_moves):
                data += self.match_moves[i * 2 + 1] + " "
        f.write(data)
        f.close()

    def on_select_stockfish_button_listener(self):
        # Create the file dialog
        f = filedialog.askopenfilename()
        if f is None:
            return

        # Set the Stockfish path
        self.stockfish_path = f
        self.stockfish_path_text["text"] = self.stockfish_path
        self.stockfish_path_text.update()

    # Clears the Treeview
    def clear_tree(self):
        self.tree.delete(*self.tree.get_children())
        self.tree.update()

    # Inserts a move into the Treeview
    def insert_move(self, move):
        cells_num = sum([len(self.tree.item(i)["values"]) - 1 for i in self.tree.get_children()])
        if (cells_num % 2) == 0:
            rows_num = len(self.tree.get_children())
            self.tree.insert('', 'end', text="1", values=(rows_num + 1, move))
        else:
            self.tree.set(self.tree.get_children()[-1], column=2, value=move)
        self.tree.update()

    # Overwrites the Treeview with the given list of moves
    def set_moves(self, moves):
        self.clear_tree()

        # Insert in pairs
        pairs = list(zip(*[iter(moves)] * 2))
        for i, pair in enumerate(pairs):
            self.tree.insert('', 'end', text="1", values=(str(i + 1), pair[0], pair[1]))

        # Insert the remaining one if it exists
        if len(moves) % 2 == 1:
            self.tree.insert('', 'end', text="1", values=(len(pairs) + 1, moves[-1]))

        self.tree.update()


if __name__ == '__main__':
    window = tk.Tk()
    my_gui = GUI(window)
    window.mainloop()
