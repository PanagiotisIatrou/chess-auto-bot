from selenium.common import NoSuchElementException
from selenium.webdriver.common.by import By

from grabbers.grabber import Grabber


class LichessGrabber(Grabber):
    def __init__(self, chrome_url, chrome_session_id):
        super().__init__(chrome_url, chrome_session_id)

    def update_board_elem(self):
        try:
            # Try finding the normal board
            self._board_elem = self.chrome.find_element(By.XPATH, '//*[@id="main-wrap"]/main/div[1]/div[1]/div/cg-container')
        except NoSuchElementException:
            try:
                # Try finding the board in the puzzles page
                self._board_elem = self.chrome.find_element(By.XPATH, '/html/body/div[2]/main/div[1]/div/cg-container')
            except NoSuchElementException:
                self._board_elem = None

    def update_player_color(self):
        # Get "ranks" child
        children = self._board_elem.find_elements(By.XPATH, "./*")
        child = [x for x in children if "ranks" in x.get_attribute("class")][0]
        if child.get_attribute("class") == "ranks":
            self._is_white = True
        else:
            self._is_white = False

    def is_game_over(self):
        try:
            # Find the game over window
            game_over_window = self.chrome.find_element(By.XPATH, '//*[@id="main-wrap"]/main/aside/div/section[2]')
            if game_over_window is not None:
                return True
            else:
                return False
        except NoSuchElementException:
            # Try finding the puzzles game over window
            try:
                game_over_window = self.chrome.find_element(By.XPATH, '/html/body/div[2]/main/div[2]/div[3]/div[1]')
                if game_over_window is not None and game_over_window.text == "Success!":
                    return True
                else:
                    return False
            except NoSuchElementException:
                return False

    def get_move_list(self):
        # Find the moves list
        move_list_elem = None
        puzzles = False
        try:
            # Try finding the normal move list
            move_list_elem = self.chrome.find_element(By.XPATH, '//*[@id="main-wrap"]/main/div[1]/rm6/l4x')
        except NoSuchElementException:
            try:
                move_list_elem = self.chrome.find_element(By.XPATH, '//*[@id="main-wrap"]/main/div[1]/rm6')
                if move_list_elem is not None:
                    return []
            except NoSuchElementException:
                try:
                    # Try finding the move list in the puzzles page
                    move_list_elem = self.chrome.find_element(By.XPATH, '/html/body/div[2]/main/div[2]/div[2]/div')
                    puzzles = True
                except NoSuchElementException:
                    return None

        # Get a list with all the lines with the moves
        children = None
        try:
            if not puzzles:
                children = move_list_elem.find_elements(By.TAG_NAME, "u8t")
            else:
                children = move_list_elem.find_elements(By.TAG_NAME, "move")
        except NoSuchElementException:
            return None

        moves_list = [move.text for move in children]
        return moves_list
