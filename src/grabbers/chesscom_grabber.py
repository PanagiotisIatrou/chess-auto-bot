from selenium.common import NoSuchElementException
from selenium.webdriver.common.by import By

from grabbers.grabber import Grabber


class ChesscomGrabber(Grabber):
    def __init__(self, chrome_url, chrome_session_id):
        super().__init__(chrome_url, chrome_session_id)

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
        # Move lines in bot games have different
        # structure than online games
        vs_bot = False

        # Find the moves list
        move_list_elem = None
        try:
            move_list_elem = self.chrome.find_element(By.XPATH, "/html/body/div[3]/div/vertical-move-list")
            vs_bot = True
        except NoSuchElementException:
            try:
                move_list_elem = self.chrome.find_element(By.XPATH, "//*[@id='move-list']/vertical-move-list")
            except NoSuchElementException:
                try:
                    move_list_elem = self.chrome.find_element(By.XPATH, "/html/body/div[4]/div/vertical-move-list")
                except NoSuchElementException:
                    return None

        # Get a list with all the lines with the moves
        move_lines = None
        try:
            move_lines = move_list_elem.find_elements(By.XPATH, "./*")
        except NoSuchElementException:
            return None

        # Select all children with class containing "white node" or "black node"
        # Moves that are not pawn moves have a different structure
        # containing children

        moves_list = []
        for move_line in move_lines:
            moves = move_line.find_elements(By.XPATH, "./*")
            for move in moves:
                move_class = move.get_attribute("class")

                # Check if it is indeed a move
                if "white node" in move_class or "black node" in move_class:
                    # Check if it has a figure
                    child = None
                    try:
                        child = move.find_element(By.XPATH, "./*")
                    except NoSuchElementException:
                        child = None

                    if child is None:
                        moves_list.append(move.text)
                    else:
                        figure = child.get_attribute("data-figurine")

                        # Check if it was en-passant or figure-move
                        if figure is None:
                            moves_list.append(move.text)
                        else:
                            # Check if it is promotion
                            if "=" in move.text:
                                m = move.text + figure
                                # If the move is a check, add the + in the end
                                if "+" in m:
                                    m = m.replace("+", "")
                                    m += "+"
                                moves_list.append(m)
                            else:
                                moves_list.append(figure + move.text)

        return moves_list

    def is_game_puzzles(self):
        return False

    def click_puzzle_next(self):
        pass