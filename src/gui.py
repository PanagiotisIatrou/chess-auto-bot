import os

import multiprocess
import threading
import time
import tkinter as tk
from tkinter import ttk, filedialog
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service as ChromeService
from overlay import run
from stockfish_bot import StockfishBot
from selenium.common import WebDriverException
import keyboard


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
        self.overlay_screen_pipe = None

        # The Stockfish Bot process
        self.stockfish_bot_process = None
        self.overlay_screen_process = None
        self.restart_after_stopping = False

        # Used for storing the match moves
        self.match_moves = []

        # Set the window properties
        master.title("Chess")
        master.geometry("")
        master.iconphoto(True, tk.PhotoImage(file="src/assets/pawn_32x32.png"))
        master.resizable(False, False)
        master.attributes("-topmost", True)
        master.protocol("WM_DELETE_WINDOW", self.on_close_listener)

        # Change the style
        style = ttk.Style()
        style.theme_use("clam")

        # Left frame
        left_frame = tk.Frame(master)

        # Create the status text
        status_label = tk.Frame(left_frame)
        tk.Label(status_label, text="Status:").pack(side=tk.LEFT)
        self.status_text = tk.Label(status_label, text="Inactive", fg="red")
        self.status_text.pack()
        status_label.pack(anchor=tk.NW)
        
        # Create the evaluation info
        self.eval_frame = tk.Frame(left_frame)
        
        # Evaluation (centipawns)
        eval_label = tk.Frame(self.eval_frame)
        tk.Label(eval_label, text="Eval:").pack(side=tk.LEFT)
        self.eval_text = tk.Label(eval_label, text="-")
        self.eval_text.pack()
        eval_label.pack(anchor=tk.NW)
        
        # WDL (win/draw/loss)
        wdl_label = tk.Frame(self.eval_frame)
        tk.Label(wdl_label, text="WDL:").pack(side=tk.LEFT)
        self.wdl_text = tk.Label(wdl_label, text="-")
        self.wdl_text.pack()
        wdl_label.pack(anchor=tk.NW)
        
        # Material advantage
        material_label = tk.Frame(self.eval_frame)
        tk.Label(material_label, text="Material:").pack(side=tk.LEFT)
        self.material_text = tk.Label(material_label, text="-")
        self.material_text.pack()
        material_label.pack(anchor=tk.NW)
        
        # White player accuracy
        white_acc_label = tk.Frame(self.eval_frame)
        tk.Label(white_acc_label, text="Bot Acc:").pack(side=tk.LEFT)
        self.white_acc_text = tk.Label(white_acc_label, text="-")
        self.white_acc_text.pack()
        white_acc_label.pack(anchor=tk.NW)
        
        # Black player accuracy
        black_acc_label = tk.Frame(self.eval_frame)
        tk.Label(black_acc_label, text="Opponent Acc:").pack(side=tk.LEFT)
        self.black_acc_text = tk.Label(black_acc_label, text="-")
        self.black_acc_text.pack()
        black_acc_label.pack(anchor=tk.NW)
        
        self.eval_frame.pack(anchor=tk.NW)

        # Create the website chooser radio buttons
        self.website = tk.StringVar(value="chesscom")
        self.chesscom_radio_button = tk.Radiobutton(
            left_frame,
            text="Chess.com",
            variable=self.website,
            value="chesscom"
        )
        self.chesscom_radio_button.pack(anchor=tk.NW)
        self.lichess_radio_button = tk.Radiobutton(
            left_frame,
            text="Lichess.org",
            variable=self.website,
            value="lichess"
        )
        self.lichess_radio_button.pack(anchor=tk.NW)

        # Create the open browser button
        self.opening_browser = False
        self.opened_browser = False
        self.open_browser_button = tk.Button(
            left_frame,
            text="Open Browser",
            command=self.on_open_browser_button_listener,
        )
        self.open_browser_button.pack(anchor=tk.NW)

        # Create the start button
        self.running = False
        self.start_button = tk.Button(
            left_frame, text="Start", command=self.on_start_button_listener
        )
        self.start_button["state"] = "disabled"
        self.start_button.pack(anchor=tk.NW, pady=5)

        # Create the manual mode checkbox
        self.enable_manual_mode = tk.BooleanVar(value=False)
        self.manual_mode_checkbox = tk.Checkbutton(
            left_frame,
            text="Manual Mode",
            variable=self.enable_manual_mode,
            command=self.on_manual_mode_checkbox_listener,
        )
        self.manual_mode_checkbox.pack(anchor=tk.NW)

        # Create the manual mode instructions
        self.manual_mode_frame = tk.Frame(left_frame)
        self.manual_mode_label = tk.Label(
            self.manual_mode_frame, text="\u2022 Press 3 to make a move"
        )
        self.manual_mode_label.pack(anchor=tk.NW)

        # Create the mouseless mode checkbox
        self.enable_mouseless_mode = tk.BooleanVar(value=False)
        self.mouseless_mode_checkbox = tk.Checkbutton(
            left_frame,
            text="Mouseless Mode",
            variable=self.enable_mouseless_mode
        )
        self.mouseless_mode_checkbox.pack(anchor=tk.NW)

        # Create the non-stop puzzles check button
        self.enable_non_stop_puzzles = tk.IntVar(value=0)
        self.non_stop_puzzles_check_button = tk.Checkbutton(
            left_frame,
            text="Non-stop puzzles",
            variable=self.enable_non_stop_puzzles
        )
        self.non_stop_puzzles_check_button.pack(anchor=tk.NW)

        # Create the non-stop matches check button
        self.enable_non_stop_matches = tk.IntVar(value=0)
        self.non_stop_matches_check_button = tk.Checkbutton(left_frame, text="Non-stop online matches",
                                                            variable=self.enable_non_stop_matches)
        self.non_stop_matches_check_button.pack(anchor=tk.NW)

        # Create the bongcloud check button
        self.enable_bongcloud = tk.IntVar()
        self.bongcloud_check_button = tk.Checkbutton(
            left_frame,
            text="Bongcloud",
            variable=self.enable_bongcloud
        )
        self.bongcloud_check_button.pack(anchor=tk.NW)

        # Create the mouse latency scale
        mouse_latency_frame = tk.Frame(left_frame)
        tk.Label(mouse_latency_frame, text="Mouse Latency (seconds)").pack(side=tk.LEFT, pady=(17, 0))
        self.mouse_latency = tk.DoubleVar(value=0.0)
        self.mouse_latency_scale = tk.Scale(mouse_latency_frame, from_=0.0, to=15, resolution=0.2, orient=tk.HORIZONTAL,
                                          variable=self.mouse_latency)
        self.mouse_latency_scale.pack()
        mouse_latency_frame.pack(anchor=tk.NW)

        # Separator
        separator_frame = tk.Frame(left_frame)
        separator = ttk.Separator(separator_frame, orient="horizontal")
        separator.grid(row=0, column=0, sticky="ew")
        label = tk.Label(separator_frame, text="Stockfish parameters")
        label.grid(row=0, column=0, padx=40)
        separator_frame.pack(anchor=tk.NW, pady=10, expand=True, fill=tk.X)

        # Create the Slow mover entry field
        slow_mover_frame = tk.Frame(left_frame)
        self.slow_mover_label = tk.Label(slow_mover_frame, text="Slow Mover")
        self.slow_mover_label.pack(side=tk.LEFT)
        self.slow_mover = tk.IntVar(value=100)
        self.slow_mover_entry = tk.Entry(
            slow_mover_frame, textvariable=self.slow_mover, justify="center", width=8
        )
        self.slow_mover_entry.pack()
        slow_mover_frame.pack(anchor=tk.NW)

        # Create the skill level scale
        skill_level_frame = tk.Frame(left_frame)
        tk.Label(skill_level_frame, text="Skill Level").pack(side=tk.LEFT, pady=(19, 0))
        self.skill_level = tk.IntVar(value=20)
        self.skill_level_scale = tk.Scale(
            skill_level_frame,
            from_=0,
            to=20,
            orient=tk.HORIZONTAL,
            variable=self.skill_level,
        )
        self.skill_level_scale.pack()
        skill_level_frame.pack(anchor=tk.NW)

        # Create the Stockfish depth scale
        stockfish_depth_frame = tk.Frame(left_frame)
        tk.Label(stockfish_depth_frame, text="Depth").pack(side=tk.LEFT, pady=19)
        self.stockfish_depth = tk.IntVar(value=15)
        self.stockfish_depth_scale = tk.Scale(
            stockfish_depth_frame,
            from_=1,
            to=20,
            orient=tk.HORIZONTAL,
            variable=self.stockfish_depth,
        )
        self.stockfish_depth_scale.pack()
        stockfish_depth_frame.pack(anchor=tk.NW)

        # Create the memory entry field
        memory_frame = tk.Frame(left_frame)
        tk.Label(memory_frame, text="Memory").pack(side=tk.LEFT)
        self.memory = tk.IntVar(value=512)
        self.memory_entry = tk.Entry(
            memory_frame, textvariable=self.memory, justify="center", width=9
        )
        self.memory_entry.pack(side=tk.LEFT)
        tk.Label(memory_frame, text="MB").pack()
        memory_frame.pack(anchor=tk.NW, pady=(0, 15))

        # Create the CPU threads entry field
        cpu_threads_frame = tk.Frame(left_frame)
        tk.Label(cpu_threads_frame, text="CPU Threads").pack(side=tk.LEFT)
        self.cpu_threads = tk.IntVar(value=1)
        self.cpu_threads_entry = tk.Entry(
            cpu_threads_frame, textvariable=self.cpu_threads, justify="center", width=7
        )
        self.cpu_threads_entry.pack()
        cpu_threads_frame.pack(anchor=tk.NW)

        # Separator
        separator_frame = tk.Frame(left_frame)
        separator = ttk.Separator(separator_frame, orient="horizontal")
        separator.grid(row=0, column=0, sticky="ew")
        label = tk.Label(separator_frame, text="Misc")
        label.grid(row=0, column=0, padx=82)
        separator_frame.pack(anchor=tk.NW, pady=10, expand=True, fill=tk.X)

        # Create the topmost check button
        self.enable_topmost = tk.IntVar(value=1)
        self.topmost_check_button = tk.Checkbutton(
            left_frame,
            text="Window stays on top",
            variable=self.enable_topmost,
            onvalue=1,
            offvalue=0,
            command=self.on_topmost_check_button_listener,
        )
        self.topmost_check_button.pack(anchor=tk.NW)

        # Create the select stockfish button
        self.stockfish_path = ""
        self.select_stockfish_button = tk.Button(
            left_frame,
            text="Select Stockfish",
            command=self.on_select_stockfish_button_listener,
        )
        self.select_stockfish_button.pack(anchor=tk.NW)

        # Create the stockfish path text
        self.stockfish_path_text = tk.Label(left_frame, text="", wraplength=180)
        self.stockfish_path_text.pack(anchor=tk.NW)

        left_frame.grid(row=0, column=0, padx=5, sticky=tk.NW)

        # Right frame
        right_frame = tk.Frame(master)

        # Treeview frame
        treeview_frame = tk.Frame(right_frame)

        # Create the moves Treeview
        self.tree = ttk.Treeview(
            treeview_frame,
            column=("#", "White", "Black"),
            show="headings",
            height=23,
            selectmode="browse",
        )
        self.tree.pack(anchor=tk.NW, side=tk.LEFT)

        # # Add the scrollbar to the Treeview
        self.vsb = ttk.Scrollbar(
            treeview_frame,
            orient="vertical",
            command=self.tree.yview
        )
        self.vsb.pack(fill=tk.Y, expand=True)
        self.tree.configure(yscrollcommand=self.vsb.set)

        # Create the columns
        self.tree.column("# 1", anchor=tk.CENTER, width=35)
        self.tree.heading("# 1", text="#")
        self.tree.column("# 2", anchor=tk.CENTER, width=60)
        self.tree.heading("# 2", text="White")
        self.tree.column("# 3", anchor=tk.CENTER, width=60)
        self.tree.heading("# 3", text="Black")

        treeview_frame.pack(anchor=tk.NW)

        # Create the export PGN button
        self.export_pgn_button = tk.Button(
            right_frame, text="Export PGN", command=self.on_export_pgn_button_listener
        )
        self.export_pgn_button.pack(anchor=tk.NW, fill=tk.X)

        right_frame.grid(row=0, column=1, sticky=tk.NW)

        # Start the process checker thread
        process_checker_thread = threading.Thread(target=self.process_checker_thread)
        process_checker_thread.start()

        # Start the browser checker thread
        browser_checker_thread = threading.Thread(target=self.browser_checker_thread)
        browser_checker_thread.start()

        # Start the process communicator thread
        process_communicator_thread = threading.Thread(
            target=self.process_communicator_thread
        )
        process_communicator_thread.start()

        # Start the keyboard listener thread
        keyboard_listener_thread = threading.Thread(
            target=self.keypress_listener_thread
        )
        keyboard_listener_thread.start()

    # Detects if the user pressed the close button
    def on_close_listener(self):
        # Set self.exit to True so that the threads will stop
        self.exit = True
        self.master.destroy()

    # Detects if the Stockfish Bot process is running
    def process_checker_thread(self):
        while not self.exit:
            if (
                self.running
                and self.stockfish_bot_process is not None
                and not self.stockfish_bot_process.is_alive()
            ):
                self.on_stop_button_listener()

                # Restart the process if restart_after_stopping is True
                if self.restart_after_stopping:
                    self.restart_after_stopping = False
                    self.on_start_button_listener()
            time.sleep(0.1)

    # Detects if Selenium Chromedriver is running
    def browser_checker_thread(self):
        while not self.exit:
            try:
                if (
                    self.opened_browser
                    and self.chrome is not None
                    and "target window already closed"
                    in self.chrome.get_log("driver")[-1]["message"]
                ):
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
                if (
                    self.stockfish_bot_pipe is not None
                    and self.stockfish_bot_pipe.poll()
                ):
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
                    elif data[:7] == "RESTART":
                        self.restart_after_stopping = True
                        self.stockfish_bot_pipe.send("DELETE")
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
                    elif data[:5] == "EVAL|":
                        # Parse evaluation data
                        parts = data.split("|")
                        if len(parts) >= 5:
                            eval_str, wdl_str, material_str, bot_accuracy_str, opponent_accuracy_str  = parts[1:]
                            
                            bot_acc = bot_accuracy_str
                            opponent_acc = opponent_accuracy_str
                            
                            # Update the evaluation info
                            self.update_evaluation_display(eval_str, wdl_str, material_str, bot_acc, opponent_acc)
                    elif data[:7] == "ERR_EXE":
                        tk.messagebox.showerror(
                            "Error",
                            "Stockfish path provided is not valid!"
                        )
                    elif data[:8] == "ERR_PERM":
                        tk.messagebox.showerror(
                            "Error",
                            "Stockfish path provided is not executable!"
                        )
                    elif data[:9] == "ERR_BOARD":
                        tk.messagebox.showerror(
                            "Error",
                            "Cant find board!"
                        )
                    elif data[:9] == "ERR_COLOR":
                        tk.messagebox.showerror(
                            "Error",
                            "Cant find player color!"
                        )
                    elif data[:9] == "ERR_MOVES":
                        tk.messagebox.showerror(
                            "Error",
                            "Cant find moves list!"
                        )
                    elif data[:12] == "ERR_GAMEOVER":
                        tk.messagebox.showerror(
                            "Error",
                            "Game has already finished!"
                        )
            except (BrokenPipeError, OSError):
                self.stockfish_bot_pipe = None

            time.sleep(0.1)

    def keypress_listener_thread(self):
        while not self.exit:
            time.sleep(0.1)
            if not self.opened_browser:
                continue

            if keyboard.is_pressed("1"):
                self.on_start_button_listener()
            elif keyboard.is_pressed("2"):
                self.on_stop_button_listener()

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
            chrome_install = ChromeDriverManager().install()

            folder = os.path.dirname(chrome_install)
            chromedriver_path = os.path.join(folder, "chromedriver.exe")

            service = ChromeService(chromedriver_path)
            self.chrome = webdriver.Chrome(
                service=service,
                options=options
            )
        except WebDriverException:
            # No chrome installed
            self.opening_browser = False
            self.open_browser_button["text"] = "Open Browser"
            self.open_browser_button["state"] = "normal"
            self.open_browser_button.update()
            tk.messagebox.showerror(
                "Error",
                "Cant find Chrome. You need to have Chrome installed for this to work.",
            )
            return
        except Exception as e:
            # Other error
            self.opening_browser = False
            self.open_browser_button["text"] = "Open Browser"
            self.open_browser_button["state"] = "normal"
            self.open_browser_button.update()
            tk.messagebox.showerror(
                "Error",
                f"An error occurred while opening the browser: {e}",
            )
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
            tk.messagebox.showerror(
                "Error",
                "Slow Mover must be between 10 and 1000"
            )
            return

        # Check if stockfish path is not empty
        if self.stockfish_path == "":
            tk.messagebox.showerror(
                "Error",
                "Stockfish path is empty"
            )
            return

        # Check if mouseless mode is enabled when on chess.com
        if self.enable_mouseless_mode.get() == 1 and self.website.get() == "chesscom":
            tk.messagebox.showerror(
                "Error", "Mouseless mode is only supported on lichess.org"
            )
            return

        # Create the pipes used for the communication
        # between the GUI and the Stockfish Bot process
        parent_conn, child_conn = multiprocess.Pipe()
        self.stockfish_bot_pipe = parent_conn

        # Create the message queue that is used for the communication
        # between the Stockfish and the Overlay processes
        st_ov_queue = multiprocess.Queue()

        # Create the Stockfish Bot process
        self.stockfish_bot_process = StockfishBot(
            self.chrome_url,
            self.chrome_session_id,
            self.website.get(),
            child_conn,
            st_ov_queue,
            self.stockfish_path,
            self.enable_manual_mode.get() == 1,
            self.enable_mouseless_mode.get() == 1,
            self.enable_non_stop_puzzles.get() == 1,
            self.enable_non_stop_matches.get() == 1,
            self.mouse_latency.get(),
            self.enable_bongcloud.get() == 1,
            self.slow_mover.get(),
            self.skill_level.get(),
            self.stockfish_depth.get(),
            self.memory.get(),
            self.cpu_threads.get(),
        )
        self.stockfish_bot_process.start()

        # Create the overlay
        self.overlay_screen_process = multiprocess.Process(
            target=run, args=(st_ov_queue,)
        )
        self.overlay_screen_process.start()

        # Update the run button
        self.running = True
        self.start_button["text"] = "Starting..."
        self.start_button["state"] = "disabled"
        self.start_button.update()

    def on_stop_button_listener(self):
        # Stop the Stockfish Bot process
        if self.stockfish_bot_process is not None:
            if self.overlay_screen_process is not None:
                self.overlay_screen_process.kill()
                self.overlay_screen_process = None

            if self.stockfish_bot_process.is_alive():
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
        
        # Reset evaluation info
        self.eval_text["text"] = "-"
        self.eval_text["fg"] = "black"
        self.wdl_text["text"] = "-"
        self.material_text["text"] = "-"
        self.material_text["fg"] = "black"
        self.white_acc_text["text"] = "-"
        self.black_acc_text["text"] = "-"
        
        # Update the UI
        self.eval_text.update()
        self.wdl_text.update()
        self.material_text.update()
        self.white_acc_text.update()
        self.black_acc_text.update()

        # Update the run button
        if not self.restart_after_stopping:
            self.start_button["text"] = "Start"
            self.start_button["state"] = "normal"
            self.start_button["command"] = self.on_start_button_listener
        else:
            self.restart_after_stopping = False
            self.on_start_button_listener()
        self.start_button.update()

    def on_topmost_check_button_listener(self):
        if self.enable_topmost.get() == 1:
            self.master.attributes("-topmost", True)
        else:
            self.master.attributes("-topmost", False)

    def on_export_pgn_button_listener(self):
        # Create the file dialog
        f = filedialog.asksaveasfile(
            initialfile="match.pgn",
            defaultextension=".pgn",
            filetypes=[("Portable Game Notation", "*.pgn"), ("All Files", "*.*")],
        )
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
        cells_num = sum(
            [len(self.tree.item(i)["values"]) - 1 for i in self.tree.get_children()]
        )
        if (cells_num % 2) == 0:
            rows_num = len(self.tree.get_children())
            self.tree.insert("", "end", text="1", values=(rows_num + 1, move))
        else:
            self.tree.set(self.tree.get_children()[-1], column=2, value=move)
        self.tree.update()

    # Overwrites the Treeview with the given list of moves
    def set_moves(self, moves):
        self.clear_tree()

        # Insert in pairs
        pairs = list(zip(*[iter(moves)] * 2))
        for i, pair in enumerate(pairs):
            self.tree.insert("", "end", text="1", values=(str(i + 1), pair[0], pair[1]))

        # Insert the remaining one if it exists
        if len(moves) % 2 == 1:
            self.tree.insert("", "end", text="1", values=(len(pairs) + 1, moves[-1]))

        self.tree.update()

    def on_manual_mode_checkbox_listener(self):
        if self.enable_manual_mode.get() == 1:
            self.manual_mode_frame.pack(after=self.manual_mode_checkbox)
            self.manual_mode_frame.update()
        else:
            self.manual_mode_frame.pack_forget()
            self.manual_mode_checkbox.update()

    def update_evaluation_display(self, eval_str, wdl_str, material_str, bot_acc, opponent_acc):
        self.eval_text["text"] = eval_str
        # Color based on eval (positive = green, negative = red)
        try:
            if eval_str.startswith("M"):  # Mate
                mate_value = int(eval_str[1:])
                self.eval_text["fg"] = "green" if mate_value > 0 else "red"
            else:  # Centipawns
                eval_value = float(eval_str)
                self.eval_text["fg"] = "green" if eval_value > 0 else ("black" if eval_value == 0 else "red")
        except ValueError:
            self.eval_text["fg"] = "black"
            
        # Update WDL
        self.wdl_text["text"] = wdl_str
        
        # Update material
        self.material_text["text"] = material_str
        # Color based on material
        try:
            if material_str.startswith("+"):
                self.material_text["fg"] = "green"
            elif material_str.startswith("-"):
                self.material_text["fg"] = "red"
            else:
                self.material_text["fg"] = "black"
        except:
            self.material_text["fg"] = "black"
            
        # Update accuracy values
        self.white_acc_text["text"] = bot_acc
        self.black_acc_text["text"] = opponent_acc
        
        # Update the UI
        self.eval_text.update()
        self.wdl_text.update()
        self.material_text.update()
        self.white_acc_text.update()
        self.black_acc_text.update()


if __name__ == "__main__":
    window = tk.Tk()
    my_gui = GUI(window)
    window.mainloop()
