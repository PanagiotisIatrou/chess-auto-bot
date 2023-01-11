from selenium.common import NoSuchElementException
from selenium.webdriver.common.by import By

from grabbers.grabber import Grabber


class ChesscomGrabber(Grabber):
    def __init__(self, chrome_url, chrome_session_id):
        super().__init__(chrome_url, chrome_session_id)
        self.moves_list = {}

    def update_board_elem(self):
        try:
            self._board_elem = self.chrome.find_element(By.XPATH, "//*[@id='board-vs-personalities']")
        except NoSuchElementException:
            try:
                self._board_elem = self.chrome.find_element(By.XPATH, "//*[@id='board-single']")
            except NoSuchElementException:
                self._board_elem = None

    def is_white(self):
        # Find the square names list
        square_names = None
        try:
            coordinates = self.chrome.find_element(By.XPATH, "//*[@id='board-vs-personalities']//*[name()='svg']")
            square_names = coordinates.find_elements(By.XPATH, ".//*")
        except NoSuchElementException:
            try:
                coordinates = self.chrome.find_elements(By.XPATH, "//*[@id='board-single']//*[name()='svg']")
                coordinates = [x for x in coordinates if x.get_attribute("class") == "coordinates"][0]
                square_names = coordinates.find_elements(By.XPATH, ".//*")
            except NoSuchElementException:
                return None

        # Find the square with the smallest x and biggest y values (bottom left number)
        elem = None
        min_x = None
        max_y = None
        for i in range(len(square_names)):
            name_element = square_names[i]
            x = float(name_element.get_attribute("x"))
            y = float(name_element.get_attribute("y"))

            if i == 0 or (x <= min_x and y >= max_y):
                min_x = x
                max_y = y
                elem = name_element

        # Use this square to determine whether the player is white or black
        num = elem.text
        if num == "1":
            return True
        else:
            return False

    def is_game_over(self):
        try:
            # Find the game over window
            game_over_window = self.chrome.find_element(By.CLASS_NAME, "board-modal-container")
            if game_over_window is not None:
                return True
            else:
                return False
        except NoSuchElementException:
            # Return False since the game over window is not found
            return False

    def get_move_list(self):
        # Find the moves list
        try:
            move_list_elem = self.chrome.find_element(By.TAG_NAME, "vertical-move-list")
        except NoSuchElementException:
            return None

        # Select all children with class containing "white node" or "black node"
        # Moves that are not pawn moves have a different structure
        # containing children
        if not self.moves_list:
            # If the moves list is empty, find all moves
            moves = move_list_elem.find_elements(By.CSS_SELECTOR, "div.move [data-ply]")
        else:
            # If the moves list is not empty, find only the new moves
            moves = move_list_elem.find_elements(By.CSS_SELECTOR, "div.move [data-ply]:not([data-processed])")

        for move in moves:
            move_class = move.get_attribute("class")

            # Check if it is indeed a move
            if "white node" in move_class or "black node" in move_class:
                # Check if it has a figure
                try:
                    child = move.find_element(By.XPATH, "./*")
                    figure = child.get_attribute("data-figurine")
                except NoSuchElementException:
                    figure = None

                # Check if it was en-passant or figure-move
                if figure is None:
                    # If the moves_list is empty or the last move was not the current move
                    self.moves_list[move.get_attribute("data-ply")] = move.text
                else:
                    # Check if it is promotion
                    if "=" in move.text:
                        m = move.text + figure
                        # If the move is a check, add the + in the end
                        if "+" in m:
                            m = m.replace("+", "")
                            m += "+"

                        # If the moves_list is empty or the last move was not the current move
                        self.moves_list[move.get_attribute("data-ply")] = m
                    else:
                        # If the moves_list is empty or the last move was not the current move
                        self.moves_list[move.get_attribute("data-ply")] = figure + move.text

                # Mark the move as processed
                self.chrome.execute_script("arguments[0].setAttribute('data-processed', 'true')", move)

        return [val for val in self.moves_list.values()]

    def is_game_puzzles(self):
        return False

    def click_puzzle_next(self):
        pass

    def make_mouseless_move(self, move, move_count):
        pass
